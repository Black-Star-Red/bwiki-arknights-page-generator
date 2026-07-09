"""中文实装日期：月/日不补前导零；时间戳按北京时间（Asia/Shanghai）取日历日。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_ZH_YMD_FULL_RE = re.compile(r"(\d{1,4})年(\d{1,2})月(\d{1,2})日")
_ZH_MD_RE = re.compile(r"(\d{1,2})月(\d{1,2})日")


def _china_tz():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Shanghai")
    except Exception:
        return timezone(timedelta(hours=8))


# 游戏活动时间、B 站实装展示均按国内日历日理解
CN_TZ = _china_tz()


def format_zh_ymd(year: int, month: int, day: int) -> str:
    return f"{int(year)}年{int(month)}月{int(day)}日"


def zh_ymd_from_unix_ts(ts: int) -> str:
    """Unix 秒 → 北京时间年月日（用于实装日期，避免 UTC/本机时区差一天）。"""
    dt = datetime.fromtimestamp(int(ts), tz=CN_TZ)
    return format_zh_ymd(dt.year, dt.month, dt.day)


def format_ts_cn_datetime(ts: int) -> str:
    """Unix 秒 → 北京时间 `YYYY-MM-DD HH:MM:SS`（活动列表展示）。"""
    return datetime.fromtimestamp(int(ts), tz=CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def format_ts_cn_date(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=CN_TZ).strftime("%Y-%m-%d")


def normalize_zh_release_date(text: str) -> str:
    """
    去掉月/日前导零。

    支持：2026年06月02日 → 2026年6月2日；05月01日 → 5月1日；
    以及 wiki 链接串内的日期片段。
    """
    s = (text or "").strip()
    if not s:
        return s

    if _ZH_YMD_FULL_RE.search(s):

        def _full(m: re.Match[str]) -> str:
            return format_zh_ymd(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        return _ZH_YMD_FULL_RE.sub(_full, s)

    if _ZH_MD_RE.search(s):

        def _md(m: re.Match[str]) -> str:
            return f"{int(m.group(1))}月{int(m.group(2))}日"

        return _ZH_MD_RE.sub(_md, s)

    return s


def normalize_supplementary_release_date(value: str) -> str:
    """实装日期字段（含 wiki 外链整段）统一去月/日前导零。"""
    return normalize_zh_release_date((value or "").strip())


def _parse_zh_month_day(text: str) -> tuple[int, int] | None:
    s = (text or "").strip()
    m = _ZH_MD_RE.search(s)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def zh_ymd_from_pool_article(
    publish_ts: int | None,
    month_day_text: str,
) -> str:
    """
    限定专栏：summary 活动时间月日 + 专栏 publish_time 的年 → 完整实装日。

    若 month_day_text 已含四位数年份则仅规范化。
    """
    raw = (month_day_text or "").strip()
    if not raw:
        return ""
    if _ZH_YMD_FULL_RE.search(raw):
        return normalize_zh_release_date(raw)
    md = _parse_zh_month_day(raw)
    if md is None:
        return normalize_zh_release_date(raw)
    month, day = md
    if publish_ts is not None:
        try:
            year = datetime.fromtimestamp(int(publish_ts), tz=CN_TZ).year
        except (OSError, OverflowError, ValueError):
            year = None
        if year is not None:
            return format_zh_ymd(year, month, day)
    return f"{month}月{day}日"


__all__ = [
    "CN_TZ",
    "format_zh_ymd",
    "zh_ymd_from_unix_ts",
    "format_ts_cn_datetime",
    "format_ts_cn_date",
    "normalize_zh_release_date",
    "normalize_supplementary_release_date",
    "zh_ymd_from_pool_article",
]
