from fastapi import APIRouter

from app.schemas.agent import TodayHotspotsResponse
from app.services.hotspot_source import get_today_hotspots_response, refresh_today_hotspots

router = APIRouter(prefix="/hotspots", tags=["hotspots"])


@router.get("/today", response_model=TodayHotspotsResponse)
def get_today_hotspots() -> TodayHotspotsResponse:
    return get_today_hotspots_response()


@router.post("/refresh", response_model=TodayHotspotsResponse)
def refresh_hotspots() -> TodayHotspotsResponse:
    """Manually triggered by the "更新今日热点" button on the frontend."""
    return refresh_today_hotspots()
