from pydantic import BaseModel, Field
from typing import Any, Literal


class AgentInfo(BaseModel):
    name: str
    display_name: str
    description: str


class AgentListResponse(BaseModel):
    agents: list[AgentInfo]


class AgentPromptEntry(BaseModel):
    key: str
    value: str


class AgentStructuredContext(BaseModel):
    role: Literal["brand", "platform"] | None = None
    entries: list[AgentPromptEntry] = Field(default_factory=list)


class CampaignSection(BaseModel):
    title: str
    paragraphs: list[str]
    markdown: str = ""


class CampaignOutput(BaseModel):
    prompt: str = ""
    title: str
    intro: str
    sections: list[CampaignSection]


class HotspotOutput(BaseModel):
    summary: str = ""
    background: str = ""
    emotion: str = ""
    category_opportunity: str = ""
    brand_angle: str = ""
    content_topics: list[str] = Field(default_factory=list)
    action_steps: list[str] = Field(default_factory=list)
    risk_alert: str = ""


class BrandAssetBriefRequest(BaseModel):
    task_type: Literal["kv", "detail", "social"]
    prompt: str = Field(default="", description="Primary prompt for visual brief generation")
    context: str = Field(default="", description="Optional context for the brief generator")


class BrandAssetBriefOutput(BaseModel):
    task_type: Literal["kv", "detail", "social"]
    title: str
    brief: str
    image_prompt: str
    suggestions: list[str] = Field(default_factory=list)


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(default="", description="Image generation prompt")
    product_image: str | None = None
    reference_image: str | None = None
    product_image_name: str | None = None
    reference_image_name: str | None = None
    asset_type: str | None = None
    headline: str | None = None
    promotion_text: str | None = None
    platform_text: str | None = None
    visual_style: str | None = None
    add_text_layer: bool | None = None


class ImageGenerateOutput(BaseModel):
    image_url: str = ""
    image_base64: str = ""
    status: str = "ready"
    message: str = ""


class TodayHotspot(BaseModel):
    id: int
    title: str
    platform: str
    category: str
    tag: str
    date: str
    node_type: Literal[
        "traditional_festival",
        "public_holiday",
        "solar_term",
        "ecommerce_node",
        "international_festival",
        "lifestyle_trend",
    ]
    node_label: str


class TodayHotspotsResponse(BaseModel):
    hotspots: list[TodayHotspot]
    source: str = "simulated"


class AgentRunRequest(BaseModel):
    prompt: str = Field(default="", description="Primary prompt for the agent")
    context: str = Field(default="", description="Optional context for the agent")
    structured_context: AgentStructuredContext | None = None


class AgentRunResponse(BaseModel):
    agent: str
    status: str
    output: str | CampaignOutput | HotspotOutput | BrandAssetBriefOutput | ImageGenerateOutput
    metadata: dict[str, Any] = Field(default_factory=dict)
