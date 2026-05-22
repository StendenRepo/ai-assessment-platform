import app.models  # noqa: F401 — registers all models with Base metadata
from app.database import engine, Base

Base.metadata.create_all(bind=engine)
print("All tables created successfully!")