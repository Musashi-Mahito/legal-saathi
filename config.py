"""Application configuration: environment variables and shared constants.

Every threshold used by the app lives here so that behaviour can be reviewed and
tuned in one place. Nothing in this module may contain legal content.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to ``default``."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    """Read a float environment variable, falling back to ``default``."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# --- Limits -----------------------------------------------------------------
MAX_UPLOAD_MB: int = _get_int("MAX_UPLOAD_MB", 5)
MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1024 * 1024
MAX_MESSAGE_CHARS: int = 2000
MAX_DOC_CHARS: int = 120_000
MAX_PDF_PAGES: int = 30
MAX_SESSIONS: int = 200
SESSION_TTL_SECONDS: int = 2 * 60 * 60
HISTORY_TURNS: int = 10

# --- Document chunking ------------------------------------------------------
LONG_DOC_CHAR_THRESHOLD: int = _get_int("LONG_DOC_CHAR_THRESHOLD", 12_000)
CHUNK_SIZE: int = 3500
CHUNK_OVERLAP: int = 300

# --- Escalation thresholds --------------------------------------------------
LAWYER_ADVISE_DEPOSIT_INR: int = 500_000
LAWYER_ADVISE_REFUND_INR: int = 5_000_000
DEADLINE_URGENT_DAYS: int = 7
REFUND_LIMITATION_MONTHS: int = 24
REFUND_APPROACHING_MONTHS: int = 21

# --- LLM --------------------------------------------------------------------
DEFAULT_PROVIDER_ORDER: tuple[str, ...] = ("groq", "gemini")
LLM_TIMEOUT_SECONDS: float = _get_float("LLM_TIMEOUT_SECONDS", 45.0)
LLM_MAX_RETRIES: int = 2
LLM_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0)
CHUNK_RATE_LIMIT_WAIT_SECONDS: float = 5.0

# --- Flask ------------------------------------------------------------------
FLASK_SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "change-me")
FLASK_HOST: str = os.environ.get("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
FLASK_PORT: int = _get_int("FLASK_PORT", 5000)

# --- Paths ------------------------------------------------------------------
KB_PATH: Path = BASE_DIR / "kb.json"
FAKE_LLM_PATH: Path = BASE_DIR / "tests" / "fixtures" / "fake_llm.json"

# --- Job archive ------------------------------------------------------------
JOBS_DIR: Path = BASE_DIR / "jobs"
JOBS_ENABLED: bool = os.environ.get("JOBS_ARCHIVE", "1").strip().lower() not in {"0", "false", "no"}

# --- Escalation resources (wording only; never invented phone numbers) ------
RESOURCE_DLSA: str = "District Legal Services Authority (DLSA) - free legal aid if eligible"
RESOURCE_CONSUMER_HELPLINE: str = "National Consumer Helpline 1915 (consumer problems)"


@dataclass(frozen=True)
class ProviderConfig:
    """Connection details for one OpenAI-compatible provider."""

    name: str
    api_key: str
    base_url: str
    model: str

    @property
    def usable(self) -> bool:
        """True when the provider has enough configuration to be called."""
        return bool(self.api_key and self.base_url and self.model)


def _provider(name: str) -> ProviderConfig:
    """Build a provider config from ``<NAME>_API_KEY`` style variables."""
    prefix = name.upper()
    return ProviderConfig(
        name=name,
        api_key=os.environ.get(f"{prefix}_API_KEY", "").strip(),
        base_url=os.environ.get(f"{prefix}_BASE_URL", "").strip(),
        model=os.environ.get(f"{prefix}_MODEL", "").strip(),
    )


def provider_order() -> list[str]:
    """Return provider names in the order they should be attempted."""
    raw = os.environ.get("LLM_PROVIDER_ORDER", "")
    names = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return names or list(DEFAULT_PROVIDER_ORDER)


def provider_config(name: str) -> ProviderConfig:
    """Return the configuration for a single provider name."""
    return _provider(name)


def long_doc_provider() -> str:
    """Provider preferred for long documents (may be empty)."""
    return os.environ.get("LONG_DOC_PROVIDER", "").strip().lower()
