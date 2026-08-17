import logging
from datetime import datetime, timezone

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from collectors.base import Collector, CollectorError, RawJob

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lever.co/v0/postings/{slug}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _fetch(slug: str) -> requests.Response:
    return requests.get(BASE_URL.format(slug=slug), params={"mode": "json"}, timeout=10)


def _epoch_ms_to_iso(epoch_ms) -> str | None:
    if not epoch_ms:
        return None
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


class LeverCollector(Collector):
    ats_type = "lever"

    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        try:
            resp = _fetch(company_slug)
        except requests.RequestException as exc:
            raise CollectorError("lever", company_slug, str(exc)) from exc

        if resp.status_code == 404:
            logger.info("lever: %s has no board (404)", company_slug)
            return []
        if resp.status_code != 200:
            raise CollectorError("lever", company_slug, f"unexpected status {resp.status_code}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise CollectorError("lever", company_slug, f"invalid JSON: {exc}") from exc

        jobs = []
        for job in data:
            categories = job.get("categories") or {}
            jobs.append(
                RawJob(
                    ats_type="lever",
                    ats_job_id=job.get("id"),
                    title=(job.get("text") or "").strip(),
                    company_name=company_slug,
                    location_raw=categories.get("location"),
                    description_raw=job.get("descriptionPlain", ""),
                    apply_url=job.get("applyUrl") or job.get("hostedUrl", ""),
                    posted_at=_epoch_ms_to_iso(job.get("createdAt")),
                    employment_type_raw=categories.get("commitment"),
                    raw_payload=job,
                )
            )
        return jobs
