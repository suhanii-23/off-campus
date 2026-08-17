"""RawJob fixtures for the 8 required end-to-end scoring scenarios."""

from collectors.base import RawJob


def excellent_ai_match() -> RawJob:
    return RawJob(
        ats_type="greenhouse",
        ats_job_id="scenario-1",
        title="Machine Learning Engineer",
        company_name="Acme AI",
        location_raw="Bengaluru, India",
        description_raw=(
            "Join our AI team building deep learning models with PyTorch, "
            "TensorFlow, and Hugging Face. Work on computer vision with OpenCV "
            "and YOLO, fine-tune LLMs with QLoRA, and deploy with vLLM and "
            "Docker on GCP. 0-2 years of experience welcome, new grad friendly."
        ),
        apply_url="https://example.com/jobs/scenario-1",
    )


def excellent_swe_match() -> RawJob:
    return RawJob(
        ats_type="lever",
        ats_job_id="scenario-2",
        title="Software Development Engineer",
        company_name="Acme Corp",
        location_raw="Bengaluru, India",
        description_raw=(
            "Build backend REST APIs with Python, FastAPI, and Docker, "
            "deployed on GCP with Kubernetes. Work with SQL databases, Git, "
            "and some JavaScript for internal tooling. Entry-level role, "
            "0-2 years experience, new grads welcome."
        ),
        apply_url="https://example.com/jobs/scenario-2",
    )


def borderline_match() -> RawJob:
    return RawJob(
        ats_type="ashby",
        ats_job_id="scenario-3",
        title="Backend Engineer",
        company_name="Acme Startup",
        location_raw="Bengaluru, India",
        description_raw=(
            "Work with Python, SQL databases, FastAPI, and Git on our core "
            "platform."
        ),
        apply_url="https://example.com/jobs/scenario-3",
    )


def senior_irrelevant_role() -> RawJob:
    return RawJob(
        ats_type="greenhouse",
        ats_job_id="scenario-4",
        title="Senior Staff Principal Engineering Manager",
        company_name="Acme Corp",
        location_raw="San Francisco, CA",
        description_raw="15+ years leading org-wide infrastructure initiatives across multiple teams.",
        apply_url="https://example.com/jobs/scenario-4",
    )


def duplicate_job_first_scan() -> RawJob:
    return RawJob(
        ats_type="greenhouse",
        ats_job_id="scenario-5",
        title="Backend Engineer",
        company_name="Acme Corp",
        location_raw="Bengaluru, India",
        description_raw="Build APIs in Python and FastAPI.",
        apply_url="https://example.com/jobs/scenario-5",
    )


def duplicate_job_second_scan() -> RawJob:
    # Same ats_job_id/company, unchanged content -> must dedupe, not re-notify.
    return duplicate_job_first_scan()


def startup_unconventional_title() -> RawJob:
    return RawJob(
        ats_type="greenhouse",
        ats_job_id="scenario-6",
        title="Product Engineer",
        company_name="Tiny AI Startup",
        location_raw="Bengaluru, India",
        description_raw=(
            "Build intelligent applications powered by foundation models. "
            "You'll work on RAG pipelines, vector databases, and LLM "
            "fine-tuning using Hugging Face and PyTorch, deployed with "
            "FastAPI and Kubernetes."
        ),
        apply_url="https://example.com/jobs/scenario-6",
    )


def ai_job_no_ml_engineer_title() -> RawJob:
    return RawJob(
        ats_type="lever",
        ats_job_id="scenario-7",
        title="Founding Engineer",
        company_name="Vision Startup",
        location_raw="Bengaluru, India",
        description_raw=(
            "Build computer vision pipelines using OpenCV, YOLO, and CLIP. "
            "Train and deploy deep learning models with PyTorch and "
            "TensorFlow, served via vLLM."
        ),
        apply_url="https://example.com/jobs/scenario-7",
    )


def india_ineligible_remote_job() -> RawJob:
    return RawJob(
        ats_type="ashby",
        ats_job_id="scenario-8",
        title="Software Engineer",
        company_name="US Only Corp",
        location_raw="Remote",
        description_raw=(
            "Build backend services in Python and FastAPI. Applicants must "
            "be US citizens and authorized to work in the United States."
        ),
        apply_url="https://example.com/jobs/scenario-8",
    )
