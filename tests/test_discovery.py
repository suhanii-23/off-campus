import yaml

from discovery import probe_ats


def test_slug_variants_includes_guessed_and_normalized_forms():
    variants = probe_ats.slug_variants("Acme AI Corp", "acme")
    assert "acme" in variants
    assert "acme-ai-corp" in variants
    assert "acmeaicorp" in variants


def test_append_company_writes_new_entry(tmp_path, mocker):
    companies_file = tmp_path / "companies.yaml"
    mocker.patch.object(probe_ats, "COMPANIES_PATH", companies_file)

    added = probe_ats.append_company("Acme", "greenhouse", "acme")

    assert added is True
    data = yaml.safe_load(companies_file.read_text())
    assert data["companies"][0]["name"] == "Acme"
    assert data["companies"][0]["ats_type"] == "greenhouse"
    assert data["companies"][0]["source"] == "auto_probe"


def test_append_company_skips_existing_duplicate(tmp_path, mocker):
    companies_file = tmp_path / "companies.yaml"
    companies_file.write_text(
        yaml.safe_dump(
            {"companies": [{"name": "Acme", "ats_type": "greenhouse", "ats_slug": "acme", "source": "manual"}]}
        )
    )
    mocker.patch.object(probe_ats, "COMPANIES_PATH", companies_file)

    added = probe_ats.append_company("Acme", "greenhouse", "acme")

    assert added is False
    data = yaml.safe_load(companies_file.read_text())
    assert len(data["companies"]) == 1


def test_probe_company_returns_first_confirmed_hit(mocker):
    fake_job = mocker.Mock()
    mocker.patch.object(
        probe_ats,
        "PROBE_COLLECTORS",
        [
            ("greenhouse", mocker.Mock(fetch_jobs=mocker.Mock(return_value=[]))),
            ("lever", mocker.Mock(fetch_jobs=mocker.Mock(return_value=[fake_job]))),
            ("ashby", mocker.Mock(fetch_jobs=mocker.Mock(return_value=[fake_job]))),
        ],
    )
    mocker.patch.object(probe_ats.time, "sleep")

    hit = probe_ats.probe_company("Acme", "acme")

    assert hit is not None
    ats_type, slug = hit
    assert ats_type == "lever"


def test_probe_company_returns_none_when_no_ats_matches(mocker):
    mocker.patch.object(
        probe_ats,
        "PROBE_COLLECTORS",
        [
            ("greenhouse", mocker.Mock(fetch_jobs=mocker.Mock(return_value=[]))),
            ("lever", mocker.Mock(fetch_jobs=mocker.Mock(return_value=[]))),
            ("ashby", mocker.Mock(fetch_jobs=mocker.Mock(return_value=[]))),
        ],
    )
    mocker.patch.object(probe_ats.time, "sleep")

    assert probe_ats.probe_company("Acme", "acme") is None
