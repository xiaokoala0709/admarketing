import traceback

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.schemas.agent import (
    AgentListResponse,
    AgentRunRequest,
    AgentRunResponse,
    BrandAssetBriefOutput,
    BrandAssetBriefRequest,
)
from app.services.agent_registry import get_agent, list_agents
from app.services.agent_adapters import build_brand_asset_brief

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse)
def get_agents() -> AgentListResponse:
    return AgentListResponse(agents=list_agents())


@router.post("/{agent_name}/run", response_model=AgentRunResponse)
def run_agent(agent_name: str, payload: AgentRunRequest) -> AgentRunResponse | JSONResponse:
    agent = get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        return agent.run(payload)
    except Exception as exc:
        traceback.print_exc()
        detail = getattr(exc, "detail", str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "agent_run_failed",
                "detail": detail,
                "agent_id": agent_name,
            },
        )


@router.post("/agent_3/brief")
def generate_agent_3_brief(payload: BrandAssetBriefRequest) -> BrandAssetBriefOutput:
    return build_brand_asset_brief(payload)
