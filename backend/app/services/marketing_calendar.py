"""今日/近期运营节点日历。

按用户要求："如果遇到二十四节气、国际节日、中国传统节日、电商节日...品牌切入角度优先和
这类热点相结合" —— 这个模块跟抓取到的热搜内容完全无关，只看"今天是几号"，从固定日期表 /
农历换算里找出临近的节点。找到的节点会被 hotspot_source.py 当成优先坑位，排在抓取到的真实
热点前面。

覆盖范围：
- 二十四节气：公历近似固定日期，年际会有 ±1 天的天文浮动，营销场景够用，不追求分秒级精确。
- 法定节假日：元旦（固定公历日期）。
- 电商节点：38/315/520/618/77/88/99/双11/双12 等固定日期大促节点。
- 国际节日：固定日期的（情人节/愚人节/万圣节/圣诞节）+ 需要计算"第几个星期几"的（母亲节/
  父亲节/感恩节）。
- 中国传统节日：农历节日（春节/元宵/端午/七夕/中秋/重阳/腊八），用 zhdate 换算成公历日期。
- 开学季：不是单独一天，是一段窗口期（秋季学期 8月底-9月初、春季学期 2月中），按日期区间
  判断"是否临近"，而不是精确到某一天。

展会信息、影视上映、以及各地"春秋假"这类没有全国统一固定日期的信息（2025-2026 年多地陆续
试点春秋假，但具体放几天、哪几天完全是各省市自己定，没有全国统一日期表可查），走另一个模块
（hotspot_source.py 里的联网搜索），不在这里处理。
"""

import datetime

from zhdate import ZhDate

LOOKAHEAD_DAYS = 3  # 节点前后 3 天内都算"临近"，不用卡死必须是当天才生效

SOLAR_TERMS: list[tuple[int, int, str]] = [
    (1, 5, "小寒"), (1, 20, "大寒"), (2, 4, "立春"), (2, 19, "雨水"),
    (3, 5, "惊蛰"), (3, 20, "春分"), (4, 5, "清明"), (4, 20, "谷雨"),
    (5, 5, "立夏"), (5, 21, "小满"), (6, 5, "芒种"), (6, 21, "夏至"),
    (7, 7, "小暑"), (7, 22, "大暑"), (8, 7, "立秋"), (8, 23, "处暑"),
    (9, 7, "白露"), (9, 23, "秋分"), (10, 8, "寒露"), (10, 23, "霜降"),
    (11, 7, "立冬"), (11, 22, "小雪"), (12, 7, "大雪"), (12, 21, "冬至"),
]

ECOMMERCE_NODES: list[tuple[int, int, str]] = [
    (3, 8, "38女王节"), (3, 15, "315消费者权益日"), (5, 20, "520"),
    (6, 18, "618年中大促"), (7, 7, "77会员节"), (8, 8, "88大促"),
    (9, 9, "99划算节"), (11, 11, "双11"), (12, 12, "双12"),
]

PUBLIC_HOLIDAYS_FIXED: list[tuple[int, int, str]] = [
    (1, 1, "元旦"),
]

INTERNATIONAL_FESTIVALS_FIXED: list[tuple[int, int, str]] = [
    (2, 14, "情人节"), (4, 1, "愚人节"), (10, 31, "万圣节"), (12, 25, "圣诞节"),
]

# (农历月, 农历日, 名称) —— 七夕节已包含在内
LUNAR_FESTIVALS: list[tuple[int, int, str]] = [
    (1, 1, "春节"), (1, 15, "元宵节"), (5, 5, "端午节"),
    (7, 7, "七夕节"), (8, 15, "中秋节"), (9, 9, "重阳节"), (12, 8, "腊八节"),
]

# 开学季不是某一天，是一段窗口期：(起始月, 起始日, 结束月, 结束日, 名称)
SCHOOL_SEASON_RANGES: list[tuple[int, int, int, int, str]] = [
    (8, 25, 9, 10, "秋季开学季"),
    (2, 10, 2, 25, "春季开学季"),
]


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> datetime.date:
    """weekday: 周一=0 ... 周日=6。n 从 1 开始数第几个。"""
    day = datetime.date(year, month, 1)
    count = 0
    while True:
        if day.weekday() == weekday:
            count += 1
            if count == n:
                return day
        day += datetime.timedelta(days=1)


def _computed_international_festivals(year: int) -> list[tuple[datetime.date, str]]:
    return [
        (_nth_weekday_of_month(year, 5, 6, 2), "母亲节"),   # 5月第2个周日
        (_nth_weekday_of_month(year, 6, 6, 3), "父亲节"),   # 6月第3个周日
        (_nth_weekday_of_month(year, 11, 3, 4), "感恩节"),  # 11月第4个周四
    ]


