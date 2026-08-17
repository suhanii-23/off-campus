from types import SimpleNamespace

from notifications.dedup import should_notify


def make_job(**overrides):
    defaults = dict(
        score_final=91.0,
        notified_at=None,
        notified_content_hash=None,
        content_hash="hash-a",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_new_high_score_job_should_notify():
    job = make_job()
    assert should_notify(job, threshold=80, high_recall_mode=False) is True


def test_below_threshold_should_not_notify():
    job = make_job(score_final=75.0)
    assert should_notify(job, threshold=80, high_recall_mode=False) is False


def test_high_recall_mode_lowers_effective_threshold():
    job = make_job(score_final=75.0)
    assert should_notify(job, threshold=80, high_recall_mode=True) is True


def test_already_notified_unchanged_job_should_not_renotify():
    job = make_job(notified_at="2026-08-01T00:00:00Z", notified_content_hash="hash-a", content_hash="hash-a")
    assert should_notify(job, threshold=80, high_recall_mode=False) is False


def test_already_notified_but_content_changed_should_renotify():
    job = make_job(notified_at="2026-08-01T00:00:00Z", notified_content_hash="hash-old", content_hash="hash-new")
    assert should_notify(job, threshold=80, high_recall_mode=False) is True


def test_none_score_should_not_notify():
    job = make_job(score_final=None)
    assert should_notify(job, threshold=80, high_recall_mode=False) is False


def test_defaults_come_from_settings_when_not_passed(mocker):
    mocker.patch("notifications.dedup.settings.MATCH_THRESHOLD", 80)
    mocker.patch("notifications.dedup.settings.HIGH_RECALL_MODE", True)
    mocker.patch("notifications.dedup.settings.HIGH_RECALL_THRESHOLD_REDUCTION", 10)

    job = make_job(score_final=72.0)
    assert should_notify(job) is True
