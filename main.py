import logging
import time
from datetime import datetime, timezone

import yaml

from collectors.ashby import AshbyCollector
from collectors.base import CollectorError
from collectors.greenhouse import GreenhouseCollector
from collectors.lever import LeverCollector
from config import settings
from database.crud import build_job_index, get_or_create_company, upsert_job
from database.engine import get_session, init_db
from database.models import Job
from discovery.seed_loader import load_confirmed_companies
from matching.layer3_llm import make_cached_layer3_fn
from matching.scorer import score_job
from notifications.dedup import should_notify
from notifications.formatter import format_message
from notifications.telegram import send_telegram_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("main")

# Commit (and SAVEPOINT) in batches rather than per job. Doing either per-job
# is fine against local SQLite but turns into thousands of individual
# network round-trips against a remote Postgres (Supabase) — the dominant
# cost once company/job counts grow. A batch is wrapped in one SAVEPOINT; if
# something in it throws, we fall back to replaying that batch job-by-job
# (each in its own SAVEPOINT) so a single bad job can't lose its neighbors'
# progress — that granularity just isn't paid for on the (common) happy path.
BATCH_SIZE = 50

COLLECTORS = {
    "greenhouse": GreenhouseCollector(),
    "lever": LeverCollector(),
    "ashby": AshbyCollector(),
}


def load_profile(path: str = "config/profile.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _process_one_job(session, company, raw_job, profile: dict, name: str, index, touched_job_ids: set) -> None:
    raw_job.company_name = name  # prefer the confirmed display name over the slug fallback
    result = upsert_job(session, company, raw_job, index=index)
    touched_job_ids.add(result.job.id)

    if result.is_new or result.content_changed:
        layer3_fn = make_cached_layer3_fn(existing_job=result.job) if settings.ANTHROPIC_API_KEY else None
        score = score_job(raw_job, profile, layer3_fn=layer3_fn)

        result.job.score_final = score.final
        result.job.score_layer1 = score.layer1
        result.job.score_layer2 = score.layer2
        result.job.score_layer3 = score.layer3
        result.job.layer3_invoked = score.layer3_invoked
        result.job.categories = score.categories
        result.job.experience_fit = score.experience_fit
        result.job.india_eligible = score.india_eligible
        result.job.match_reasons = score.reasons

    if should_notify(result.job):
        message = format_message(result.job)
        sent = send_telegram_message(message)
        if sent:
            result.job.notified_at = _now()
            result.job.notified_content_hash = result.job.content_hash
            if result.job.application_status == "new":
                result.job.application_status = "notified"
            logger.info("Notified: %s @ %s (score=%.0f)", result.job.title, name, result.job.score_final)


def process_company(session, company_config: dict, profile: dict) -> None:
    name = company_config["name"]
    ats_type = company_config["ats_type"]
    slug = company_config["ats_slug"]

    collector = COLLECTORS.get(ats_type)
    if collector is None:
        logger.error("No collector registered for ats_type=%s (company=%s)", ats_type, name)
        return

    company = get_or_create_company(session, name, ats_type, slug, source=company_config.get("source", "manual"))

    try:
        raw_jobs = collector.fetch_jobs(slug)
    except CollectorError as exc:
        logger.warning("Collector error for %s (%s/%s): %s", name, ats_type, slug, exc)
        company.last_scan_status = "error"
        company.last_error = str(exc)
        company.last_scanned_at = _now()
        session.commit()
        return
    except Exception as exc:  # noqa: BLE001 - one company must never kill the run
        logger.exception("Unexpected error scanning %s (%s/%s)", name, ats_type, slug)
        company.last_scan_status = "error"
        company.last_error = str(exc)
        company.last_scanned_at = _now()
        session.commit()
        return

    logger.info("%s (%s/%s): fetched %d jobs", name, ats_type, slug, len(raw_jobs))

    # Bulk-fetch this company's existing jobs once instead of querying per
    # job — the single biggest lever for scan speed against a remote DB.
    index = build_job_index(session, company.id)
    touched_job_ids: set[str] = set()

    for batch_start in range(0, len(raw_jobs), BATCH_SIZE):
        batch = raw_jobs[batch_start : batch_start + BATCH_SIZE]
        try:
            with session.begin_nested():  # one SAVEPOINT for the whole batch
                for raw_job in batch:
                    _process_one_job(session, company, raw_job, profile, name, index, touched_job_ids)
        except Exception:  # noqa: BLE001 - fall back to isolating the bad job within this batch
            logger.warning(
                "Batch of %d jobs from %s failed together, retrying one at a time", len(batch), name
            )
            for raw_job in batch:
                try:
                    with session.begin_nested():
                        _process_one_job(session, company, raw_job, profile, name, index, touched_job_ids)
                except Exception:  # noqa: BLE001 - one bad job must never kill the run
                    logger.exception("Failed to process job %r from %s", raw_job.title, name)

        session.commit()

    # Jobs previously seen for this company but absent from this scan are
    # presumed closed/filled.
    stale_query = session.query(Job).filter(Job.company_id == company.id, Job.is_active.is_(True))
    if touched_job_ids:
        stale_query = stale_query.filter(~Job.id.in_(touched_job_ids))
    for job in stale_query.all():
        job.is_active = False

    company.last_scan_status = "ok" if raw_jobs else "empty"
    company.last_error = None
    company.last_scanned_at = _now()
    session.commit()


def run() -> None:
    init_db()
    profile = load_profile()
    companies = load_confirmed_companies()

    if not companies:
        logger.warning("No confirmed companies in config/companies.yaml — nothing to scan.")
        return

    logger.info(
        "Starting scan: %d companies, MATCH_THRESHOLD=%s, HIGH_RECALL_MODE=%s",
        len(companies),
        settings.MATCH_THRESHOLD,
        settings.HIGH_RECALL_MODE,
    )

    session = get_session()
    try:
        for i, company_config in enumerate(companies):
            process_company(session, company_config, profile)
            if i < len(companies) - 1:
                time.sleep(1)  # be a good citizen against these public ATS APIs
    finally:
        session.close()

    logger.info("Scan complete.")


if __name__ == "__main__":
    run()
