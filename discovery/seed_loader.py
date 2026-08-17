from pathlib import Path

import yaml

CONFIRMED_COMPANIES_PATH = Path("config/companies.yaml")
SEED_COMPANIES_PATH = Path("config/seed_companies.yaml")


def load_confirmed_companies() -> list[dict]:
    """Companies the pipeline actually scans every run: each entry has a
    confirmed ats_type + ats_slug (verified by discovery/probe_ats.py or
    added by hand)."""
    if not CONFIRMED_COMPANIES_PATH.exists():
        return []
    with open(CONFIRMED_COMPANIES_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data.get("companies", [])


def load_unconfirmed_seed_companies() -> list[dict]:
    """Bulk candidate companies (e.g. from a YC-style directory) with a
    guessed slug but no confirmed ATS yet. Not scanned by main.py directly —
    discovery/probe_ats.py resolves these into config/companies.yaml."""
    if not SEED_COMPANIES_PATH.exists():
        return []
    with open(SEED_COMPANIES_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data.get("companies", [])
