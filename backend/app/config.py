import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/ai_assessment")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    RECORDING_DIR: str = os.getenv("RECORDING_DIR", "./data/recordings")
    EXPORT_DIR: str = os.getenv("EXPORT_DIR", "./data/exports")


settings = Settings()
