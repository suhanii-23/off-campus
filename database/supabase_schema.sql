-- Reference DDL for a Supabase (Postgres) project.
--
-- You do NOT need to run this by hand: `database.engine.init_db()` (called
-- automatically by main.py on startup) runs `Base.metadata.create_all()`,
-- which creates these same tables from the SQLAlchemy models in
-- database/models.py if they don't already exist. This file is kept as a
-- human-readable reference and for pasting into the Supabase SQL editor if
-- you'd rather create the schema explicitly before running the app.

CREATE TABLE IF NOT EXISTS companies (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    ats_type        TEXT NOT NULL,
    ats_slug        TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'manual',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_scanned_at TIMESTAMPTZ,
    last_scan_status TEXT,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_company_ats UNIQUE (ats_type, ats_slug)
);

CREATE INDEX IF NOT EXISTS ix_company_active ON companies (is_active);

CREATE TABLE IF NOT EXISTS jobs (
    id                      TEXT PRIMARY KEY,
    company_id              TEXT NOT NULL REFERENCES companies (id),

    ats_type                TEXT NOT NULL,
    ats_job_id              TEXT,
    fallback_key            TEXT NOT NULL,

    title                   TEXT NOT NULL,
    company_name            TEXT NOT NULL,
    location_raw            TEXT,
    is_remote               BOOLEAN NOT NULL DEFAULT FALSE,
    employment_type         TEXT,
    description_raw         TEXT NOT NULL,
    apply_url               TEXT NOT NULL,
    posted_at               TIMESTAMPTZ,
    first_seen_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    content_hash            TEXT NOT NULL,

    score_final             DOUBLE PRECISION,
    score_layer1            DOUBLE PRECISION,
    score_layer2            DOUBLE PRECISION,
    score_layer3            DOUBLE PRECISION,
    layer3_invoked          BOOLEAN NOT NULL DEFAULT FALSE,
    layer3_raw_response     JSONB,
    categories              JSONB,
    experience_fit          TEXT,
    india_eligible          BOOLEAN,
    match_reasons           JSONB,

    notified_at             TIMESTAMPTZ,
    notified_content_hash   TEXT,
    application_status      TEXT NOT NULL DEFAULT 'new',

    is_active               BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT uq_job_ats_native UNIQUE (ats_type, ats_job_id)
);

CREATE INDEX IF NOT EXISTS ix_job_fallback_key ON jobs (fallback_key);
CREATE INDEX IF NOT EXISTS ix_job_score ON jobs (score_final);
CREATE INDEX IF NOT EXISTS ix_job_company ON jobs (company_id);
CREATE INDEX IF NOT EXISTS ix_job_active ON jobs (is_active);
