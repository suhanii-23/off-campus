from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from notifications.formatter import format_message, get_priority_emoji


def make_job(**overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        company_name="Acme AI",
        title="Machine Learning Engineer",
        employment_type="Internship",
        location_raw="Bengaluru, India",
        score_final=91.0,
        posted_at=now - timedelta(minutes=42),
        first_seen_at=now - timedelta(minutes=40),
        match_reasons=["Python + ML", "FastAPI", "AI/LLM", "Entry-level eligible"],
        apply_url="https://example.com/jobs/1",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_emoji_tier_boundaries():
    assert get_priority_emoji(100) == "🔥"
    assert get_priority_emoji(90) == "🔥"
    assert get_priority_emoji(89.9) == "🟢"
    assert get_priority_emoji(80) == "🟢"
    assert get_priority_emoji(79.9) == "🟡"
    assert get_priority_emoji(70) == "🟡"
    assert get_priority_emoji(69.9) == "⚪"
    assert get_priority_emoji(None) == "⚪"


def test_message_contains_all_required_fields():
    job = make_job()
    message = format_message(job)

    assert "\U0001f6a8 NEW JOB MATCH" in message
    assert "Company: Acme AI" in message
    assert "Role: Machine Learning Engineer" in message
    assert "Type: Internship" in message
    assert "Location: Bengaluru, India" in message
    assert "Match: 🔥 91/100" in message
    assert "Posted: 42 minute" in message
    assert "Why it matches:" in message
    assert "• Python + ML" in message
    assert "• FastAPI" in message
    assert "Apply:\nhttps://example.com/jobs/1" in message


def test_message_caps_reasons_at_five():
    job = make_job(match_reasons=[f"reason {i}" for i in range(10)])
    message = format_message(job)
    assert message.count("•") == 5


def test_message_handles_missing_optional_fields_gracefully():
    job = make_job(employment_type=None, location_raw=None, match_reasons=[])
    message = format_message(job)
    assert "Type: Unspecified" in message
    assert "Location: Unspecified" in message
    assert "(no reasons recorded)" in message


def test_message_falls_back_to_first_seen_when_no_posted_at():
    job = make_job(posted_at=None)
    message = format_message(job)
    assert "Posted: 40 minute" in message
