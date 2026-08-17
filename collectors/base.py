from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RawJob:
    ats_type: str
    ats_job_id: Optional[str]
    title: str
    company_name: str
    location_raw: Optional[str]
    description_raw: str
    apply_url: str
    posted_at: Optional[str] = None  # ISO8601 string, normalized downstream
    employment_type_raw: Optional[str] = None
    raw_payload: Optional[dict] = None


class CollectorError(Exception):
    def __init__(self, ats_type: str, company_slug: str, message: str):
        self.ats_type = ats_type
        self.company_slug = company_slug
        super().__init__(f"[{ats_type}:{company_slug}] {message}")


class Collector(ABC):
    ats_type: str

    @abstractmethod
    def fetch_jobs(self, company_slug: str) -> list[RawJob]:
        """Fetch and parse all open jobs for one company.

        Raises CollectorError on unexpected failures. A company that simply
        doesn't use this ATS (e.g. HTTP 404) should return an empty list,
        not raise.
        """
        raise NotImplementedError
