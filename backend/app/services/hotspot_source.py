"""Real (manually-triggered) today's-hotspot fetching.

This module powers the "更新" button. It does NOT run automatically on
every page load — a real refresh is only triggered when the user
explicitly calls POST /api/hotspots/refresh, so it stays cheap and doesn't
depend on any always-on scraper process.

Two independent kinds of hotspot candidates, combined into one list
--------------------------------------------------------------------
1. "运营日历" priority nodes — 二十四节气 / 法定节假日 / 中国传统节日 / 国际节日 /
   电商节点 / 开学季 (see marketing_calendar.py, pure date math, no network)
   plus 展会信息 / 影视上映 / 春秋假 (dynamic, looked up via Claude's
   web-search tool since there's no fixed, nationally-consistent date for
   these — 春秋假 in particular is a 2025-2026 policy still being rolled
   out province by province, no single national date). Per the brand's
   request, when today is near one of these, it should be prioritized as
   a brand-angle entry point — so these are placed first, up to
   PRIORITY_SLOT_CAP slots.
2. Real scraped platform hotspots (微博 / 微信 / 今日头条 / 百度), filtered to
   a broad set of 快消 (FMCG) product categories (see CATEGORY_RULES below —
   美妆个护 / 酒类 / 母婴用品 / 潮玩文创 / 食品饮料 / 家清家居 / 运动户外 /
   服饰穿搭 / 3C数码 / 宠物用品) and deduped, filling the remaining slots up
   to MAX_RESULTS. Even with this broad a category list, a lot of real-world
   hot searches are still pure news/social-event stories with no commercial
   angle at all — on a day like that, category_matched can legitimately be
   0 and refresh_today_hotspots falls back to the simulated list. That's
   the quality gate working as intended, not a bug.

Scraped-platform data sources, tried in order per platform
------------------------------------------------------------
1. tophub (榜眼数据 / tophubdata.com's official API) — used only if
   TOPHUB_ACCESS_KEY is set as an env var. It's the only source that has
   微信 at all (as "微信24h热文榜", a popular-articles ranking rather than a
   true topic hot-search list — noisier, but the category filter below
   screens most of the noise out). Platform IDs (hashid) are fixed catalog
   identifiers, not secrets, hardcoded below.
2. DailyHotApi (https://github.com/imsyy/DailyHotApi) — a free, no-signup,
   actively maintained open-source hot-list aggregator. Used whenever
   tophub isn't configured, or as the fallback when a specific tophub call
   fails. Doesn't cover 微信, so that platform silently contributes nothing
   when tophub isn't configured — the other 3 platforms carry the list.
3. newsnow (https://github.com/ourongxing/newsnow) — another free,
   self-hosted, open-source aggregator, tried only if DailyHotApi returned
   nothing for that platform AND NEWSNOW_BASE_URL is configured (no public
   demo站可用，必须自己部署). Exists mainly to give 微博/百度 a second chance
   when our self-hosted DailyHotApi instance fails on them (微博 hits a
   403 from Sina blocking non-mainland IPs; 百度 comes back malformed) —
   but note newsnow's 微博 scraper hits the *same* upstream
   (s.weibo.com/top/summary), just with an extra Cookie header, so there's
   no guarantee it actually dodges the same IP block. Worth trying since
   it's free either way.
4. The existing simulated (mock) list — used if none of the sources above,
   combined with the calendar nodes, yield enough results overall, so the
   page never errors out.

Everything here fails soft: if a platform request fails, we just skip it
(or fall through to the next source); if the exhibition/film web-search
call fails, we just get 0 items from it; if too few hotspots survive
overall, refresh_today_hotspots falls back to the simulated list.
"""

import difflib
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.agent import TodayHotspot, TodayHotspotsResponse
from app.services.agent_adapters import build_today_hotspots, create_anthropic_client, extract_message_text
from app.services.marketing_calendar import get_today_calendar_nodes

logger = logging.getLogger(__name__)

HOT_API_BASE_URL = "https://dailyhot-api-psi.vercel.app"  # 自建实例，替代已停摆的官方免费示例站
TOPHUB_API_BASE_URL = "https://api.tophubdata.com"

