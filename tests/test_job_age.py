from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from notifications.formatter import relative_time


def test_just_now():
    now = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)
    dt = now - timedelta(seconds=10)
    assert relative_time(dt, now=now) == "just now"


def test_minutes_ago():
    now = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)
    dt = now - timedelta(minutes=32)
    assert relative_time(dt, now=now) == "32 minutes ago"


def test_singular_minute():
    now = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)
    dt = now - timedelta(minutes=1)
    assert relative_time(dt, now=now) == "1 minute ago"


def test_hours_ago():
    now = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)
    dt = now - timedelta(hours=3)
    assert relative_time(dt, now=now) == "3 hours ago"


def test_days_ago():
    now = datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)
    dt = now - timedelta(days=2)
    assert relative_time(dt, now=now) == "2 days ago"


def test_none_returns_unknown():
    assert relative_time(None) == "unknown"


@freeze_time("2026-08-16 12:00:00")
def test_uses_real_utcnow_when_now_not_passed():
    dt = datetime(2026, 8, 16, 11, 45, 0, tzinfo=timezone.utc)
    assert relative_time(dt) == "15 minutes ago"
