import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic
from anthropic import Anthropic
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.agent import (
    AgentInfo,
    AgentPromptEntry,
    AgentRunRequest,
    AgentRunResponse,
    BrandAssetBriefOutput,
    BrandAssetBriefRequest,
    CampaignOutput,
    CampaignSection,
    HotspotOutput,
    TodayHotspot,
)

logger = logging.getLogger(__name__)

AGENT_1_SYSTEM_PROMPT = """你是一名资深品牌内容策略顾问。请基于用户提供的热点信息和品牌背景，输出一个给品牌运营使用的热点工作台结果。

必须严格输出 JSON 对象，格式如下：
{
  "summary": "一句话总结这个热点为什么值得关注",
  "background": "概括热点发生了什么，以及为什么今天值得看",
  "emotion": "概括用户正在被什么情绪驱动",
  "category_opportunity": "说明哪些品类最容易承接这个热点，以及机会点",
  "brand_angle": "给出品牌可进入的话语角度",
  "content_topics": ["选题1", "选题2", "选题3"],
  "action_steps": ["动作1", "动作2", "动作3"],
  "risk_alert": "一句风险提醒"
}

要求：
- 所有字段都必须返回。
- content_topics 返回 3 条，action_steps 返回 3 条。
- 用运营工作台语言，不要写技术说明，不要输出 Markdown，不要附加 JSON 之外的文字。
- 内容必须具体、克制、可执行，不要套话。"""

AGENT_2_SYSTEM_PROMPT = """你是一位给老板写策略初稿的互联网营销负责人，请基于用户输入，输出一份适合互联网/电商/品牌营销岗位使用的节点整合营销方案初稿。

必须使用 Markdown 输出，并严格包含以下结构：
# 策略方案生成结果

## 1. 策略判断
## 2. 用户与场景洞察
## 3. 货盘与品类策略
## 4. 活动机制设计
## 5. 内容与传播打法
## 6. 资源与招商建议
## 7. 执行节奏
## 8. 复盘指标
## 可直接执行清单

内容要求：
- 不要空泛，不要写“提升品牌影响力”这类套话，必须结合用户输入里的平台、节点、预算、品类、目标。
- 每个模块至少 3 条，不超过 6 条。
- 每条尽量使用“动作 + 目的 + 判断依据”的表达方式。
- 整体语气像互联网营销岗写给老板看的策略初稿，不要写成社媒文案。
- 如果用户是平台方，重点写招商、会场、货盘、搜索、站内资源、商家权益、GMV 和用户增长。
- 如果用户是品牌方，重点写品牌定位、卖点转译、内容种草、节点转化、达人合作、电商承接。
- 在“可直接执行清单”中使用 Markdown checkbox（- [ ]）。
- 允许使用加粗、列表和小标题增强可读性，但不要输出 JSON。"""

AGENT_3_BRIEF_SYSTEM_PROMPT = """你是一位资深品牌视觉策划与 AI 图片提示词设计师。请基于用户输入，生成一份适合品牌设计师或 AI 出图工具直接使用的视觉 brief。

你必须严格输出 JSON 对象，格式如下：
{
  "title": "一句适合作为本次素材任务标题的名称",
  "brief": "一段完整的中文视觉 brief，说明画面目标、主体、构图、氛围、文案重点和使用场景",
  "image_prompt": "一段可直接给图片生成模型使用的详细提示词，尽量具体，包含主体、材质、光线、构图、背景、比例、风格",
  "suggestions": ["建议1", "建议2", "建议3"]
}

要求：
- brief 必须是中文，适合品牌团队内部沟通。
- image_prompt 必须具体，不要空泛，不要只写关键词堆砌。
- suggestions 返回 3 条，用于提醒用户优化素材或输入。
- 不要输出 Markdown，不要输出 JSON 之外的任何文字。"""


@dataclass(frozen=True)
class AgentAdapter:
    name: str
    display_name: str
    description: str

    def info(self) -> AgentInfo:
        return AgentInfo(
            name=self.name,
            display_name=self.display_name,
            description=self.description,
        )

    def run(self, payload: AgentRunRequest) -> AgentRunResponse:
        return AgentRunResponse(
            agent=self.name,
            status="ready",
            output=(
                f"{self.display_name} is connected through the FastAPI adapter layer. "
                "Replace this placeholder implementation with the real Python agent."
            ),
            metadata={
                "prompt": payload.prompt,
                "context": payload.context,
                "placeholder": True,
            },
        )


