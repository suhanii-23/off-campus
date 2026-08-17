import logging

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from collectors.base import Collector, CollectorError, RawJob

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def _strip_html(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(separator="\n").strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _fetch(slug: str) -> requests.Response:
    return requests.get(BASE_URL.format(slug=slug), timeout=10)


class AshbyCollector(Collector):
    ats_type = "ashby"

    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        try:
            resp = _fetch(company_slug)
        except requests.RequestException as exc:
            raise CollectorError("ashby", company_slug, str(exc)) from exc

        if resp.status_code == 404:
            logger.info("ashby: %s has no board (404)", company_slug)
            return []
        if resp.status_code != 200:
            raise CollectorError("ashby", company_slug, f"unexpected status {resp.status_code}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise CollectorError("ashby", company_slug, f"invalid JSON: {exc}") from exc

        jobs = []
        for job in data.get("jobs", []):
            if not job.get("isListed", True):
                continue

            description = job.get("descriptionPlain") or _strip_html(job.get("descriptionHtml", ""))
            jobs.append(
                RawJob(
                    ats_type="ashby",
                    ats_job_id=job.get("id"),
                    title=(job.get("title") or "").strip(),
                    company_name=company_slug,
                    location_raw=job.get("location"),
                    description_raw=description,
                    apply_url=job.get("applyUrl") or job.get("jobUrl", ""),
                    posted_at=job.get("publishedAt"),
                    employment_type_raw=job.get("employmentType"),
                    raw_payload=job,
                )
            )
        return jobs
