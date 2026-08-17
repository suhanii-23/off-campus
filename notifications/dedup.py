from config import settings


def should_notify(job, threshold: int = None, high_recall_mode: bool = None) -> bool:
    """Pure decision function: should we send a Telegram alert for this job?

    True only when the score clears the (possibly high-recall-lowered)
    threshold AND the job is either brand new or has materially changed
    since the last notification — never re-notifies an unchanged job seen
    again on a later scan.
    """
    threshold = settings.MATCH_THRESHOLD if threshold is None else threshold
    high_recall_mode = settings.HIGH_RECALL_MODE if high_recall_mode is None else high_recall_mode

    effective_threshold = threshold
    if high_recall_mode:
        effective_threshold = threshold - settings.HIGH_RECALL_THRESHOLD_REDUCTION

    if job.score_final is None or job.score_final < effective_threshold:
        return False

    if job.notified_at is None:
        return True

    return job.notified_content_hash != job.content_hash
