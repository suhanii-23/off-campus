# Job Hunter

An automated job discovery and Telegram notification system for AI/ML and
Software Engineering internships and entry-level/new-grad roles, tuned for
a final-year student targeting India-based and India-eligible-remote
positions. It polls company job boards, scores every posting against a
skill profile using a 3-layer matching pipeline, and pushes a Telegram
alert as soon as a genuinely new, relevant job appears.

**Design priority: recall over precision.** It would rather surface 20
jobs and have you skip 5 than silently miss one great one.

## 1. Architecture

```
off-campus/
├── main.py                # orchestrates: discover -> collect -> dedupe/persist -> score -> notify
├── collectors/             # one module per ATS (Greenhouse, Lever, Ashby)
├── discovery/               # company seed loading + semi-automated ATS auto-probe
├── matching/                 # 3-layer scoring pipeline (rules, embeddings, LLM)
├── notifications/             # Telegram message formatting + dedup logic
├── database/                   # SQLAlchemy models, SQLite/Postgres engine, CRUD/dedup
├── dashboard/                   # Streamlit review UI
├── config/                       # profile.yaml, companies.yaml, settings.py — edit, don't code
├── tests/                         # pytest suite, mocked fixtures
└── .github/workflows/              # scheduled pipeline + CI test runs
```

**Data flow:** `config/companies.yaml` lists companies with a confirmed ATS.
For each, the matching `Collector` fetches current job postings, `database/crud.py`
deduplicates against what's already stored (by native ATS job ID, falling
back to a normalized company+title+location key), and any new-or-changed
job goes through `matching/scorer.py`:

1. **Layer 1 (rules)** — always runs, no external calls. Keyword/title/skill
   matching against `config/profile.yaml`, seniority detection, experience-year
   extraction, India-eligibility heuristics, multi-label categorization.
2. **Layer 2 (embeddings)** — local `sentence-transformers` model, cosine
   similarity between the job description and your profile blurb. Free, no
   API key, runs for every job.
3. **Layer 3 (LLM)** — Anthropic API, called *only* for borderline scores
   (55–79 combined) or "unconventional title but skill-dense description"
   cases (e.g. a "Product Engineer" role that's actually heavy LLM/RAG
   work). Results are cached in the database by content hash, so an
   unchanged posting never re-hits the API on a later scan.

Jobs that clear the notification threshold (and haven't already been
notified for their current content) get formatted and sent to Telegram.

## 2. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in the values below
```

### Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | No locally / **Yes in CI** | Postgres connection string (Supabase). Unset locally → SQLite at `./jobs.db`. |
| `ANTHROPIC_API_KEY` | No | Enables Layer 3 LLM matching. Without it, scoring still works via Layers 1+2 only. |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | No | Without these, the pipeline runs and scores jobs but skips sending notifications (logs a warning instead). |
| `MATCH_THRESHOLD` | No (default `80`) | Minimum score to notify. |
| `HIGH_RECALL_MODE` | No (default `true`) | Lowers the effective notification threshold by 10 and keeps borderline/unconventional-title roles. |

### Telegram bot setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`, and copy the token it gives you into `TELEGRAM_BOT_TOKEN`.
2. Send your new bot any message (e.g. "hi") so it can see your chat.
3. Visit `https://api.telegram.org/bot<your-token>/getUpdates` in a browser and find `"chat":{"id": ...}` in the response — that's `TELEGRAM_CHAT_ID`.

### Database setup (Supabase)

