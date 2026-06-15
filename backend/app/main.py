from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.api.routes.agents import router as agents_router
from app.api.routes.hotspots import router as hotspots_router
from app.api.routes.images import router as images_router
from app.core.config import settings
from app.services.agent_adapters import ping_llm

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, bool | str]:
    return {
        "ok": True,
        "has_anthropic_key": settings.has_anthropic_key,
        "anthropic_base_url": settings.anthropic_base_url,
        "anthropic_model": settings.anthropic_model,
    }


@app.get(f"{settings.api_prefix}/debug/llm-ping")
def llm_ping() -> dict[str, bool | str]:
    return ping_llm()


app.include_router(agents_router, prefix=settings.api_prefix)
app.include_router(hotspots_router, prefix=settings.api_prefix)
app.include_router(images_router, prefix=settings.api_prefix)
