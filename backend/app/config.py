import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "AI Assessment Service"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/ai_assessment",
    )
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    RECORDING_DIR: str = os.getenv("RECORDING_DIR", "./data/recordings")
    EXPORT_DIR: str = os.getenv("EXPORT_DIR", "./data/exports")

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-a-long-random-string")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")


settings = Settings()