@dataclass(frozen=True)
class ClaudeHotspotAgentAdapter(AgentAdapter):
    def _extract_hotspot_title(self, payload: AgentRunRequest) -> str:
        lines = [line.strip() for line in payload.context.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("- 热点标题："):
                return line.replace("- 热点标题：", "", 1).strip() or "未提供热点标题"
        return "未提供热点标题"

    def _build_user_prompt(self, payload: AgentRunRequest) -> str:
        return (
            "请根据以下热点信息和品牌背景，生成一个适合品牌运营直接阅读的热点工作台内容。\n\n"
            f"【热点信息】\n{payload.context.strip() or '未提供'}\n\n"
            f"【品牌背景 Prompt】\n{payload.prompt.strip() or '未提供'}"
        )

    def _parse_output(self, response: anthropic.types.Message) -> HotspotOutput:
        raw_text = extract_message_text(response)
        if not raw_text:
            raise ValueError("Model returned empty content")

        data = json.loads(raw_text)
        content_topics = data.get("content_topics")
        action_steps = data.get("action_steps")

        return HotspotOutput(
            summary=str(data.get("summary") or "").strip(),
            background=str(data.get("background") or "").strip(),
            emotion=str(data.get("emotion") or "").strip(),
            category_opportunity=str(data.get("category_opportunity") or "").strip(),
            brand_angle=str(data.get("brand_angle") or "").strip(),
            content_topics=[str(item).strip() for item in content_topics[:3]] if isinstance(content_topics, list) else [],
            action_steps=[str(item).strip() for item in action_steps[:3]] if isinstance(action_steps, list) else [],
            risk_alert=str(data.get("risk_alert") or "").strip(),
        )

    def _fallback_output(self, hotspot_title: str) -> HotspotOutput:
        return HotspotOutput(
            summary=f"《{hotspot_title}》适合被当作当天运营选题池中的情绪型热点来处理。",
            background="这个热点本质上不是单一新闻，而是用户围绕某个生活场景持续表达态度与经验，适合品牌借势做轻表达而不是硬转化。",
            emotion="用户此刻更在意被理解、被共鸣，以及内容是否贴近日常生活节奏。",
            category_opportunity="适合生活方式、情绪消费、轻功能型消费与礼赠相关品类承接，重点是把产品放进具体生活场景。",
            brand_angle="品牌更适合从理解用户处境或生活状态切入，而不是直接借热点喊口号。",
            content_topics=[
                "把热点翻译成一个更具体的生活场景选题",
                "围绕用户当下情绪，做一句更克制的品牌表达",
                "用清单型内容承接收藏与转发需求",
            ],
            action_steps=[
                "先用图文卡片快速验证用户是否愿意停留和收藏",
                "再补一条短视频内容，放大最容易引发共鸣的细节",
                "最后把互动评论整理成下一轮内容角度",
            ],
            risk_alert="避免直接套热点口号，重点不是追热度，而是让品牌表达看起来合理且不过度。",
        )

    def run(self, payload: AgentRunRequest) -> AgentRunResponse:
        if not settings.has_anthropic_key:
            raise HTTPException(
                status_code=500,
                detail="ANTHROPIC_API_KEY missing. Please put it in backend/.env",
            )

        hotspot_title = self._extract_hotspot_title(payload)
        logger.info("Agent 1 request started for hotspot: %s", hotspot_title)

        user_prompt = self._build_user_prompt(payload)
        client = create_anthropic_client()

        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1400,
                temperature=0.7,
                system=AGENT_1_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )
            hotspot_output = self._parse_output(response)
            fallback = False
            fallback_reason = None
        except Exception:
            logger.exception("Agent 1 model request failed")
            hotspot_output = self._fallback_output(hotspot_title)
            response = None
            fallback = True
            fallback_reason = "model_call_failed"

        usage = getattr(response, "usage", None) if response is not None else None

        return AgentRunResponse(
            agent=self.name,
            status="completed",
            output=hotspot_output,
            metadata={
                "is_ai_generated": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data_source": "mock_hotspot_list",
                "model": settings.anthropic_model,
                "usage": {
                    "input_tokens": getattr(usage, "input_tokens", 0),
                    "output_tokens": getattr(usage, "output_tokens", 0),
                    "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
                    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
                },
                "fallback": fallback,
                **({"fallback_reason": fallback_reason} if fallback_reason else {}),
            },
        )


