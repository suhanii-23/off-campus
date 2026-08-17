from collectors.base import RawJob
from database.crud import build_job_index, get_or_create_company, upsert_job
from database.models import Job


def make_raw_job(**overrides) -> RawJob:
    defaults = dict(
        ats_type="greenhouse",
        ats_job_id="123",
        title="Software Engineer Intern",
        company_name="Acme",
        location_raw="Bengaluru, India",
        description_raw="Build backend services in Python.",
        apply_url="https://boards.greenhouse.io/acme/jobs/123",
        posted_at="2026-08-01T00:00:00Z",
    )
    defaults.update(overrides)
    return RawJob(**defaults)


def test_get_or_create_company_is_idempotent(db_session):
    c1 = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    c2 = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    assert c1.id == c2.id
    assert db_session.query(Job).count() == 0


def test_upsert_job_creates_new_row(db_session):
    company = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    result = upsert_job(db_session, company, make_raw_job())
    db_session.commit()

    assert result.is_new is True
    assert result.content_changed is True
    assert db_session.query(Job).count() == 1


def test_upsert_job_dedupes_by_native_ats_id(db_session):
    company = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    r1 = upsert_job(db_session, company, make_raw_job())
    db_session.commit()

    # Same ats_job_id, re-scanned on a later run — must not create a duplicate row.
    r2 = upsert_job(db_session, company, make_raw_job())
    db_session.commit()

    assert db_session.query(Job).count() == 1
    assert r1.job.id == r2.job.id
    assert r2.is_new is False
    assert r2.content_changed is False  # unchanged description/title


def test_upsert_job_detects_content_change(db_session):
    company = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    upsert_job(db_session, company, make_raw_job())
    db_session.commit()

    changed = upsert_job(
        db_session,
        company,
        make_raw_job(description_raw="Build backend services in Python and Go now."),
    )
    db_session.commit()

    assert changed.is_new is False
    assert changed.content_changed is True
    assert db_session.query(Job).count() == 1


def test_upsert_job_falls_back_to_normalized_key_without_native_id(db_session):
    company = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    r1 = upsert_job(db_session, company, make_raw_job(ats_job_id=None))
    db_session.commit()

    # Same title/company/location, still no native id -> should match via fallback_key.
    r2 = upsert_job(db_session, company, make_raw_job(ats_job_id=None))
    db_session.commit()

    assert db_session.query(Job).count() == 1
    assert r1.job.id == r2.job.id
    assert r2.is_new is False


def test_upsert_job_dedupes_across_ats_types_via_fallback_key(db_session):
    # Simulates a company mirrored on two ATS platforms (or an ATS
    # migration between scans): same company/title/location, no native id,
    # different ats_type. Should still be recognized as the same posting.
    company_gh = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    company_lever = get_or_create_company(db_session, "Acme", "lever", "acme")

    r1 = upsert_job(
        db_session, company_gh, make_raw_job(ats_type="greenhouse", ats_job_id=None)
    )
    db_session.commit()

    r2 = upsert_job(
        db_session, company_lever, make_raw_job(ats_type="lever", ats_job_id=None)
    )
    db_session.commit()

    assert db_session.query(Job).count() == 1
    assert r1.job.id == r2.job.id
    assert r2.is_new is False


def test_upsert_job_different_companies_do_not_collide(db_session):
    acme = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    globex = get_or_create_company(db_session, "Globex", "lever", "globex")

    upsert_job(db_session, acme, make_raw_job(ats_type="greenhouse", ats_job_id="1"))
    upsert_job(
        db_session,
        globex,
        make_raw_job(ats_type="lever", ats_job_id="1", company_name="Globex"),
    )
    db_session.commit()

    assert db_session.query(Job).count() == 2


def test_build_job_index_reflects_existing_jobs(db_session):
    company = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    upsert_job(db_session, company, make_raw_job(ats_job_id="1"))
    upsert_job(db_session, company, make_raw_job(ats_job_id="2", title="Backend Engineer"))
    db_session.commit()

    index = build_job_index(db_session, company.id)

    assert len(index.by_native_id) == 2
    assert ("greenhouse", "1") in index.by_native_id
    assert ("greenhouse", "2") in index.by_native_id
    assert len(index.by_fallback_key) == 2


def test_upsert_job_with_index_dedupes_without_querying(db_session, mocker):
    company = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    upsert_job(db_session, company, make_raw_job(ats_job_id="1"))
    db_session.commit()

    index = build_job_index(db_session, company.id)

    # Spy on session.query to prove the index-based path avoids it entirely
    # for the dedup lookup (the whole point of building the index).
    query_spy = mocker.spy(db_session, "query")
    result = upsert_job(db_session, company, make_raw_job(ats_job_id="1"), index=index)
    db_session.commit()

    assert result.is_new is False
    assert query_spy.call_count == 0
    assert db_session.query(Job).count() == 1


def test_upsert_job_with_index_registers_new_job_for_in_scan_dedup(db_session):
    company = get_or_create_company(db_session, "Acme", "greenhouse", "acme")
    index = build_job_index(db_session, company.id)  # empty index, company has no jobs yet

    # First occurrence within this scan: new job, added to session + index.
    r1 = upsert_job(db_session, company, make_raw_job(ats_job_id="1"), index=index)
    assert r1.is_new is True

    # A duplicate of the same job appearing again later in the same fetch
    # (e.g. a flaky ATS response) must dedupe via the index, not the DB,
    # since it hasn't been committed/flushed yet.
    r2 = upsert_job(db_session, company, make_raw_job(ats_job_id="1"), index=index)
    assert r2.is_new is False
    assert r2.job.id == r1.job.id

    db_session.commit()
    assert db_session.query(Job).count() == 1
