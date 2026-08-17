"""Semi-automated company discovery: given a company name and a guessed
slug, probe Greenhouse/Lever/Ashby's public APIs to see which (if any) ATS
the company uses, and on a confirmed hit, append it to config/companies.yaml.

This is intentionally NOT a web crawler — it resolves candidates that a
human (or a seed list like config/seed_companies.yaml) already named. See
README "Company discovery" for why this design was chosen over scraping
search engines.

Usage:
    python -m discovery.probe_ats "Company Name" guessed-slug
    python -m discovery.probe_ats --from-seed
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

from collectors.ashby import AshbyCollector
from collectors.base import CollectorError
from collectors.greenhouse import GreenhouseCollector
from collectors.lever import LeverCollector
from discovery.seed_loader import load_unconfirmed_seed_companies

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

COMPANIES_PATH = Path("config/companies.yaml")

PROBE_COLLECTORS = [
    ("greenhouse", GreenhouseCollector()),
    ("lever", LeverCollector()),
    ("ashby", AshbyCollector()),
]

RATE_LIMIT_SECONDS = 1.5


def slug_variants(name: str, guessed_slug: str) -> list[str]:
    variants = {guessed_slug.strip().lower()}
    normalized = name.strip().lower()
    variants.add(normalized.replace(" ", "-"))
    variants.add(normalized.replace(" ", ""))
    variants.add(normalized.replace(" ", "_"))
    return [v for v in variants if v]


def probe_company(name: str, guessed_slug: str) -> tuple[str, str] | None:
    """Try each ATS against each slug variant. Returns (ats_type, slug) on
    the first confirmed hit (200 + non-empty job list), else None."""
    for slug in slug_variants(name, guessed_slug):
        for ats_type, collector in PROBE_COLLECTORS:
            try:
                jobs = collector.fetch_jobs(slug)
            except CollectorError as exc:
                logger.debug("probe %s/%s failed: %s", ats_type, slug, exc)
                continue
            time.sleep(RATE_LIMIT_SECONDS)
            if jobs:
                logger.info("Confirmed: %s -> %s/%s (%d jobs)", name, ats_type, slug, len(jobs))
                return ats_type, slug
    return None


def _load_companies_yaml() -> dict:
    if not COMPANIES_PATH.exists():
        return {"companies": []}
    with open(COMPANIES_PATH) as f:
        return yaml.safe_load(f) or {"companies": []}


def append_company(name: str, ats_type: str, slug: str) -> bool:
    """Append a confirmed company to companies.yaml, skipping if that exact
    (ats_type, slug) is already present. Returns True if appended."""
    data = _load_companies_yaml()
    existing = data.setdefault("companies", [])

    for entry in existing:
        if entry.get("ats_type") == ats_type and entry.get("ats_slug") == slug:
            logger.info("Already present: %s (%s/%s), skipping", name, ats_type, slug)
            return False

    existing.append({"name": name, "ats_type": ats_type, "ats_slug": slug, "source": "auto_probe"})
    with open(COMPANIES_PATH, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    logger.info("Added: %s (%s/%s) to %s", name, ats_type, slug, COMPANIES_PATH)
    return True


def run_single(name: str, guessed_slug: str) -> None:
    hit = probe_company(name, guessed_slug)
    if hit is None:
        logger.info("No ATS match found for %s (guessed slug: %s)", name, guessed_slug)
        return
    ats_type, slug = hit
    append_company(name, ats_type, slug)


def run_from_seed() -> None:
    candidates = load_unconfirmed_seed_companies()
    logger.info("Probing %d seed candidates...", len(candidates))
    for candidate in candidates:
        run_single(candidate["name"], candidate["guessed_slug"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", help="Company name")
    parser.add_argument("guessed_slug", nargs="?", help="Guessed ATS slug")
    parser.add_argument(
        "--from-seed", action="store_true", help="Batch-probe all of config/seed_companies.yaml"
    )
    args = parser.parse_args()

    if args.from_seed:
        run_from_seed()
    elif args.name and args.guessed_slug:
        run_single(args.name, args.guessed_slug)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
