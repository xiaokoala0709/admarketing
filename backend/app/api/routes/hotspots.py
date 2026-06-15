from fastapi import APIRouter

from app.schemas.agent import TodayHotspotsResponse
from app.services.agent_adapters import build_today_hotspots

router = APIRouter(prefix="/hotspots", tags=["hotspots"])


@router.get("/today", response_model=TodayHotspotsResponse)
def get_today_hotspots() -> TodayHotspotsResponse:
    return TodayHotspotsResponse(hotspots=build_today_hotspots())
