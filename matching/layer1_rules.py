import re
from dataclasses import dataclass, field

from collectors.base import RawJob
from matching.categories import categorize

SENIORITY_HARD_CAP = 15
SENIORITY_RESCUED_CAP = 65
MAX_SKILL_POINTS = 45
POINTS_PER_SKILL = 5
TITLE_MATCH_POINTS = 30
JUNIOR_SIGNAL_BONUS = 20
EXPLICIT_LOW_YEARS_BONUS = 15
MODERATE_YEARS_PENALTY = 5
HIGH_YEARS_PENALTY = 20

_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:-|–|to)?\s*(\d+)?\s*\+?\s*years?", re.IGNORECASE)


@dataclass
class Layer1Result:
    score: float
    categories: list[str]
    experience_fit: str  # Strong | Moderate | Weak
    india_eligible: bool
    seniority_rejected: bool
    matched_skills: list[str]
    title_synonym_hit: bool
    reasons: list[str] = field(default_factory=list)


def _contains_word(haystack: str, needle: str) -> bool:
    # Lookaround on "not a word character" rather than \b: \b requires a
    # word<->non-word transition, which breaks for keywords ending in
    # punctuation (e.g. "sr." followed by a space is non-word -> non-word,
    # so \b never fires there even though "sr." is clearly a whole match).
    pattern = r"(?<!\w)" + re.escape(needle.strip()) + r"(?!\w)"
    return re.search(pattern, haystack) is not None


def _skill_hit(description: str, skill: str, synonyms: list[str]) -> bool:
    candidates = [skill] + synonyms
    lowered = description.lower()
    return any(candidate.lower() in lowered for candidate in candidates)


def _min_years_required(text: str) -> int | None:
    match = _YEARS_RE.search(text)
    if not match:
        return None
    return int(match.group(1))


def score_layer1(raw_job: RawJob, profile: dict) -> Layer1Result:
    title = raw_job.title or ""
    description = raw_job.description_raw or ""
    location = raw_job.location_raw or ""
    title_lower = title.lower()
    combined_lower = f"{title_lower} {description.lower()} {location.lower()}"

    reasons: list[str] = []

    # --- Skill keyword matching ---
    matched_skills = []
    for skill in profile.get("skills", []):
        synonyms = profile.get("skill_synonyms", {}).get(skill, [])
        if _skill_hit(description, skill, synonyms):
            matched_skills.append(skill)
    skill_points = min(MAX_SKILL_POINTS, len(matched_skills) * POINTS_PER_SKILL)
    if matched_skills:
        reasons.append(f"Matched skills: {', '.join(matched_skills[:6])}")

    # --- Title synonym matching ---
    title_synonyms = profile.get("title_synonyms", [])
    title_synonym_hit = any(syn.lower() in title_lower for syn in title_synonyms)
    title_points = TITLE_MATCH_POINTS if title_synonym_hit else 0
    if title_synonym_hit:
        reasons.append("Title matches a known software/AI-ML role pattern")
    elif len(matched_skills) >= 3:
        reasons.append("Unconventional title, but description is skill-dense")

    # --- Experience fit ---
    junior_signals = profile.get("junior_experience_signals", [])
    has_junior_signal = any(sig.lower() in combined_lower for sig in junior_signals)
    min_years = _min_years_required(description)

    experience_bonus = 0
    if has_junior_signal:
        experience_fit = "Strong"
        experience_bonus = JUNIOR_SIGNAL_BONUS
        reasons.append("Entry-level/internship/new-grad signal detected")
    elif min_years is not None:
        if min_years <= 2:
            experience_fit = "Strong"
            experience_bonus = EXPLICIT_LOW_YEARS_BONUS
            reasons.append(f"Requires ~{min_years}+ years — within entry-level range")
        elif min_years <= 4:
            experience_fit = "Moderate"
            experience_bonus = -MODERATE_YEARS_PENALTY
            reasons.append(f"Requires ~{min_years}+ years — slightly above entry-level")
        else:
            experience_fit = "Weak"
            experience_bonus = -HIGH_YEARS_PENALTY
            reasons.append(f"Requires ~{min_years}+ years — likely too senior")
    else:
        experience_fit = "Moderate"

    # --- Seniority exclusion (title only), with rescue from body signals ---
    seniority_exceptions = profile.get("title_seniority_exceptions", [])
    is_exempt_title = any(exc.lower() in title_lower for exc in seniority_exceptions)

    seniority_keywords = profile.get("seniority_exclude_keywords", [])
    seniority_rejected = not is_exempt_title and any(
        _contains_word(title_lower, kw) for kw in seniority_keywords
    )

    rescue_phrases = profile.get("seniority_rescue_phrases", [])
    rescued = seniority_rejected and any(
        phrase.lower() in combined_lower for phrase in rescue_phrases
    )
    if seniority_rejected and not rescued:
        reasons.append("Senior/lead/staff/manager title detected — likely too senior")
    elif seniority_rejected and rescued:
        reasons.append(
            "Senior-sounding title, but entry-level signal in description — kept for review"
        )

    # --- India eligibility ---
    ineligible_signals = profile.get("india_ineligible_signals", [])
    explicit_exclusion = any(sig.lower() in combined_lower for sig in ineligible_signals)
    india_locations = profile.get("locations", [])
    explicit_india_match = any(loc.lower() in combined_lower for loc in india_locations)

    if explicit_exclusion:
        india_eligible = False
        reasons.append("Location text explicitly excludes India-based applicants")
    elif explicit_india_match:
        india_eligible = True
        reasons.append("Location matches an India-based city/region")
    else:
        india_eligible = True
        reasons.append("India eligibility uncertain — no explicit region restriction found")

    # --- Combine into final layer1 score ---
    score = skill_points + title_points + experience_bonus
    score = max(0, min(100, score))

    if seniority_rejected:
        cap = SENIORITY_RESCUED_CAP if rescued else SENIORITY_HARD_CAP
        score = min(score, cap)

    categories = categorize(f"{title} {description}")

    return Layer1Result(
        score=float(score),
        categories=categories,
        experience_fit=experience_fit,
        india_eligible=india_eligible,
        seniority_rejected=seniority_rejected,
        matched_skills=matched_skills,
        title_synonym_hit=title_synonym_hit,
        reasons=reasons,
    )
