import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from collectors.base import RawJob
from database.models import Company, Job


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def compute_fallback_key(company_name: str, title: str, location: Optional[str]) -> str:
    raw = f"{_normalize(company_name)}|{_normalize(title)}|{_normalize(location or '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_content_hash(title: str, description: str) -> str:
    raw = f"{_normalize(title)}|{_normalize(description)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Some ATS platforms (notably Greenhouse) don't expose a structured
# employment-type field at all, leaving RawJob.employment_type_raw as None
# for every job. Checked against the TITLE only (not the description, which
# is long/noisy and prone to unrelated false positives, e.g. "intern" as a
# bare substring matching inside "international"/"internal").
_EMPLOYMENT_TYPE_TITLE_PATTERNS = [
    (re.compile(r"\b(?:intern|interns|internship)\b", re.IGNORECASE), "Internship"),
    (re.compile(r"\b(?:contract|contractor)\b", re.IGNORECASE), "Contract"),
    (re.compile(r"\b(?:part-time|part time)\b", re.IGNORECASE), "Part-time"),
    (re.compile(r"\b(?:temporary|temp)\b", re.IGNORECASE), "Temporary"),
]


def infer_employment_type(raw_job: RawJob) -> str:
    if raw_job.employment_type_raw:
        return raw_job.employment_type_raw
    title = raw_job.title or ""
    for pattern, label in _EMPLOYMENT_TYPE_TITLE_PATTERNS:
        if pattern.search(title):
            return label
    return "Full-time"


def get_or_create_company(
    session: Session, name: str, ats_type: str, ats_slug: str, source: str = "manual"
) -> Company:
    existing = (
        session.query(Company)
        .filter_by(ats_type=ats_type, ats_slug=ats_slug)
        .one_or_none()
    )
    if existing:
        return existing

    company = Company(name=name, ats_type=ats_type, ats_slug=ats_slug, source=source)
    session.add(company)
    session.flush()
    return company


@dataclass
class UpsertResult:
    job: Job
    is_new: bool
    content_changed: bool


@dataclass
class JobIndex:
    """In-memory dedup index for one company's jobs, built with a single
    query up front. Passing this to upsert_job avoids 1-2 SELECT round-trips
    per job during a scan — cheap against local SQLite, but the dominant
    cost when scanning against a remote DB (e.g. Supabase)."""

    by_native_id: dict[tuple[str, str], Job]
    by_fallback_key: dict[str, Job]


def build_job_index(session: Session, company_id: str) -> JobIndex:
    jobs = session.query(Job).filter(Job.company_id == company_id).all()
    by_native_id: dict[tuple[str, str], Job] = {}
    by_fallback_key: dict[str, Job] = {}
    for job in jobs:
        if job.ats_job_id:
            by_native_id[(job.ats_type, job.ats_job_id)] = job
        by_fallback_key[job.fallback_key] = job
    return JobIndex(by_native_id=by_native_id, by_fallback_key=by_fallback_key)


def _parse_posted_at(posted_at: Optional[str]) -> Optional[datetime]:
    if not posted_at:
        return None
    try:
        dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def upsert_job(
    session: Session, company: Company, raw_job: RawJob, index: Optional[JobIndex] = None
) -> UpsertResult:
    """Insert a new job or update an existing one, deduping by (ats_type,
    ats_job_id) first and falling back to a normalized company+title+location
    key when the ATS doesn't provide a stable native id.

    Pass `index` (from build_job_index) to dedupe via an in-memory lookup
    instead of per-job queries — strongly recommended for any real scan
    against a remote database. Without it, falls back to per-job queries
    (used by tests and one-off callers where the extra round-trips don't
    matter)."""
    fallback_key = compute_fallback_key(raw_job.company_name, raw_job.title, raw_job.location_raw)
    content_hash = compute_content_hash(raw_job.title, raw_job.description_raw)

    existing: Optional[Job] = None
    if index is not None:
        if raw_job.ats_job_id:
            existing = index.by_native_id.get((raw_job.ats_type, raw_job.ats_job_id))
        if existing is None:
            existing = index.by_fallback_key.get(fallback_key)
    else:
        if raw_job.ats_job_id:
            existing = (
                session.query(Job)
                .filter_by(ats_type=raw_job.ats_type, ats_job_id=raw_job.ats_job_id)
                .one_or_none()
            )
        if existing is None:
            # Deliberately not filtered by ats_type: the same posting can be
            # mirrored across ATS platforms, or a company can migrate ATS
            # providers between scans. fallback_key (normalized company+title+
            # location) is the cross-ATS dedup signal in that case.
            existing = session.query(Job).filter_by(fallback_key=fallback_key).one_or_none()

    if existing is not None:
        content_changed = existing.content_hash != content_hash
        existing.last_seen_at = _now()
        existing.is_active = True
        existing.title = raw_job.title
        existing.location_raw = raw_job.location_raw
        existing.employment_type = infer_employment_type(raw_job)
        existing.description_raw = raw_job.description_raw
        existing.apply_url = raw_job.apply_url
        existing.content_hash = content_hash
        posted_at = _parse_posted_at(raw_job.posted_at)
        if posted_at:
            existing.posted_at = posted_at
        return UpsertResult(job=existing, is_new=False, content_changed=content_changed)

    job = Job(
        company_id=company.id,
        ats_type=raw_job.ats_type,
        ats_job_id=raw_job.ats_job_id,
        fallback_key=fallback_key,
        title=raw_job.title,
        company_name=raw_job.company_name,
        location_raw=raw_job.location_raw,
        employment_type=infer_employment_type(raw_job),
        description_raw=raw_job.description_raw,
        apply_url=raw_job.apply_url,
        posted_at=_parse_posted_at(raw_job.posted_at),
        content_hash=content_hash,
    )
    session.add(job)

    if index is not None:
        # Register immediately so a duplicate later in the same fetch (or a
        # cross-ATS mirror processed in the same scan) still dedupes
        # correctly without needing a DB round-trip.
        if job.ats_job_id:
            index.by_native_id[(job.ats_type, job.ats_job_id)] = job
        index.by_fallback_key[job.fallback_key] = job
    else:
        session.flush()

    return UpsertResult(job=job, is_new=True, content_changed=True)
