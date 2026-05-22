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


settings = Settings()
