import os
from dotenv import load_dotenv

load_dotenv()

# Anchor relative data paths to the backend directory (parent of app/), so file
# storage is deterministic regardless of the working directory uvicorn is
# launched from. Absolute paths from the environment are used as-is.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_dir(value: str) -> str:
    return value if os.path.isabs(value) else os.path.normpath(os.path.join(BASE_DIR, value))


def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    PROJECT_NAME: str = "AI Assessment Service"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/ai_assessment",
    )
    UPLOAD_DIR: str = _resolve_dir(os.getenv("UPLOAD_DIR", "./data/uploads"))
    RECORDING_DIR: str = _resolve_dir(os.getenv("RECORDING_DIR", "./data/recordings"))
    EXPORT_DIR: str = _resolve_dir(os.getenv("EXPORT_DIR", "./data/exports"))

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-a-long-random-string")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    EVIDENCE_PATH_SALT: str = os.getenv("EVIDENCE_PATH_SALT", JWT_SECRET_KEY)

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    OLLAMA_MODEL_BACKUP: str = os.getenv("OLLAMA_MODEL_BACKUP", "qwen2.5:3b")
    OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))
    # Vision model for image evidence description (must support images via Ollama API)
    VISION_MODEL: str = os.getenv("VISION_MODEL", "llava:7b")
    VISION_TIMEOUT_SECONDS: float = float(os.getenv("VISION_TIMEOUT_SECONDS", "180"))

    # Speech-to-text container (on-premise faster-whisper service)
    STT_URL: str = os.getenv("STT_URL", "http://stt:9000")
    STT_TIMEOUT_SECONDS: int = int(os.getenv("STT_TIMEOUT_SECONDS", "600"))

    # Recording retention (GDPR): flag for deletion after this many days,
    # and start reminding the teacher this many days before that date.
    RECORDING_RETENTION_DAYS: int = int(os.getenv("RECORDING_RETENTION_DAYS", "90"))
    RECORDING_REMINDER_LEAD_DAYS: int = int(
        os.getenv("RECORDING_REMINDER_LEAD_DAYS", "14")
    )
    # GDPR extension cap: a recording's expiry may be extended at most this many
    # times, by at most this many days each.
    RECORDING_MAX_EXTENSIONS: int = int(os.getenv("RECORDING_MAX_EXTENSIONS", "2"))
    RECORDING_MAX_EXTENSION_DAYS: int = int(
        os.getenv("RECORDING_MAX_EXTENSION_DAYS", "90")
    )


settings = Settings()
