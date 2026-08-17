from dataclasses import dataclass, field
from typing import Callable, Optional

from collectors.base import RawJob
from config import settings
from matching.layer1_rules import score_layer1
from matching.layer2_embeddings import score_layer2


@dataclass
class ScoreResult:
    final: float
    layer1: float
    layer2: float
    layer3: Optional[float]
    layer3_invoked: bool
    categories: list[str]
    experience_fit: str
    india_eligible: bool
    reasons: list[str] = field(default_factory=list)


def score_job(
    raw_job: RawJob,
    profile: dict,
    layer3_fn: Optional[Callable[[RawJob, dict], Optional[object]]] = None,
) -> ScoreResult:
    """Run the full layered scoring pipeline for one job.

    `layer3_fn`, when provided, is called as `layer3_fn(raw_job, profile)`
    and must return an object with `.score`, `.categories`,
    `.experience_fit`, `.india_eligible`, `.reasons` attributes (see
    matching.layer3_llm.Layer3Result), or None. Injected as a callable
    rather than imported directly so this function stays testable without
    a real Anthropic API key or DB session — main.py wires the real
    DB-cached implementation in.
    """
    l1 = score_layer1(raw_job, profile)
    l2 = score_layer2(raw_job.description_raw, profile.get("profile_blurb", ""))

    combined_l1_l2 = settings.WEIGHT_L1_NO_L3 * l1.score + settings.WEIGHT_L2_NO_L3 * l2

    borderline = settings.LAYER3_BORDERLINE_LOW <= combined_l1_l2 <= settings.LAYER3_BORDERLINE_HIGH
    unconventional_dense = (
        not l1.title_synonym_hit and len(l1.matched_skills) >= settings.LAYER3_UNCONVENTIONAL_MIN_SKILLS
    )
    skip_for_seniority = (
        l1.seniority_rejected and combined_l1_l2 < settings.LAYER3_SKIP_SENIORITY_SCORE_CEILING
    )

    layer3_invoked = False
    l3 = None
    if layer3_fn is not None and not skip_for_seniority and (borderline or unconventional_dense):
        layer3_invoked = True
        l3 = layer3_fn(raw_job, profile)

    if l3 is not None:
        final = (
            settings.WEIGHT_L1_WITH_L3 * l1.score
            + settings.WEIGHT_L2_WITH_L3 * l2
            + settings.WEIGHT_L3_WITH_L3 * l3.score
        )
        categories = sorted(set(l1.categories) | set(l3.categories))
        experience_fit = l3.experience_fit or l1.experience_fit
        india_eligible = l1.india_eligible or l3.india_eligible
        reasons = l1.reasons + l3.reasons
        layer3_score = l3.score
    else:
        final = combined_l1_l2
        categories = l1.categories
        experience_fit = l1.experience_fit
        india_eligible = l1.india_eligible
        reasons = l1.reasons
        layer3_score = None

    final = max(0.0, min(100.0, final))

    return ScoreResult(
        final=final,
        layer1=l1.score,
        layer2=l2,
        layer3=layer3_score,
        layer3_invoked=layer3_invoked,
        categories=categories,
        experience_fit=experience_fit,
        india_eligible=india_eligible,
        reasons=reasons,
    )
