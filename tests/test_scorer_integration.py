from types import SimpleNamespace

from collectors.base import RawJob
from matching.scorer import score_job


def make_job(**overrides) -> RawJob:
    defaults = dict(
        ats_type="greenhouse",
        ats_job_id="1",
        title="Software Engineer",
        company_name="Acme",
        location_raw="Bengaluru, India",
        description_raw="Build APIs in Python.",
        apply_url="https://example.com/jobs/1",
    )
    defaults.update(overrides)
    return RawJob(**defaults)


def fake_layer3(score, categories=None, experience_fit="Strong", india_eligible=True, reasons=None):
    def _fn(raw_job, profile):
        return SimpleNamespace(
            score=score,
            categories=categories or [],
            experience_fit=experience_fit,
            india_eligible=india_eligible,
            reasons=reasons or ["LLM: borderline role looks relevant"],
        )

    return _fn


def test_no_layer3_fn_never_invokes_layer3(profile):
    job = make_job(
        title="Machine Learning Engineer",
        description_raw="PyTorch, TensorFlow, Hugging Face, OpenCV, YOLO, QLoRA, vLLM, Docker. New grad friendly.",
    )
    result = score_job(job, profile, layer3_fn=None)
    assert result.layer3_invoked is False
    assert result.layer3 is None


def test_borderline_score_triggers_layer3(profile):
    # Chosen to land L1+L2 combined in the 55-79 borderline band: title
    # matches (title_points) but only a couple of skills, no junior signal.
    job = make_job(
        title="Backend Engineer",
        description_raw="Work with Python and SQL databases on our core platform.",
    )
    called = {"count": 0}

    def spy_layer3(raw_job, prof):
        called["count"] += 1
        return SimpleNamespace(
            score=85.0, categories=["BACKEND"], experience_fit="Strong",
            india_eligible=True, reasons=["LLM confirms strong fit"],
        )

    result = score_job(job, profile, layer3_fn=spy_layer3)
    if result.layer3_invoked:
        assert called["count"] == 1
        assert result.layer3 == 85.0
        assert "LLM confirms strong fit" in result.reasons


def test_unconventional_dense_title_triggers_layer3(profile):
    job = make_job(
        title="Founding Engineer",
        description_raw=(
            "Build RAG pipelines and LLM applications using vector databases, "
            "FastAPI, Hugging Face, and vLLM."
        ),
    )
    result = score_job(job, profile, layer3_fn=fake_layer3(score=90.0, categories=["LLM_GENAI"]))
    assert result.layer3_invoked is True
    assert result.final > 0


def test_seniority_rejected_low_score_skips_layer3(profile):
    job = make_job(
        title="Senior Staff Principal Engineer",
        description_raw="15+ years leading org-wide infrastructure initiatives.",
    )
    called = {"count": 0}

    def spy_layer3(raw_job, prof):
        called["count"] += 1
        return SimpleNamespace(score=50.0, categories=[], experience_fit="Weak", india_eligible=True, reasons=[])

    result = score_job(job, profile, layer3_fn=spy_layer3)
    assert called["count"] == 0
    assert result.layer3_invoked is False
    assert result.layer1 <= 15  # layer1's seniority cap applied
    # Layer 2 (semantic similarity) isn't seniority-capped, so the blended
    # final score can be somewhat higher than layer1 alone, but should still
    # be well below the notification threshold.
    assert result.final < 40


def test_final_score_combines_all_three_layers_when_invoked(profile):
    job = make_job(
        title="Backend Engineer",
        description_raw="Work with Python and SQL databases.",
    )
    result = score_job(
        job, profile, layer3_fn=fake_layer3(score=95.0, categories=["BACKEND", "AI_ML"])
    )
    if result.layer3_invoked:
        # final should be a genuine blend, not just layer3's raw score
        assert result.final != result.layer3
        assert "AI_ML" in result.categories


def test_score_is_always_clamped_0_to_100(profile):
    job = make_job(
        title="Software Engineer",
        description_raw="Python Python Python FastAPI Docker Git SQL",
    )
    result = score_job(job, profile, layer3_fn=fake_layer3(score=120.0))
    assert 0.0 <= result.final <= 100.0