def build_today_hotspots() -> list[TodayHotspot]:
    today = datetime.now().strftime("%Y.%m.%d")
    return [
        TodayHotspot(
            id=1,
            title="通勤防晒与轻户外内容持续升温",
            platform="抖音",
            category="服饰 / 防晒用品",
            tag="夏季出行",
            date=today,
            node_type="lifestyle_trend",
            node_label="生活趋势",
        ),
        TodayHotspot(
            id=2,
            title="办公室低负担零食饮料讨论增加",
            platform="小红书",
            category="食品饮料 / 即食轻餐",
            tag="办公室补给",
            date=today,
            node_type="lifestyle_trend",
            node_label="生活趋势",
        ),
        TodayHotspot(
            id=3,
            title="夏季居家清洁与香氛内容关注上升",
            platform="小红书",
            category="家清 / 家居香氛",
            tag="入夏焕新",
            date=today,
            node_type="solar_term",
            node_label="二十四节气",
        ),
        TodayHotspot(
            id=4,
            title="618 囤货清单内容升温，低负担消费表达增加",
            platform="小红书",
            category="美妆 / 食品饮料 / 家清",
            tag="囤货清单",
            date=today,
            node_type="ecommerce_node",
            node_label="电商节点",
        ),
        TodayHotspot(
            id=5,
            title="周末城市短途出逃与轻装备内容走高",
            platform="微信",
            category="旅行 / 户外装备",
            tag="城市短逃",
            date=today,
            node_type="lifestyle_trend",
            node_label="生活趋势",
        ),
    ]


def create_anthropic_client() -> Anthropic:
    return Anthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,
        timeout=180.0,
    )


def extract_message_text(response: anthropic.types.Message) -> str:
    content = getattr(response, "content", "")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_blocks: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                text_blocks.append(text.strip())
                continue

            if isinstance(block, dict):
                dict_text = block.get("text")
                if isinstance(dict_text, str) and dict_text.strip():
                    text_blocks.append(dict_text.strip())
                    continue

                dict_content = block.get("content")
                if isinstance(dict_content, str) and dict_content.strip():
                    text_blocks.append(dict_content.strip())

        return "\n\n".join(text_blocks).strip()

    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        return str(text).strip()

    return str(content or "").strip()


def wrap_markdown_output(prompt: str, markdown_text: str, summary: str) -> CampaignOutput:
    content = markdown_text.strip() or "模型未返回任何文本内容。"
    return CampaignOutput(
        prompt=prompt,
        title="策略方案生成结果",
        intro=summary,
        sections=[
            CampaignSection(
                title="方案正文",
                paragraphs=[content],
                markdown=content,
            )
        ],
    )


def ping_llm() -> dict[str, bool | str]:
    if not settings.has_anthropic_key:
        return {
            "ok": False,
            "error": "missing_api_key",
            "detail": "ANTHROPIC_API_KEY missing. Please put it in backend/.env",
        }

    client = create_anthropic_client()

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": "只回复 OK",
                }
            ],
        )
        reply = extract_message_text(response) or ""
        return {
            "ok": True,
            "model": settings.anthropic_model,
            "base_url": settings.anthropic_base_url,
            "reply": reply,
        }
    except Exception as exc:
        logger.exception("LLM ping failed")
        return {
            "ok": False,
            "error": "llm_ping_failed",
            "detail": str(exc),
        }


def build_brand_asset_brief(payload: BrandAssetBriefRequest) -> BrandAssetBriefOutput:
    prompt = payload.prompt.strip()
    context = payload.context.strip()
    task_label = {
        "kv": "品牌 KV 主视觉",
        "detail": "产品详情页主图",
        "social": "社交媒体海报",
    }[payload.task_type]

    if not settings.has_anthropic_key:
        return BrandAssetBriefOutput(
            task_type=payload.task_type,
            title=f"{task_label}视觉 brief",
            brief=(
                f"为 {task_label} 产出一张适合品牌传播的视觉素材，突出核心卖点、明确主体层级、保留清晰文案区域，"
                "让画面既能承接商业转化，也保留品牌感。"
            ),
            image_prompt=(
                f"Create a polished {task_label} for a consumer brand campaign, with a clear product hero, premium composition, "
                "soft natural lighting, clean background, strong visual hierarchy, editorial commercial aesthetic, high detail, 3:4 aspect ratio."
            ),
            suggestions=[
                "补充更具体的产品主体与卖点，便于画面聚焦。",
                "说明希望保留的文案区域与版式位置。",
                "上传产品图和参考风格图，可提升出图一致性。",
            ],
        )

    user_prompt = (
        f"任务类型：{task_label}\n\n"
        f"【用户输入】\n{prompt or '未提供'}\n\n"
        f"【补充上下文】\n{context or '未提供'}"
    )

    client = create_anthropic_client()

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1200,
            temperature=0.7,
            system=AGENT_3_BRIEF_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )
        raw_text = extract_message_text(response)
        data = json.loads(raw_text)
        suggestions = data.get("suggestions")
        return BrandAssetBriefOutput(
            task_type=payload.task_type,
            title=str(data.get("title") or f"{task_label}视觉 brief").strip(),
            brief=str(data.get("brief") or "").strip(),
            image_prompt=str(data.get("image_prompt") or "").strip(),
            suggestions=[str(item).strip() for item in suggestions[:3]] if isinstance(suggestions, list) else [],
        )
    except Exception:
        logger.exception("Agent 3 brief generation failed")
        return BrandAssetBriefOutput(
            task_type=payload.task_type,
            title=f"{task_label}视觉 brief",
            brief=(
                f"围绕 {task_label} 输出一张品牌素材，优先突出产品主体、核心卖点和明确的画面情绪，"
                "画面构图尽量简洁，确保品牌信息和视觉焦点清晰可读。"
            ),
            image_prompt=(
                f"Create a commercial {task_label} image for a consumer brand, hero product in focus, clean layout, warm editorial lighting, "
                "premium styling, soft background, readable composition, high detail, 3:4 aspect ratio."
            ),
            suggestions=[
                "细化希望强调的单一卖点，避免信息过载。",
                "明确品牌调性，例如克制、明亮、轻盈或高级。",
                "补充使用场景，有助于模型生成更自然的构图。",
            ],
        )


