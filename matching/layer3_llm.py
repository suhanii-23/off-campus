import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from collectors.base import RawJob
from config import settings
from matching.categories import CATEGORY_KEYWORDS

logger = logging.getLogger(__name__)

_client = None

MAX_DESCRIPTION_CHARS = 4000


def get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


@dataclass
class Layer3Result:
    score: float
    categories: list[str]
    experience_fit: str  # Strong | Moderate | Weak
    india_eligible: bool
    reasons: list[str] = field(default_factory=list)


_CLASSIFY_TOOL = {
    "name": "classify_job",
    "description": (
        "Classify how well this job posting matches the candidate's profile, "
        "using ONLY information present in the posting and profile."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "description": "Match score from 0 (irrelevant) to 100 (perfect match).",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(CATEGORY_KEYWORDS.keys())},
                "description": "All applicable categories, even for unconventional titles.",
            },
            "experience_fit": {
                "type": "string",
                "enum": ["Strong", "Moderate", "Weak"],
                "description": "How well the role's seniority/experience bar fits a final-year student.",
            },
            "india_eligible": {
                "type": "boolean",
                "description": "Whether a candidate based in India could realistically apply/work this role.",
            },
            "reasons": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 5 short bullet reasons explaining the score.",
            },
        },
        "required": ["score", "categories", "experience_fit", "india_eligible", "reasons"],
    },
}

PROMPT_TEMPLATE = """You are screening a job posting for a final-year engineering student \
job-hunting for software engineering and AI/ML roles. Bias toward RECALL: if the role is \
plausibly relevant even under an unconventional title, say so.

CANDIDATE PROFILE
Skills: {skills}
Summary: {profile_blurb}

JOB POSTING
Title: {title}
Company: {company_name}
Location: {location}
Description:
{description}

Classify this job using the classify_job tool."""


def _build_prompt(raw_job: RawJob, profile: dict) -> str:
    return PROMPT_TEMPLATE.format(
        skills=", ".join(profile.get("skills", [])),
        profile_blurb=profile.get("profile_blurb", "").strip(),
        title=raw_job.title,
        company_name=raw_job.company_name,
        location=raw_job.location_raw or "unspecified",
        description=(raw_job.description_raw or "")[:MAX_DESCRIPTION_CHARS],
    )


def call_layer3_api(raw_job: RawJob, profile: dict) -> tuple[Layer3Result, dict]:
    """Call the Anthropic API and return both the parsed result and the raw
    tool-input dict (the latter is what gets cached on the Job row)."""
    client = get_client()
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=600,
        tools=[_CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_job"},
        messages=[{"role": "user", "content": _build_prompt(raw_job, profile)}],
    )

    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    data = tool_use_block.input

    result = Layer3Result(
        score=float(data["score"]),
        categories=list(data.get("categories", [])),
        experience_fit=data.get("experience_fit", "Moderate"),
        india_eligible=bool(data.get("india_eligible", True)),
        reasons=[f"LLM: {r}" for r in data.get("reasons", [])],
    )
    return result, data


def _result_from_cached_response(score: float, data: dict) -> Layer3Result:
    return Layer3Result(
        score=float(score),
        categories=list(data.get("categories", [])),
        experience_fit=data.get("experience_fit", "Moderate"),
        india_eligible=bool(data.get("india_eligible", True)),
        reasons=[f"LLM: {r}" for r in data.get("reasons", [])],
    )


def make_cached_layer3_fn(existing_job=None) -> Callable[[RawJob, dict], Optional[Layer3Result]]:
    """Build a layer3_fn for matching.scorer.score_job that transparently
    caches on `existing_job` (a database.models.Job row, or None for a
    brand-new job). Cache key is content_hash: unchanged postings never
    re-hit the Anthropic API on later scans. Callers still need to
    session.commit() afterward to persist the cached response.
    """

    def _fn(raw_job: RawJob, profile: dict) -> Optional[Layer3Result]:
        if (
            existing_job is not None
            and existing_job.layer3_raw_response
            and existing_job.score_layer3 is not None
        ):
            return _result_from_cached_response(existing_job.score_layer3, existing_job.layer3_raw_response)

        try:
            result, raw_data = call_layer3_api(raw_job, profile)
        except Exception as exc:  # network/API errors must not kill the run
            logger.warning("Layer 3 LLM call failed for %s: %s", raw_job.apply_url, exc)
            return None

        if existing_job is not None:
            existing_job.layer3_raw_response = raw_data
            existing_job.score_layer3 = result.score

        return result

    return _fn
