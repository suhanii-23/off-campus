import os

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


# --- Secrets / connection info (never log these values) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./jobs.db")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Notification tuning ---
MATCH_THRESHOLD = _env_int("MATCH_THRESHOLD", 80)
HIGH_RECALL_MODE = _env_bool("HIGH_RECALL_MODE", True)
HIGH_RECALL_THRESHOLD_REDUCTION = 10

# --- Scoring pipeline tuning ---
# Weights when only Layer 1 (rules) + Layer 2 (embeddings) ran.
WEIGHT_L1_NO_L3 = 0.6
WEIGHT_L2_NO_L3 = 0.4

# Weights when Layer 3 (LLM) also ran.
WEIGHT_L1_WITH_L3 = 0.4
WEIGHT_L2_WITH_L3 = 0.2
WEIGHT_L3_WITH_L3 = 0.4

# Combined L1+L2 score range that's ambiguous enough to justify an LLM call.
LAYER3_BORDERLINE_LOW = 55
LAYER3_BORDERLINE_HIGH = 79

# Minimum matched skills to treat an unconventional (non-matching) title as
# still worth an LLM look (e.g. "Product Engineer" doing heavy LLM/RAG work).
LAYER3_UNCONVENTIONAL_MIN_SKILLS = 3

# Don't bother calling the LLM on a seniority-rejected role unless something
# else about it (borderline score) suggests it might be mislabeled.
LAYER3_SKIP_SENIORITY_SCORE_CEILING = 40

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