@dataclass(frozen=True)
class ClaudeCampaignAgentAdapter(AgentAdapter):
    def _build_user_prompt(self, payload: AgentRunRequest) -> str:
        entries = payload.structured_context.entries if payload.structured_context else []
        role = payload.structured_context.role if payload.structured_context else None
        role_text = "品牌方" if role == "brand" else "平台方" if role == "platform" else "未指定"
        background_list = "\n".join(
            f"- {entry.key}：{entry.value or '未填写'}" for entry in entries
        )

        focus = (
            "请重点写品牌定位、卖点转译、内容种草、节点转化、达人合作和电商承接。"
            if role == "brand"
            else "请重点写招商、会场、货盘、搜索、站内资源、商家权益、GMV 和用户增长。"
            if role == "platform"
            else "请根据输入信息判断重点，并保持策略视角。"
        )

        return (
            "以下是本次策划的背景信息，请输出一份节点整合营销方案初稿。\n\n"
            f"- 当前角色：{role_text}\n"
            f"{background_list}\n\n"
            f"{focus}"
        )

    def _timeout_output(self, prompt: str) -> CampaignOutput:
        return wrap_markdown_output(
            prompt,
            "# 策略方案生成结果\n\n## 方案正文\n\n模型请求超时，未拿到可解析的返回内容。",
            "模型请求超时，已返回可展示的降级结果。请稍后重试。",
        )

    def _parse_output(self, response: anthropic.types.Message, prompt: str) -> CampaignOutput:
        raw_text = extract_message_text(response)
        logger.info("Agent 2 response preview: %s", raw_text[:500])

        if not raw_text:
            return wrap_markdown_output(
                prompt,
                "# 策略方案生成结果\n\n## 方案正文\n\n模型未返回任何文本内容。",
                "模型未返回内容，已返回空结果说明。",
            )

        return wrap_markdown_output(
            prompt,
            raw_text,
            "已生成策略方案。",
        )

    def run(self, payload: AgentRunRequest) -> AgentRunResponse:
        if not settings.has_anthropic_key:
            raise HTTPException(
                status_code=500,
                detail="ANTHROPIC_API_KEY missing. Please put it in backend/.env",
            )

        user_prompt = self._build_user_prompt(payload)
        client = create_anthropic_client()

        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2400,
                temperature=0.7,
                system=AGENT_2_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )
        except anthropic.APITimeoutError:
            logger.exception("Agent 2 model request timed out")
            return AgentRunResponse(
                agent=self.name,
                status="completed",
                output=self._timeout_output(user_prompt),
                metadata={
                    "model": settings.anthropic_model,
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                    "fallback": True,
                    "fallback_reason": "model_timeout",
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "model_call_failed",
                    "detail": str(exc),
                },
            ) from exc

        try:
            campaign_output = self._parse_output(response, user_prompt)
        except Exception:
            logger.exception("Agent 2 parsing failed")
            campaign_output = wrap_markdown_output(
                user_prompt,
                extract_message_text(response),
                "模型返回解析失败，已以原文形式展示。",
            )

        usage = getattr(response, "usage", None)

        return AgentRunResponse(
            agent=self.name,
            status="completed",
            output=campaign_output,
            metadata={
                "model": settings.anthropic_model,
                "usage": {
                    "input_tokens": getattr(usage, "input_tokens", 0),
                    "output_tokens": getattr(usage, "output_tokens", 0),
                    "cache_creation_input_tokens": getattr(
                        usage,
                        "cache_creation_input_tokens",
                        0,
                    ),
                    "cache_read_input_tokens": getattr(
                        usage,
                        "cache_read_input_tokens",
                        0,
                    ),
                },
            },
        )