1. Create a free project at [supabase.com](https://supabase.com).
2. Grab the Postgres connection string from Project Settings → Database (use the "connection pooling" string for serverless-style short-lived connections), and set it as `DATABASE_URL` (form: `postgresql+psycopg2://user:password@host:port/postgres`).
3. Tables are created automatically on first run (`database/engine.init_db()`, called from `main.py`). `database/supabase_schema.sql` is a hand-written reference copy of the same schema if you'd rather run it manually in the Supabase SQL editor.
4. **Locally you can skip this entirely** — leaving `DATABASE_URL` unset uses a local SQLite file. You only need Supabase for GitHub Actions, since Actions runners are ephemeral and a SQLite file wouldn't survive between scheduled runs (which would break deduplication and re-notify every job as "new" every single run).

## 3. Local testing

```bash
pytest                 # fast suite (~13s), excludes the real-embedding-model test
pytest -m slow          # includes the one test that downloads/runs the real sentence-transformers model
pytest -q               # quiet output
```

69 tests across collectors, layer 1 rules, layer 2 embeddings, layer 3 LLM
(mocked), the scorer, dedup, notification formatting/dedup, job-age, and
8 required end-to-end scenarios (excellent AI match, excellent SWE match,
borderline match, senior/irrelevant role, duplicate job, unconventional-title
startup job, AI job without "ML Engineer" in the title, India-ineligible
remote job).

Run the pipeline against real companies locally:

```bash
python main.py
```

This scans whatever's in `config/companies.yaml` (seeded with 4 verified
real companies — Stripe, Rigetti, Ramp, Notion — across all 3 supported
ATS types) and writes to `./jobs.db`.

Review results:

```bash
streamlit run dashboard/app.py
```

## 4. Deployment (GitHub Actions)

1. Push this repo to GitHub.
2. Add repo secrets (Settings → Secrets and variables → Actions): `DATABASE_URL`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. `.github/workflows/pipeline.yml` runs on a `0 */6 * * *` cron (every 6 hours) and on manual `workflow_dispatch`. Trigger it manually first ("Actions" tab → "job-hunter-pipeline" → "Run workflow") to confirm secrets are wired correctly before relying on the schedule.
4. `.github/workflows/tests.yml` runs the fast test suite on every push/PR — no secrets needed (uses the SQLite default and in-memory fixtures).

**GitHub Actions cron is best-effort, not exact.** Actions documents that
scheduled runs can be delayed under high platform load — sometimes by many
minutes. If you need tighter near-real-time detection than a 6-hour cron
(with best-effort timing) can offer, the pipeline is a plain Python script
with no GH-Actions-specific code, so it can be redeployed as-is behind a
different scheduler — Cloud Run + Cloud Scheduler, AWS Lambda + EventBridge,
or a Railway/Render cron job — all of which give tighter timing guarantees.
This isn't implemented in v1; wiring it up is a matter of choosing one and
pointing its scheduler at `python main.py` with the same environment variables.

## 5. How to add a company

**Option A — you already know the ATS:** edit `config/companies.yaml` directly:

```yaml
  - name: "Some Startup"
    ats_type: "greenhouse"   # or "lever" / "ashby"
    ats_slug: "some-startup"
    source: "manual"
```

**Option B — you don't know the ATS:** let the auto-probe find it:

```bash
python -m discovery.probe_ats "Some Startup" some-startup
```

This tries Greenhouse, Lever, and Ashby against a few slug variants of the
name, and on a confirmed hit (a 200 response with at least one listed job)
appends the entry to `config/companies.yaml` automatically.

**Bulk candidates:** add `{name, guessed_slug}` pairs to
`config/seed_companies.yaml`, then run:

```bash
python -m discovery.probe_ats --from-seed
```

to probe all of them in one pass (rate-limited to be a good citizen against
these public APIs).

## 6. How to add a new ATS collector

Implement the `Collector` interface in `collectors/base.py`:

```python
class Collector(ABC):
    ats_type: str
    @abstractmethod
    def fetch_jobs(self, company_slug: str) -> list[RawJob]: ...
```

