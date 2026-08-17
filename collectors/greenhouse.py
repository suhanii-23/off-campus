import logging

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from collectors.base import Collector, CollectorError, RawJob

logger = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _strip_html(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(separator="\n").strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _fetch(slug: str) -> requests.Response:
    return requests.get(BASE_URL.format(slug=slug), params={"content": "true"}, timeout=10)


class GreenhouseCollector(Collector):
    ats_type = "greenhouse"

    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        try:
            resp = _fetch(company_slug)
        except requests.RequestException as exc:
            raise CollectorError("greenhouse", company_slug, str(exc)) from exc

        if resp.status_code == 404:
            logger.info("greenhouse: %s has no board (404)", company_slug)
            return []
        if resp.status_code != 200:
            raise CollectorError(
                "greenhouse", company_slug, f"unexpected status {resp.status_code}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise CollectorError("greenhouse", company_slug, f"invalid JSON: {exc}") from exc

        jobs = []
        for job in data.get("jobs", []):
            location = (job.get("location") or {}).get("name")
            posted_at = job.get("first_published") or job.get("updated_at")
            jobs.append(
                RawJob(
                    ats_type="greenhouse",
                    ats_job_id=str(job.get("id")),
                    title=job.get("title", "").strip(),
                    company_name=job.get("company_name") or company_slug,
                    location_raw=location,
                    description_raw=_strip_html(job.get("content", "")),
                    apply_url=job.get("absolute_url", ""),
                    posted_at=posted_at,
                    raw_payload=job,
                )
            )
        return jobs
