from fastapi import FastAPI
from app.routes.health import router as health_router

app = FastAPI(
    title="AI Assessment Service",
    version="0.1.0"
)

app.include_router(health_router)


@app.get("/")
def root():
    return {
        "message": "AI Assessment Service Running"
    }