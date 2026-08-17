"""End-to-end scoring scenarios required by the project spec."""

from types import SimpleNamespace

from database.crud import get_or_create_company, upsert_job
from database.models import Job
from matching.scorer import score_job
from tests.fixtures import mock_jobs


def test_scenario_1_excellent_ai_match(profile):
    result = score_job(mock_jobs.excellent_ai_match(), profile, layer3_fn=None)
    assert result.final >= 80
    assert "AI_ML" in result.categories
    assert result.experience_fit == "Strong"
    assert result.india_eligible is True


def test_scenario_2_excellent_swe_match(profile):
    result = score_job(mock_jobs.excellent_swe_match(), profile, layer3_fn=None)
    assert result.final >= 80
    assert "SOFTWARE" in result.categories or "BACKEND" in result.categories
    assert result.experience_fit == "Strong"


def test_scenario_3_borderline_match_triggers_layer3(profile):
    def fake_layer3(raw_job, prof):
        return SimpleNamespace(
            score=82.0,
            categories=["BACKEND"],
            experience_fit="Strong",
            india_eligible=True,
            reasons=["LLM: role is entry-level friendly despite terse description"],
        )

    without_l3 = score_job(mock_jobs.borderline_match(), profile, layer3_fn=None)
    assert 55 <= without_l3.final <= 79  # confirms this fixture is genuinely borderline

    with_l3 = score_job(mock_jobs.borderline_match(), profile, layer3_fn=fake_layer3)
    assert with_l3.layer3_invoked is True
    assert with_l3.layer3 == 82.0


def test_scenario_4_senior_irrelevant_role_scores_low(profile):
    result = score_job(mock_jobs.senior_irrelevant_role(), profile, layer3_fn=None)
    assert result.layer1 <= 15
    assert result.final < settings_threshold()


def test_scenario_5_duplicate_job_does_not_create_second_row_or_flag_as_new(db_session):
    company = get_or_create_company(db_session, "Acme Corp", "greenhouse", "acme-corp")

    first = upsert_job(db_session, company, mock_jobs.duplicate_job_first_scan())
    db_session.commit()
    assert first.is_new is True

    second = upsert_job(db_session, company, mock_jobs.duplicate_job_second_scan())
    db_session.commit()

    assert second.is_new is False
    assert second.content_changed is False
    assert db_session.query(Job).count() == 1


def test_scenario_6_startup_unconventional_title_still_tagged_ai(profile):
    result = score_job(mock_jobs.startup_unconventional_title(), profile, layer3_fn=None)
    assert "LLM_GENAI" in result.categories or "AI_SOFTWARE" in result.categories


def test_scenario_7_ai_job_without_ml_engineer_title_still_scores_meaningfully(profile):
    result = score_job(mock_jobs.ai_job_no_ml_engineer_title(), profile, layer3_fn=None)
    assert "COMPUTER_VISION" in result.categories or "AI_ML" in result.categories
    assert result.final >= 15  # unconventional title, but real signal should not be near-zero


def test_scenario_8_india_ineligible_remote_job(profile):
    result = score_job(mock_jobs.india_ineligible_remote_job(), profile, layer3_fn=None)
    assert result.india_eligible is False


def settings_threshold() -> float:
    from config import settings

    return float(settings.MATCH_THRESHOLD)
