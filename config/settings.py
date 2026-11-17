"""Environment-backed settings for INTERVIEWIQ."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "openai/gpt-oss-20b"
GROQ_API_BASE_URL = "https://api.groq.com"


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None
    groq_model: str
    database_path: Path
    groq_request_timeout: float
    groq_max_retries: int

    @classmethod
    def from_env(cls, *, load_env_file: bool = True) -> "Settings":
        if load_env_file:
            load_dotenv(PROJECT_ROOT / ".env")

        model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip()
        if not model:
            model = DEFAULT_MODEL

        raw_database_path = os.getenv(
            "INTERVIEWIQ_DATABASE_PATH", "data/interviewiq.sqlite3"
        ).strip()
        if not raw_database_path:
            raw_database_path = "data/interviewiq.sqlite3"
        database_path = Path(raw_database_path).expanduser()
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path

        try:
            timeout = float(os.getenv("GROQ_REQUEST_TIMEOUT", "45"))
            retries = int(os.getenv("GROQ_MAX_RETRIES", "2"))
        except ValueError as exc:
            raise ValueError(
                "GROQ_REQUEST_TIMEOUT must be a number and "
                "GROQ_MAX_RETRIES must be an integer."
            ) from exc

        if timeout <= 0:
            raise ValueError("GROQ_REQUEST_TIMEOUT must be greater than zero.")
        if retries < 0:
            raise ValueError("GROQ_MAX_RETRIES cannot be negative.")

        api_key = os.getenv("GROQ_API_KEY", "").strip() or None
        return cls(
            groq_api_key=api_key,
            groq_model=model,
            database_path=database_path,
            groq_request_timeout=timeout,
            groq_max_retries=retries,
        )