Look at `collectors/greenhouse.py`, `collectors/lever.py`, or
`collectors/ashby.py` for the pattern: fetch via `requests` wrapped in a
`tenacity` retry, treat a 404 as "this company doesn't use this ATS"
(return `[]`, don't raise), and map the ATS's native JSON fields onto
`RawJob`. Register it in `main.py`'s `COLLECTORS` dict. Workday,
SmartRecruiters, Teamtailor, and Recruitee all have similarly-shaped public
board APIs and would follow the same pattern — none are implemented yet
(see Limitations).

## 7. How to modify your profile

Everything in `config/profile.yaml` — skills, skill synonyms, title
synonyms, seniority-exclusion keywords, locations, India-ineligibility
signals — is plain data. Edit it and re-run; no code changes needed. Don't
add skills/experience that aren't real — the scorer trusts this file as
ground truth about you.

## 8. How to change the match threshold

Set `MATCH_THRESHOLD` (default `80`) and/or `HIGH_RECALL_MODE` (default
`true`, which lowers the effective threshold by 10) in `.env` locally or as
a GitHub Actions secret/env var. No code changes needed.

## 9. Known limitations

Please read this section honestly rather than assuming full coverage —
the system optimizes hard for recall and early detection, but it cannot
guarantee finding every relevant job on the internet.

- **ATS coverage**: only Greenhouse, Lever, and Ashby are implemented.
  Workday, SmartRecruiters, Teamtailor, Recruitee, and custom career-page
  scrapers are not — a company using one of those simply won't be scanned
  even if listed in `companies.yaml` with a matching guess. The `Collector`
  interface is designed for these to be added later without touching core
  logic (see §6).
- **Company discovery is semi-automated, not a crawler.** `probe_ats.py`
  confirms a *guessed* company name/slug against known ATS APIs — it does
  not independently discover new companies from the open web. Coverage is
  bounded by what's in `companies.yaml`/`seed_companies.yaml`, which needs
  ongoing manual curation (or periodic import from a YC-style public
  directory) to stay fresh. This was a deliberate scope decision to avoid
  scraping search engines without an API (see the design discussion this
  repo was built from).
- **Greenhouse's posted date is a best-effort proxy.** Its job-list endpoint
  doesn't reliably expose a true "first posted" timestamp in all cases;
  `first_published` is used when present, falling back to `updated_at`.
  Lever and Ashby provide more reliable native timestamps.
- **India eligibility for ambiguous remote postings defaults to
  eligible/uncertain**, not excluded — a deliberate recall-biased choice.
  It only flips to ineligible on an explicit signal ("must be US-based",
  "authorized to work in the United States", etc.). This means some
  genuinely US-only remote roles may still surface; check the "Why it
  matches" reasons, which note when eligibility was uncertain.
- **Layer 2 truncates long job descriptions** (~1500 characters) to fit the
  embedding model's context window — very long postings are scored on their
  first portion only.
- **Layer 3 LLM calls are best-effort.** A failed/timed-out Anthropic call
  logs a warning and the job falls back to the Layer 1+2 combined score
  rather than blocking the run.
- **GitHub Actions cron timing is not exact** (see §4) — treat the 6-hour
  schedule as approximate, not a real-time guarantee.
- **`probe_ats.py` rewrites `companies.yaml` programmatically** when it
  appends a new company, which does not preserve hand-written comments
  below the `companies:` key (a `pyyaml` limitation, not a bug).
- **The "unlisted"/closed-job detection** (marking a `Job` row `is_active =
  False` when it disappears from a company's current listing) only runs
  for companies actually present in `companies.yaml` at scan time — a
  company removed from that file won't have its old jobs' status updated.
- **Notification status is tracked as columns on `Job`** (`notified_at`,
  `notified_content_hash`), not a separate audit-log table — sufficient for
  "don't re-notify," but doesn't retain a full history of every notification
  attempt if you need that later.

## 10. Test results

```
69 passed, 1 deselected (the real-embedding-model integration test, run separately via `pytest -m slow`)
```

Verified against real, live data during development (not just fixtures):
all three collectors were run against real company job boards (Stripe on
Greenhouse — 578 jobs, Rigetti on Lever — 13 jobs, Ramp on Ashby — 136
jobs), the full `main.py` pipeline was run twice back-to-back to confirm
zero duplicate rows and correct dedup on the second pass, `probe_ats.py`
was run against a real company (Notion) and correctly identified and
recorded its Ashby board, and the Streamlit dashboard was loaded in a
browser against the resulting database and confirmed to filter correctly
(e.g. an AI_ML category filter correctly narrowed 593 jobs to 26, all
genuinely AI/ML-tagged).