def _lunar_festival_dates(year: int) -> list[tuple[datetime.date, str]]:
    results = []
    for lunar_month, lunar_day, name in LUNAR_FESTIVALS:
        for candidate_year in (year - 1, year, year + 1):
            # 跨年：农历年初的节日换算到公历可能落在上一年年底，所以对相邻年份都试一遍，
            # 只保留换算结果确实落在目标公历年附近的。
            try:
                gdate = ZhDate(candidate_year, lunar_month, lunar_day).to_datetime().date()
            except Exception:
                continue
            if gdate.year == year:
                results.append((gdate, name))
    return results


NODE_TYPE_META = {
    "solar_term": {"node_label": "二十四节气", "category": "节气应景"},
    "ecommerce_node": {"node_label": "电商节点", "category": "电商大促"},
    "international_festival": {"node_label": "国际节日", "category": "国际节日营销"},
    "traditional_festival": {"node_label": "中国传统节日", "category": "传统节日营销"},
    "public_holiday": {"node_label": "法定节假日", "category": "节假日营销"},
    "lifestyle_trend": {"node_label": "生活趋势", "category": "开学季营销"},
}


def _range_days_away(today: datetime.date, start: datetime.date, end: datetime.date) -> int | None:
    """在区间内返回 0；区间前/后在 LOOKAHEAD_DAYS 天以内返回正数天数差；否则返回 None。"""
    if start <= today <= end:
        return 0
    if today < start:
        gap = (start - today).days
    else:
        gap = (today - end).days
    return gap if gap <= LOOKAHEAD_DAYS else None


def _fixed_dates_near(year: int, month: int, day: int) -> list[datetime.date]:
    """公历固定 (月,日) 节点在年初/年末附近可能跨年才落在 LOOKAHEAD_DAYS 范围内
    （比如 12月30日 应该能看到 3 天后的"元旦"，但元旦是下一年的 1月1日），
    所以对 year-1/year/year+1 都生成一份候选，交给后面统一按"离今天多近"过滤。"""
    dates = []
    for y in (year - 1, year, year + 1):
        try:
            dates.append(datetime.date(y, month, day))
        except ValueError:
            continue  # 理论上不会发生（没有用到2月29日这种日期），保险起见
    return dates


def get_today_calendar_nodes(today: datetime.date | None = None) -> list[dict]:
    """返回按"离今天多近"排序的日历节点候选列表，每项：
    {name, date, node_type, node_label, category, days_away}
    只包含落在 LOOKAHEAD_DAYS 天以内（或落在开学季窗口期内）的节点，通常一天不会超过 1-2 个。
    """
    today = today or datetime.date.today()
    year = today.year

    raw: list[tuple[datetime.date, str, str]] = []

    for month, day, name in SOLAR_TERMS:
        for gdate in _fixed_dates_near(year, month, day):
            raw.append((gdate, name, "solar_term"))

    for month, day, name in ECOMMERCE_NODES:
        for gdate in _fixed_dates_near(year, month, day):
            raw.append((gdate, name, "ecommerce_node"))

    for month, day, name in PUBLIC_HOLIDAYS_FIXED:
        for gdate in _fixed_dates_near(year, month, day):
            raw.append((gdate, name, "public_holiday"))

    for month, day, name in INTERNATIONAL_FESTIVALS_FIXED:
        for gdate in _fixed_dates_near(year, month, day):
            raw.append((gdate, name, "international_festival"))

    for y in (year - 1, year, year + 1):
        for gdate, name in _computed_international_festivals(y):
            raw.append((gdate, name, "international_festival"))

    for gdate, name in _lunar_festival_dates(year):
        raw.append((gdate, name, "traditional_festival"))

    nearby = []
    for gdate, name, node_type in raw:
        days_away = (gdate - today).days
        if abs(days_away) <= LOOKAHEAD_DAYS:
            meta = NODE_TYPE_META[node_type]
            nearby.append({
                "name": name,
                "date": gdate,
                "node_type": node_type,
                "node_label": meta["node_label"],
                "category": meta["category"],
                "days_away": days_away,
            })

    for start_month, start_day, end_month, end_day, name in SCHOOL_SEASON_RANGES:
        start = datetime.date(year, start_month, start_day)
        end = datetime.date(year, end_month, end_day)
        days_away = _range_days_away(today, start, end)
        if days_away is not None:
            meta = NODE_TYPE_META["lifestyle_trend"]
            nearby.append({
                "name": name,
                "date": start,
                "node_type": "lifestyle_trend",
                "node_label": meta["node_label"],
                "category": meta["category"],
                "days_away": days_away,
            })

    nearby.sort(key=lambda item: abs(item["days_away"]))
    return nearby
