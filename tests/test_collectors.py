import json

import requests

from collectors.ashby import AshbyCollector
from collectors.greenhouse import GreenhouseCollector
from collectors.lever import LeverCollector


class FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def load_fixture(name):
    with open(f"tests/fixtures/{name}") as f:
        return json.load(f)


# ---------- Greenhouse ----------


def test_greenhouse_parses_jobs(mocker):
    fixture = load_fixture("mock_greenhouse_response.json")
    mocker.patch("collectors.greenhouse._fetch", return_value=FakeResponse(200, fixture))

    jobs = GreenhouseCollector().fetch_jobs("acme")

    assert len(jobs) == 3
    intern = jobs[0]
    assert intern.ats_type == "greenhouse"
    assert intern.ats_job_id == "5551001"
    assert intern.title == "Software Engineer Intern - Backend"
    assert intern.location_raw == "Bengaluru, India"
    assert "Python" in intern.description_raw
    assert "<p>" not in intern.description_raw  # HTML stripped
    assert intern.apply_url == "https://boards.greenhouse.io/acme/jobs/5551001"
    assert intern.posted_at == "2026-08-10T09:00:00-07:00"


def test_greenhouse_404_returns_empty_not_error(mocker):
    mocker.patch("collectors.greenhouse._fetch", return_value=FakeResponse(404, {}))
    jobs = GreenhouseCollector().fetch_jobs("no-such-company")
    assert jobs == []


def test_greenhouse_retries_on_timeout_then_raises_collector_error(mocker):
    from collectors.base import CollectorError

    # Patch requests.get (not _fetch) so the tenacity retry wrapping _fetch
    # actually runs and we can verify it attempts 3 times before giving up.
    mock_get = mocker.patch("collectors.greenhouse.requests.get", side_effect=requests.Timeout("timed out"))

    try:
        GreenhouseCollector().fetch_jobs("acme")
        assert False, "expected CollectorError"
    except CollectorError:
        pass

    assert mock_get.call_count == 3


def test_greenhouse_raises_collector_error_on_5xx(mocker):
    from collectors.base import CollectorError

    mocker.patch("collectors.greenhouse._fetch", return_value=FakeResponse(500, {}))
    try:
        GreenhouseCollector().fetch_jobs("acme")
        assert False, "expected CollectorError"
    except CollectorError:
        pass


# ---------- Lever ----------


def test_lever_parses_jobs(mocker):
    fixture = load_fixture("mock_lever_response.json")
    mocker.patch("collectors.lever._fetch", return_value=FakeResponse(200, fixture))

    jobs = LeverCollector().fetch_jobs("globex")

    assert len(jobs) == 2
    ml_job = jobs[0]
    assert ml_job.ats_type == "lever"
    assert ml_job.title == "Machine Learning Engineer, Computer Vision"
    assert ml_job.location_raw == "Bengaluru, India"
    assert ml_job.employment_type_raw == "Full-time"
    assert "PyTorch" in ml_job.description_raw
    assert ml_job.posted_at is not None
    assert ml_job.apply_url.endswith("/apply")


def test_lever_404_returns_empty(mocker):
    mocker.patch("collectors.lever._fetch", return_value=FakeResponse(404, {}))
    jobs = LeverCollector().fetch_jobs("no-such-company")
    assert jobs == []


# ---------- Ashby ----------


def test_ashby_parses_jobs_and_filters_unlisted(mocker):
    fixture = load_fixture("mock_ashby_response.json")
    mocker.patch("collectors.ashby._fetch", return_value=FakeResponse(200, fixture))

    jobs = AshbyCollector().fetch_jobs("initech")

    # Only the isListed=true job should come through.
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "New Grad Software Engineer"
    assert job.location_raw == "Bengaluru, India"
    assert "Kubernetes" in job.description_raw
    assert job.employment_type_raw == "FullTime"


def test_ashby_404_returns_empty(mocker):
    mocker.patch("collectors.ashby._fetch", return_value=FakeResponse(404, {}))
    jobs = AshbyCollector().fetch_jobs("no-such-company")
    assert jobs == []
