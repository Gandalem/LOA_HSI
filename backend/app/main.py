from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.characters import router as characters_router
from app.api.simulations import router as simulations_router
from app.api.material_prices import router as material_prices_router
from app.api.honing import router as honing_router
from app.api.dataset import router as dataset_router
from app.models.schemas import HealthResponse
from app.core.settings import get_settings
from app.api.material_prices import collect_material_prices, CollectMaterialPricesRequest

app = FastAPI(title="LOA-HSI Character Compare API", version="0.5.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _collect_material_prices_auto(reason: str) -> None:
    settings = get_settings()
    if not settings.auto_collect_material_prices:
        app.state.material_price_auto_status = {"enabled": False, "reason": "disabled"}
        return
    started = datetime.now(timezone.utc).isoformat()
    try:
        response = await asyncio.to_thread(
            collect_material_prices,
            CollectMaterialPricesRequest(
                useConfigFile=True,
                forceRefresh=bool(settings.material_price_startup_force if reason == "startup" else False),
                ttlMinutes=int(settings.material_price_ttl_minutes),
            ),
        )
        app.state.material_price_auto_status = {
            "enabled": True,
            "ok": True,
            "reason": reason,
            "startedAt": started,
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "cacheUsed": bool(response.cacheUsed),
            "message": response.message,
            "items": len(response.items),
        }
    except Exception as exc:
        # API 키가 없거나 로스트아크 API가 잠시 실패해도 서버 자체는 뜨게 둡니다.
        app.state.material_price_auto_status = {
            "enabled": True,
            "ok": False,
            "reason": reason,
            "startedAt": started,
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        }


async def _material_price_scheduler() -> None:
    settings = get_settings()
    interval = int(settings.material_price_refresh_interval_minutes)
    if interval <= 0:
        return
    while True:
        await asyncio.sleep(interval * 60)
        await _collect_material_prices_auto("scheduled")


@app.on_event("startup")
async def startup_tasks() -> None:
    await _collect_material_prices_auto("startup")
    settings = get_settings()
    if settings.auto_collect_material_prices and int(settings.material_price_refresh_interval_minutes) > 0:
        app.state.material_price_scheduler_task = asyncio.create_task(_material_price_scheduler())


@app.on_event("shutdown")
async def shutdown_tasks() -> None:
    task = getattr(app.state, "material_price_scheduler_task", None)
    if task:
        task.cancel()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, service="loa-hsi-character-compare")


app.include_router(characters_router, prefix="/api")
app.include_router(simulations_router, prefix="/api")
app.include_router(material_prices_router, prefix="/api")
app.include_router(honing_router, prefix="/api")
app.include_router(dataset_router, prefix="/api")
