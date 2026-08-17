from datetime import datetime, timezone
from typing import Optional

PRIORITY_TIERS = [(90, "🔥"), (80, "🟢"), (70, "🟡")]


def get_priority_emoji(score: Optional[float]) -> str:
    if score is None:
        return "⚪"
    for threshold, emoji in PRIORITY_TIERS:
        if score >= threshold:
            return emoji
    return "⚪"


def relative_time(dt: Optional[datetime], now: Optional[datetime] = None) -> str:
    """Human-readable relative time. Never fabricates precision the source
    didn't provide — callers should pass None when no timestamp is known,
    which renders as 'unknown'."""
    if dt is None:
        return "unknown"
    if now is None:
        now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    seconds = max(0, (now - dt).total_seconds())
    if seconds < 60:
        return "just now"

    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = int(hours // 24)
    return f"{days} day{'s' if days != 1 else ''} ago"


def format_message(job, now: Optional[datetime] = None) -> str:
    emoji = get_priority_emoji(job.score_final)
    posted_dt = job.posted_at or job.first_seen_at
    posted_relative = relative_time(posted_dt, now=now)

    reasons = list(job.match_reasons or [])[:5]
    reasons_block = "\n".join(f"• {reason}" for reason in reasons) or "• (no reasons recorded)"

    score_display = "?" if job.score_final is None else int(round(job.score_final))

    return (
        "\U0001f6a8 NEW JOB MATCH\n\n"
        f"Company: {job.company_name}\n"
        f"Role: {job.title}\n"
        f"Type: {job.employment_type or 'Unspecified'}\n"
        f"Location: {job.location_raw or 'Unspecified'}\n"
        f"Match: {emoji} {score_display}/100\n"
        f"Posted: {posted_relative}\n\n"
        f"Why it matches:\n{reasons_block}\n\n"
        f"Apply:\n{job.apply_url}"
    )
