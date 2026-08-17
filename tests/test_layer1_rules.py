from collectors.base import RawJob
from matching.layer1_rules import score_layer1


def make_job(**overrides) -> RawJob:
    defaults = dict(
        ats_type="greenhouse",
        ats_job_id="1",
        title="Software Engineer Intern",
        company_name="Acme",
        location_raw="Bengaluru, India",
        description_raw="Build APIs in Python. Entry level, 0-2 years experience welcome.",
        apply_url="https://example.com/jobs/1",
    )
    defaults.update(overrides)
    return RawJob(**defaults)


def test_excellent_ai_match_scores_high(profile):
    job = make_job(
        title="Machine Learning Engineer",
        description_raw=(
            "Join our AI team building deep learning models with PyTorch, "
            "TensorFlow, and Hugging Face. Work on computer vision with OpenCV "
            "and YOLO. Fine-tune LLMs with QLoRA and deploy with vLLM and Docker. "
            "0-2 years of experience welcome, new grad friendly."
        ),
    )
    result = score_layer1(job, profile)
    assert result.score >= 80
    assert "AI_ML" in result.categories
    assert result.seniority_rejected is False
    assert result.experience_fit == "Strong"


def test_excellent_swe_match_scores_high(profile):
    job = make_job(
        title="Software Development Engineer",
        description_raw=(
            "Build backend REST APIs with Python, FastAPI, and Docker, deployed "
            "on GCP with Kubernetes. Work with SQL databases and Git. Entry "
            "level role for new grads."
        ),
    )
    result = score_layer1(job, profile)
    assert result.score >= 80
    assert "SOFTWARE" in result.categories or "BACKEND" in result.categories
    assert result.experience_fit == "Strong"


def test_sr_with_period_before_space_is_caught(profile):
    # Regression: \b-based matching fails on "sr." followed by a space,
    # since "." -> " " is a non-word-to-non-word transition (no \b there).
    job = make_job(
        title="Sr. AI Engineer - Federal Sector",
        description_raw="10+ years leading federal AI deployments.",
    )
    result = score_layer1(job, profile)
    assert result.seniority_rejected is True
    assert result.score <= 15


def test_sr_without_period_is_caught(profile):
    job = make_job(
        title="Sr Software Engineer, Infrastructure",
        description_raw="8+ years of infrastructure engineering experience.",
    )
    result = score_layer1(job, profile)
    assert result.seniority_rejected is True
    assert result.score <= 15


def test_senior_role_is_capped_low(profile):
    job = make_job(
        title="Senior Staff Software Engineer",
        description_raw="10+ years of experience leading large engineering orgs.",
    )
    result = score_layer1(job, profile)
    assert result.seniority_rejected is True
    assert result.score <= 15


def test_senior_title_rescued_by_junior_signal_in_body(profile):
    job = make_job(
        title="Senior Software Engineer",
        description_raw=(
            "This role is part of our new grad program. 0-1 year of experience "
            "expected. Python and FastAPI experience a plus."
        ),
    )
    result = score_layer1(job, profile)
    assert result.seniority_rejected is True
    assert result.score <= 65
    assert result.score > 15  # rescued, not hard-capped


def test_unconventional_title_but_skill_dense_description(profile):
    job = make_job(
        title="Member of Technical Staff",
        description_raw=(
            "Build RAG pipelines and LLM applications using vector databases, "
            "FastAPI, and Hugging Face. Fine-tune models and deploy with vLLM."
        ),
    )
    result = score_layer1(job, profile)
    assert result.title_synonym_hit is False
    assert len(result.matched_skills) >= 3
    assert "LLM_GENAI" in result.categories
    assert result.seniority_rejected is False
    # Layer 1 alone won't fully credit an unconventional title (that's what
    # Layer 3 is for), but skill density should still contribute meaningfully.
    assert result.score >= 15


def test_india_ineligible_remote_role(profile):
    job = make_job(
        title="Software Engineer",
        location_raw="Remote",
        description_raw=(
            "Build backend services in Python. Applicants must be US citizens "
            "and authorized to work in the United States."
        ),
    )
    result = score_layer1(job, profile)
    assert result.india_eligible is False


def test_india_eligibility_defaults_true_when_ambiguous(profile):
    job = make_job(
        title="Software Engineer",
        location_raw="Remote",
        description_raw="Build backend services in Python. Fully remote role.",
    )
    result = score_layer1(job, profile)
    assert result.india_eligible is True
    assert any("uncertain" in r.lower() for r in result.reasons)


def test_high_years_requirement_is_penalized(profile):
    job = make_job(
        title="Software Engineer",
        description_raw="Requires 8+ years of backend engineering experience in Python.",
    )
    result = score_layer1(job, profile)
    assert result.experience_fit == "Weak"