# tophub 的 hashid 是固定不变的目录 ID，不是密钥，可以放心写死在代码里。
# 微博/今日头条取自 tophub.today 官网对应榜单页面的链接
# （https://tophub.today/n/<hashid>），微信是"微信24h热文榜"。
TOPHUB_HASHIDS: dict[str, str] = {
    "微博": "KqndgxeLl9",
    "今日头条": "x9ozB4KoXb",
    "百度": "Jb0vmloB1G",
    "微信": "WnBe01o371",
}

# dailyhot_path 为 None 表示 DailyHotApi 没有这个平台的路线，只能走 tophub。
SOURCE_PLATFORMS: list[dict[str, str | None]] = [
    {"platform": "微博", "dailyhot_path": "weibo"},
    {"platform": "今日头条", "dailyhot_path": "toutiao"},
    {"platform": "百度", "dailyhot_path": "baidu"},
    {"platform": "微信", "dailyhot_path": None},
]

# newsnow 的 source id，同样是 None 表示没有这个平台（微信不在 newsnow 覆盖范围内，
# 跟 tophub/DailyHotApi 不是同一套命名，单独维护一份映射）。
NEWSNOW_SOURCE_IDS: dict[str, str] = {
    "微博": "weibo",
    "今日头条": "toutiao",
    "百度": "baidu",
}

