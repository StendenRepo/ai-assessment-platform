from fastapi import APIRouter
import httpx

from app.config import settings

router = APIRouter()


@router.get("")
def health_check():
    return {"status": "healthy"}


@router.get("/ollama")
async def ollama_health_check():
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "status": "unhealthy",
            "service": "ollama",
            "reachable": False,
            "detail": str(exc),
        }

    data = response.json()
    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
    return {
        "status": "healthy",
        "service": "ollama",
        "reachable": True,
        "base_url": settings.OLLAMA_BASE_URL,
        "model_count": len(models),
        "models": models,
    }
