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
    OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "1024"))
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

    ASSESSMENT_OLLAMA_MODEL: str = os.getenv("ASSESSMENT_OLLAMA_MODEL", "qwen2.5:7b")
    ASSESSMENT_OLLAMA_MODEL_BACKUP: str = os.getenv(
        "ASSESSMENT_OLLAMA_MODEL_BACKUP", "llama3.1:8b"
    )
    ASSESSMENT_OLLAMA_TIMEOUT_SECONDS: float = float(
        os.getenv("ASSESSMENT_OLLAMA_TIMEOUT_SECONDS", "120")
    )

    VISION_MODEL: str = os.getenv("VISION_MODEL", "llava:7b")
    VISION_TIMEOUT_SECONDS: float = float(os.getenv("VISION_TIMEOUT_SECONDS", "180"))

    MATCH_CONFIDENCE_THRESHOLD: float = float(
        os.getenv("MATCH_CONFIDENCE_THRESHOLD", "0.15")
    )
    MATCH_STRONG_THRESHOLD: float = float(
        os.getenv("MATCH_STRONG_THRESHOLD", "0.30")
    )
    MATCH_CHUNK_SIZE: int = int(os.getenv("MATCH_CHUNK_SIZE", "60"))
    MATCH_CHUNK_OVERLAP: int = int(os.getenv("MATCH_CHUNK_OVERLAP", "15"))
    MATCH_TOP_K: int = int(os.getenv("MATCH_TOP_K", "3"))
    MATCH_USE_AI: bool = _as_bool(os.getenv("MATCH_USE_AI"), True)
    MATCH_CANDIDATE_POOL: int = int(os.getenv("MATCH_CANDIDATE_POOL", "5"))
    MATCH_AI_MODEL: str = os.getenv("MATCH_AI_MODEL", "qwen2.5:3b")
    MATCH_CANDIDATE_POOL_THOROUGH: int = int(
        os.getenv("MATCH_CANDIDATE_POOL_THOROUGH", "8")
    )
    MATCH_AI_MODEL_THOROUGH: str = os.getenv(
        "MATCH_AI_MODEL_THOROUGH", os.getenv("MATCH_AI_MODEL", "qwen2.5:3b")
    )

    GENERATION_RETENTION_DAYS: int = int(
        os.getenv("GENERATION_RETENTION_DAYS", "90")
    )
    GENERATION_REMINDER_LEAD_DAYS: int = int(
        os.getenv("GENERATION_REMINDER_LEAD_DAYS", "14")
    )

    # Speech-to-text container (on-premise faster-whisper service)
    STT_URL: str = os.getenv("STT_URL", "http://stt:9000")
    STT_TIMEOUT_SECONDS: int = int(os.getenv("STT_TIMEOUT_SECONDS", "600"))
    STT_CHUNK_TIMEOUT_SECONDS: float = float(
        os.getenv("STT_CHUNK_TIMEOUT_SECONDS", "10")
    )
    LIVE_SUBTITLE_LANGUAGE: str = os.getenv("LIVE_SUBTITLE_LANGUAGE", "en")

    # Dedicated AI-text classifier (on-premise RoBERTa — not a generic LLM)
    AI_DETECTOR_URL: str = os.getenv("AI_DETECTOR_URL", "http://ai-detector:9001")
    AI_DETECTOR_TIMEOUT_SECONDS: int = int(os.getenv("AI_DETECTOR_TIMEOUT_SECONDS", "120"))
    AI_DETECTOR_MODEL: str = os.getenv("AI_DETECTOR_MODEL", "Hello-SimpleAI/chatgpt-detector-roberta")

    # Recording retention (GDPR): flag for deletion after this many days,
    # and start reminding the teacher this many days before that date.
    RECORDING_RETENTION_DAYS: int = int(os.getenv("RECORDING_RETENTION_DAYS", "90"))
    RECORDING_REMINDER_LEAD_DAYS: int = int(
        os.getenv("RECORDING_REMINDER_LEAD_DAYS", "14")
    )
    RECORDING_MAX_EXTENSIONS: int = int(os.getenv("RECORDING_MAX_EXTENSIONS", "2"))
    RECORDING_MAX_EXTENSION_DAYS: int = int(
        os.getenv("RECORDING_MAX_EXTENSION_DAYS", "90")
    )


settings = Settings()