# 品类关键词库：命中才认为这条热点"适合品牌借势"，过滤掉政治/社会新闻/娱乐八卦等
# 不在快消（FMCG）范围内的内容。原来只覆盖品牌最初重点的5个品类，命中率偏低——
# 按用户要求"罗列所有快消品类"扩到覆盖更全的快消大盘，能接住的热点自然更多。
# 可以按需要继续加词；排在前面的规则优先命中（同一条标题只会算进一个品类）。
CATEGORY_RULES: list[dict[str, Any]] = [
    {
        "keywords": ["美妆", "护肤", "彩妆", "口红", "香水", "面膜", "精华", "粉底", "防晒霜", "身体乳", "香氛", "美容", "洗护", "唇釉", "眼影", "护发", "洗发水", "沐浴露", "防晒"],
        "category": "美妆个护",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["白酒", "啤酒", "红酒", "葡萄酒", "威士忌", "精酿", "鸡尾酒", "黄酒", "清酒", "洋酒"],
        "category": "酒类",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["母婴", "育儿", "宝宝", "婴儿", "奶粉", "纸尿裤", "儿童", "亲子", "孕妈", "新生儿", "辅食", "童装"],
        "category": "母婴用品",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["潮玩", "盲盒", "手办", "谷子", "周边", "IP联名", "痛包", "拍卡", "收藏玩具"],
        "category": "潮玩文创",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["零食", "休闲食品", "辣条", "软糖", "薯片", "饮料", "奶茶", "咖啡", "茶饮", "轻食", "代餐", "酸奶", "乳制品", "气泡水", "预制菜", "速食", "即食", "烘焙", "低糖", "零卡"],
        "category": "食品饮料",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["家清", "洗衣液", "洗洁精", "消毒", "清洁剂", "收纳", "家居", "香薰", "除螨", "厨房清洁", "湿巾", "家务"],
        "category": "家清家居",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["运动", "健身", "跑步", "瑜伽", "户外", "露营", "登山", "骑行", "滑雪", "徒步", "马拉松", "运动装备", "球鞋", "旅行", "出行", "自驾", "野餐", "飞盘"],
        "category": "运动户外",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["穿搭", "服饰", "卫衣", "防晒衣", "冲锋衣", "箱包", "潮牌", "联名款"],
        "category": "服饰穿搭",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["数码", "耳机", "智能手表", "充电宝", "小家电", "平板电脑", "手机壳"],
        "category": "3C数码",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
    {
        "keywords": ["宠物", "猫粮", "狗粮", "萌宠", "铲屎官"],
        "category": "宠物用品",
        "node_type": "lifestyle_trend",
        "node_label": "生活趋势",
    },
]

EXHIBITION_FILM_SYSTEM_PROMPT = """你是品牌营销日历助手。请联网搜索，找出最近两周内（含今天前后）
与消费品牌借势营销相关的：
1. 值得关注的行业展会/展览（例如美妆展、母婴展、潮玩展、酒类展会、运动户外用品展等）
2. 近期上映/开播、国民度或话题度较高的电影/剧集/综艺
3. 近期是否有省市中小学"春假/秋假"临近或正在进行（2025-2026年多地陆续试点，具体日期各省市
   不同，没有全国统一时间表，需要联网查最新消息）

只挑真正适合品牌借势的，不要输出无关内容。最多返回 3 条，三类都没有就少返回或返回空数组。

必须严格输出一个 JSON 数组，不要输出 JSON 之外的任何文字，每个元素格式如下：
{
  "title": "简洁描述，例如"XX美妆展9月开幕"、"XX电影国庆档上映"或"XX省中小学秋假10月中旬开始"",
  "node_type": "exhibition / film_release / public_holiday 三选一（春假秋假用 public_holiday）"
}

如果没有找到合适的，返回空数组 []。"""

DUPLICATE_SIMILARITY_THRESHOLD = 0.45
# 原来是3，但运营日历节点本身就是真实内容（不是抓来的，是日期算出来的），只因为
# 平台热点一条没命中品类就要连日历节点一起藏起来、换成全假的示例数据，有点浪费。
# 降到2之后：只要运营日历命中了至少2个节点（或者日历+品类命中总共凑够2条），
# 就展示真实数据，不会因为品类过滤这一步偏严格就整体回退。
MIN_RESULTS_TO_ACCEPT = 2
MAX_RESULTS = 5
PRIORITY_SLOT_CAP = 2  # 日历节点 + 展会/影视/春秋假 最多占用几个坑位，剩下留给抓取到的真实热点

_cache: dict[str, Any] = {"date": None, "hotspots": None, "generated_at": None}

# 每次点"更新"都会重置，记录这次抓取每一步发生了什么，方便直接从接口返回的
# JSON 里看到失败原因，不用去翻 Railway 后台日志。
_diagnostics: list[str] = []


def _note(message: str) -> None:
    _diagnostics.append(message)
    logger.warning(message)


def _today_str() -> str:
    return datetime.now().strftime("%Y.%m.%d")


def _match_category(title: str) -> dict[str, str] | None:
    for rule in CATEGORY_RULES:
        for keyword in rule["keywords"]:
            if keyword in title:
                return rule
    return None


def _phrase_overlap_ratio(a: str, b: str) -> float:
    """How much of the shorter title is covered by the longest contiguous
    substring shared with the other. Cross-platform hot-search titles for
    the same story are usually the same core phrase with a different
    suffix/prefix tacked on ("通勤防晒穿搭话题登上热搜" vs "通勤防晒穿搭
    今天你晒了吗"), so plain difflib.ratio() (which scores the whole
    strings) under-counts these as different. Longest-common-substring
    coverage catches them without needing a Chinese word segmenter."""
    matcher = difflib.SequenceMatcher(None, a, b)
    match = matcher.find_longest_match(0, len(a), 0, len(b))
    shorter_len = min(len(a), len(b))
    return (match.size / shorter_len) if shorter_len else 0.0


def _is_duplicate(title: str, seen_titles: list[str]) -> bool:
    normalized = title.strip()
    for seen in seen_titles:
        if _phrase_overlap_ratio(normalized, seen) >= DUPLICATE_SIMILARITY_THRESHOLD:
            return True
    return False


def _fetch_from_tophub(client: httpx.Client, platform: str) -> list[dict[str, str]]:
    hashid = TOPHUB_HASHIDS.get(platform)
    if not hashid:
        return []

    try:
        response = client.get(
            f"{TOPHUB_API_BASE_URL}/nodes/{hashid}",
            headers={"Authorization": settings.tophub_access_key},
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        _note(f"tophub 抓取失败 [{platform}]: {type(exc).__name__}: {exc}")
        return []

    data_field = payload.get("data") if isinstance(payload, dict) else None
    raw_items = data_field.get("items") if isinstance(data_field, dict) else None
    if not isinstance(raw_items, list):
        _note(f"tophub 返回格式异常 [{platform}]: {json.dumps(payload, ensure_ascii=False)[:300]}")
        return []

    items: list[dict[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        items.append({"title": title, "platform": platform})

    return items


def _fetch_from_dailyhot(client: httpx.Client, source: dict[str, str | None]) -> list[dict[str, str]]:
    path = source.get("dailyhot_path")
    if not path:
        return []

    try:
        response = client.get(f"{HOT_API_BASE_URL}/{path}", timeout=8.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        _note(f"DailyHotApi 抓取失败 [{path}]: {type(exc).__name__}: {exc}")
        return []

    raw_items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        _note(f"DailyHotApi 返回格式异常 [{path}]: {json.dumps(payload, ensure_ascii=False)[:300]}")
        return []

    items: list[dict[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("name") or "").strip()
        if not title:
            continue
        items.append({"title": title, "platform": source["platform"]})

    return items


def _fetch_from_newsnow(client: httpx.Client, platform: str) -> list[dict[str, str]]:
    source_id = NEWSNOW_SOURCE_IDS.get(platform)
    if not source_id or not settings.has_newsnow_base_url:
        return []

    try:
        response = client.get(
            f"{settings.newsnow_base_url}/api/s",
            params={"id": source_id, "latest": "true"},
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        _note(f"newsnow 抓取失败 [{platform}]: {type(exc).__name__}: {exc}")
        return []

    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        _note(f"newsnow 返回格式异常 [{platform}]: {json.dumps(payload, ensure_ascii=False)[:300]}")
        return []

    items: list[dict[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        items.append({"title": title, "platform": platform})

    return items


def _fetch_platform(client: httpx.Client, source: dict[str, str | None]) -> list[dict[str, str]]:
    """Try tophub first (only if a key is configured), then DailyHotApi,
    then newsnow (only if configured) as a last-resort second opinion for
    whatever DailyHotApi couldn't get for this platform."""
    if settings.has_tophub_key:
        items = _fetch_from_tophub(client, source["platform"])
        if items:
            return items

    items = _fetch_from_dailyhot(client, source)
    if items:
        return items

    return _fetch_from_newsnow(client, source["platform"])


def _fetch_exhibition_and_film_nodes() -> list[dict[str, str]]:
    """Dynamic calendar candidates that no fixed date table can cover —
    looked up live via Claude's web-search tool. Best-effort: any failure
    just means 0 candidates from this source, never an error."""
    if not settings.has_anthropic_key:
        _note("展会/影视/春秋假联网搜索跳过：未配置 ANTHROPIC_API_KEY")
        return []

    today_str = datetime.now().strftime("%Y年%m月%d日")
    client = create_anthropic_client()

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1000,
            system=EXHIBITION_FILM_SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": f"今天是{today_str}，请按要求联网搜索并返回结果。"}],
        )
        raw_text = extract_message_text(response)
        start, end = raw_text.find("["), raw_text.rfind("]")
        if start == -1 or end == -1 or end < start:
            _note(f"展会/影视/春秋假联网搜索返回内容里没找到 JSON 数组，原始片段: {raw_text[:200]!r}")
            return []
        raw_items = json.loads(raw_text[start : end + 1])
    except Exception as exc:
        _note(f"展会/影视/春秋假联网搜索失败: {type(exc).__name__}: {exc}")
        return []

    if not isinstance(raw_items, list):
        return []

    node_meta = {
        "exhibition": {"node_label": "展会信息", "category": "行业展会"},
        "film_release": {"node_label": "影视上映", "category": "影视联动"},
        "public_holiday": {"node_label": "春秋假", "category": "节假日营销"},
    }

    results: list[dict[str, str]] = []
    for raw in raw_items[:PRIORITY_SLOT_CAP]:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        node_type = raw.get("node_type")
        meta = node_meta.get(node_type)
        if not title or meta is None:
            continue
        results.append({"name": title, "node_type": node_type, "node_label": meta["node_label"], "category": meta["category"]})

    return results


def _priority_node_to_entry(node: dict[str, Any]) -> dict[str, str]:
    return {
        "title": node["name"],
        "platform": "运营日历",
        "category": node["category"],
        "tag": node["name"],
        "node_type": node["node_type"],
        "node_label": node["node_label"],
    }


def _build_live_hotspots() -> list[TodayHotspot]:
    key_len = len(settings.tophub_access_key)
    _note(f"TOPHUB_ACCESS_KEY 状态: has_tophub_key={settings.has_tophub_key}, 长度={key_len}")
    _note(f"NEWSNOW_BASE_URL 状态: has_newsnow_base_url={settings.has_newsnow_base_url}, 值={settings.newsnow_base_url or '(未配置)'}")

    calendar_nodes = get_today_calendar_nodes()
    _note(f"运营日历命中 {len(calendar_nodes)} 个节点: {[n['name'] for n in calendar_nodes]}")

    exhibition_nodes = _fetch_exhibition_and_film_nodes()
    _note(f"展会/影视/春秋假联网搜索命中 {len(exhibition_nodes)} 条")

    priority_raw = calendar_nodes + exhibition_nodes
    matched: list[dict[str, str]] = [_priority_node_to_entry(node) for node in priority_raw[:PRIORITY_SLOT_CAP]]
    seen_titles: list[str] = [entry["title"] for entry in matched]

    if len(matched) < MAX_RESULTS:
        collected: list[dict[str, str]] = []
        with httpx.Client() as client:
            for source in SOURCE_PLATFORMS:
                items = _fetch_platform(client, source)
                _note(f"{source['platform']} 原始抓取到 {len(items)} 条（tophub_key={'已配置' if settings.has_tophub_key else '未配置'}）")
                collected.extend(items[:30])

        category_matched = 0
        duplicate_skipped = 0
        for item in collected:
            if len(matched) >= MAX_RESULTS:
                break

            if _is_duplicate(item["title"], seen_titles):
                duplicate_skipped += 1
                continue

            rule = _match_category(item["title"])
            if rule is None:
                continue

            category_matched += 1
            seen_titles.append(item["title"])
            matched.append(
                {
                    "title": item["title"],
                    "platform": item["platform"],
                    "category": rule["category"],
                    "tag": f"{item['platform']}热搜",
                    "node_type": rule["node_type"],
                    "node_label": rule["node_label"],
                }
            )
        _note(f"品类命中 {category_matched} 条，去重跳过 {duplicate_skipped} 条")

    _note(f"最终可用热点 {len(matched)} 条（至少需要 {MIN_RESULTS_TO_ACCEPT} 条才会展示真实数据）")

    if len(matched) < MIN_RESULTS_TO_ACCEPT:
        raise ValueError(f"Only found {len(matched)} usable hotspots, too few to show")

    today = _today_str()
    return [
        TodayHotspot(
            id=index + 1,
            title=entry["title"],
            platform=entry["platform"],
            category=entry["category"],
            tag=entry["tag"],
            date=today,
            node_type=entry["node_type"],
            node_label=entry["node_label"],
        )
        for index, entry in enumerate(matched)
    ]


def get_today_hotspots_response() -> TodayHotspotsResponse:
    """Used by GET /today. Serves today's cached live result if we already
    refreshed today; otherwise serves the existing simulated placeholder
    list, unchanged from before — nothing calls the network here."""
    if _cache["date"] == _today_str() and _cache["hotspots"]:
        return TodayHotspotsResponse(
            hotspots=_cache["hotspots"],
            source="live",
            generated_at=_cache["generated_at"],
        )

    return TodayHotspotsResponse(hotspots=build_today_hotspots(), source="simulated", generated_at=None)


def refresh_today_hotspots() -> TodayHotspotsResponse:
    """Used by POST /refresh — the button handler. Always returns something
    displayable: real data on success, the simulated list on any failure."""
    _diagnostics.clear()

    try:
        hotspots = _build_live_hotspots()
    except Exception as exc:
        logger.exception("Hotspot refresh failed, falling back to simulated list")
        _note(f"整体抓取失败，回退为示例数据: {type(exc).__name__}: {exc}")
        return TodayHotspotsResponse(
            hotspots=build_today_hotspots(),
            source="simulated",
            generated_at=None,
            debug_notes=list(_diagnostics),
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    _cache["date"] = _today_str()
    _cache["hotspots"] = hotspots
    _cache["generated_at"] = generated_at

    return TodayHotspotsResponse(
        hotspots=hotspots,
        source="live",
        generated_at=generated_at,
        debug_notes=list(_diagnostics),
    )


