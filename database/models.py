import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    ats_type = Column(String, nullable=False)  # "greenhouse" | "lever" | "ashby"
    ats_slug = Column(String, nullable=False)
    source = Column(String, nullable=False, default="manual")  # manual|yc_seed|auto_probe
    is_active = Column(Boolean, default=True, nullable=False)
    last_scanned_at = Column(DateTime(timezone=True), nullable=True)
    last_scan_status = Column(String, nullable=True)  # ok|error|empty
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("ats_type", "ats_slug", name="uq_company_ats"),
        Index("ix_company_active", "is_active"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)

    # Dedup keys
    ats_type = Column(String, nullable=False)
    ats_job_id = Column(String, nullable=True)
    fallback_key = Column(String, nullable=False)

    # Normalized job data
    title = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    location_raw = Column(String, nullable=True)
    is_remote = Column(Boolean, default=False, nullable=False)
    employment_type = Column(String, nullable=True)
    description_raw = Column(Text, nullable=False)
    apply_url = Column(String, nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    # Change detection
    content_hash = Column(String, nullable=False)

    # Scoring outputs
    score_final = Column(Float, nullable=True)
    score_layer1 = Column(Float, nullable=True)
    score_layer2 = Column(Float, nullable=True)
    score_layer3 = Column(Float, nullable=True)
    layer3_invoked = Column(Boolean, default=False, nullable=False)
    layer3_raw_response = Column(JSON, nullable=True)
    categories = Column(JSON, nullable=True)
    experience_fit = Column(String, nullable=True)  # Strong|Moderate|Weak
    india_eligible = Column(Boolean, nullable=True)
    match_reasons = Column(JSON, nullable=True)

    # Notification / application status
    notified_at = Column(DateTime(timezone=True), nullable=True)
    notified_content_hash = Column(String, nullable=True)
    application_status = Column(String, default="new", nullable=False)
    # new|notified|applied|skipped|rejected|interview|offer

    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("ats_type", "ats_job_id", name="uq_job_ats_native"),
        Index("ix_job_fallback_key", "fallback_key"),
        Index("ix_job_score", "score_final"),
        Index("ix_job_company", "company_id"),
        Index("ix_job_active", "is_active"),
    )
