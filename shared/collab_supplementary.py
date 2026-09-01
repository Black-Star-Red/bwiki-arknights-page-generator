"""联动补充字段：获取途径解析与 联动/联动卡池 推断（供 DB merge 与角标共用）。"""

from __future__ import annotations

import re
from typing import Any

_COLLAB_OBTAIN_RE = re.compile(r"^联动、联动寻访、【([^】]+)】寻访")
_COLLAB_OBTAIN_LEGACY_RE = re.compile(r"^联动寻访、【([^】]+)】寻访")
_COLLAB_ACTIVITY_REWARD_RE = re.compile(
    r"^【([^】]+)】活动获取、活动获取、联动$"
)
_ACTIVITY_REWARD_SHORT_RE = re.compile(r"^活动获取、【([^】]+)】活动获取$")
_NAMED_GACHA_POOL_SKIP = frozenset({
    "新增干员",
    "活动奖励干员",
    "主题曲奖励干员",
})
def is_named_gacha_pool(gacha_pool: str | None) -> bool:
    """预告第一行是否为命名卡池（如 幽境狩人），而非 新增干员 等占位名。"""
    named = (gacha_pool or "").strip()
    return bool(named) and named not in _NAMED_GACHA_POOL_SKIP
def collab_gacha_pools_at_or_before(
    scan_ctx: Any | None,
    operator_pub_ts: int | None,
) -> set[str]:
    """
    只返回「池公告发布时间 <= 干员预告发布时间」的联动池名。
    scan_ctx.collab_gacha_pool_pub_ts 由 refresh_scan_activity_cache 在扫描时写入。
    """
    if scan_ctx is None:
        return set()
    table: dict[str, int] = getattr(scan_ctx, "collab_gacha_pool_pub_ts", None) or {}
    if not table:
        return set()
    if operator_pub_ts is None:
        return set()
    return {name for name, ts in table.items() if ts <= operator_pub_ts}

def pick_collab_gacha_pool(
    pools: set[str] | None,
    *,
    gacha_pool: str | None = None,
) -> str | None:
    """从 × 联动公告解析出的限时池名集合中取代表名（优先本条预告的命名池）。"""
    named = (gacha_pool or "").strip()
    if is_named_gacha_pool(named):
        return named
    if not pools:
        return None
    return sorted(pools)[0]


def is_collab_activity_reward_obtain(obtain: str) -> bool:
    """联动期活动奖励获取途径（含 、活动获取、联动 或标准三联句式）。"""
    text = (obtain or "").strip()
    if "、活动获取、联动" in text:
        return True
    return bool(_COLLAB_ACTIVITY_REWARD_RE.match(text))


def is_collab_period_activity_reward_context(
    scan_ctx: Any | None,
    *,
    gui_activity: str = "",
    pools_at_or_before: set[str] | None = None,
    is_main_theme_gui: bool = False,
) -> bool:
    """
    活动奖励干员是否处于联动活动窗。

    - GUI 已选活动：沿用原规则（联动池缓存 / 活动名与 feed 对齐）。
    - 未选 GUI 活动：feed 预填已识别联动限时池（如按数量批量扫描）时也视为联动期。
    """
    if scan_ctx is None or is_main_theme_gui:
        return False
    cached_pools = set(getattr(scan_ctx, "cached_collab_gacha_pools", None) or ())
    timeline_pools = set(pools_at_or_before or ())
    has_collab_signal = bool(cached_pools or timeline_pools)
    gui = (gui_activity or "").strip()
    if gui:
        cached_name = (getattr(scan_ctx, "cached_activity_name", None) or "").strip()
        cached_ss = str(getattr(scan_ctx, "cached_side_story", None) or "")
        return (
            has_collab_signal
            or cached_name == gui
            or gui in cached_ss
        )
    return has_collab_signal


def collab_pool_from_obtain(obtain: str) -> str | None:
    text = (obtain or "").strip()
    for pat in (_COLLAB_OBTAIN_RE, _COLLAB_OBTAIN_LEGACY_RE):
        m = pat.match(text)
        if m:
            return m.group(1).strip()
    return None


def _is_activity_or_theme_obtain(obtain: str) -> bool:
    text = obtain or ""
    return "活动获取" in text or "活动获得" in text or "主题曲" in text


def _wiki_collab_activity_reward_obtain(obtain: str) -> str | None:
    """联动活动奖励：【活动名】活动获取、活动获取、联动。"""
    text = (obtain or "").strip()
    if is_collab_activity_reward_obtain(text):
        return text
    m = _ACTIVITY_REWARD_SHORT_RE.match(text)
    if m:
        return f"联动、活动获取、【{m.group(1)}】活动获取"
    return None


def _wiki_collab_gacha_obtain(value: dict[str, Any], obtain: str) -> str | None:
    """联动卡池寻访：联动、联动寻访、【池名】寻访。"""
    pool = collab_pool_from_obtain(obtain) or str(value.get("联动卡池") or "").strip()
    if not pool:
        return None
    return f"联动、联动寻访、【{pool}】寻访"


def wiki_obtain_path(value: dict[str, Any]) -> str:
    """Wiki |获取途径= 与入库回填一致；联动干员统一带「联动」文案。"""
    obtain = str(value.get("获取途径") or "").strip()
    if value.get("联动") is True:
        if "主题曲" in obtain:
            return obtain
        if "活动获取" in obtain or "活动获得" in obtain:
            collab_activity = _wiki_collab_activity_reward_obtain(obtain)
            if collab_activity:
                return collab_activity
        gacha = _wiki_collab_gacha_obtain(value, obtain)
        if gacha:
            return gacha

    if _is_activity_or_theme_obtain(obtain):
        return obtain
    pool = collab_pool_from_obtain(obtain) or str(value.get("联动卡池") or "").strip()
    if pool and collab_pool_from_obtain(obtain) is not None:
        return f"联动、联动寻访、【{pool}】寻访"
    return obtain


def enrich_collab_meta(value: dict[str, Any]) -> dict[str, Any]:
    """从 联动 标记或联动寻访/联动活动奖励获取途径补全 联动/联动卡池。"""
    out = dict(value)
    if out.get("联动") is True:
        return out
    obtain = str(out.get("获取途径") or "")
    if is_collab_activity_reward_obtain(obtain):
        out["联动"] = True
        return out
    pool = collab_pool_from_obtain(obtain)
    if pool:
        out["联动"] = True
        if not str(out.get("联动卡池") or "").strip():
            out["联动卡池"] = pool
    return out
def _has_collab_gacha_obtain(obtain: str) -> bool:
    return collab_pool_from_obtain(obtain) is not None
def _existing_collab_pool(value: dict[str, Any], obtain: str) -> str:
    return (
        str(value.get("联动卡池") or "").strip()
        or collab_pool_from_obtain(obtain)
        or ""
    )
def _collab_pool_cutoff_ts(
    value: dict[str, Any],
    scan_ctx: Any | None,
) -> int | None:
    """
    apply 推断联动池的截止时间。
    DB 跳过路径没有 B 站 item：用活动 end_ts（窗内全部合法池）。
    """
    if scan_ctx is None:
        return None
    end = getattr(scan_ctx, "gui_activity_end_ts", None)
    return int(end) if end is not None else None
def _pool_plausible_at_cutoff(
    pool: str,
    scan_ctx: Any | None,
    cutoff_ts: int | None,
) -> bool:
    """池名在截止时间前确实出现过（时间表 + 时间过滤）。"""
    if not pool or scan_ctx is None or cutoff_ts is None:
        return False
    table: dict[str, int] = getattr(scan_ctx, "collab_gacha_pool_pub_ts", None) or {}
    if pool not in table:
        return False
    return table[pool] <= cutoff_ts
def _should_preserve_collab_pool(
    value: dict[str, Any],
    obtain: str,
    scan_ctx: Any | None,
    cutoff_ts: int | None,
) -> bool:
    """
    已有可靠联动池 → apply 不得覆盖。
    覆盖 B 站 named_pool_from_announce / collab_period_new_ops 的正确结果。
    """
    if _is_activity_or_theme_obtain(obtain):
        # 活动/主题曲奖励：不拿寻访池去改 联动卡池
        return bool(_existing_collab_pool(value, obtain))
    pool = _existing_collab_pool(value, obtain)
    if not pool:
        return False
    # 预告命名池（幽境狩人）或已是联动寻访文案
    if is_named_gacha_pool(pool) or _has_collab_gacha_obtain(obtain):
        if _pool_plausible_at_cutoff(pool, scan_ctx, cutoff_ts):
            return True
        # 不在时间表里但已是联动寻访（历史数据）→ 仍保留
        if _has_collab_gacha_obtain(obtain):
            return True
    # 仅 联动卡池 字段、无联动寻访文案
    if str(value.get("联动卡池") or "").strip():
        if _pool_plausible_at_cutoff(pool, scan_ctx, cutoff_ts):
            return True
    return False

def apply_collab_period_supplementary_meta(
    value: dict[str, Any],
    scan_ctx: Any | None,
) -> dict[str, Any]:
    """
    联动期 DB 仅「标准寻访」时补 联动/联动卡池。
    B 站已写入的正确池名不得被 cached 覆盖。
    """
    out = enrich_collab_meta(dict(value))
    if scan_ctx is None:
        return out
    gui = (getattr(scan_ctx, "gui_activity_name", None) or "").strip()
    obtain = str(out.get("获取途径") or "").strip()
    is_main_theme_gui = bool(
        getattr(scan_ctx, "gui_activity_is_main_theme", False)
    )
    # 活动奖励干员打「联」角标（与池无关）
    cached_name = (getattr(scan_ctx, "cached_activity_name", None) or "").strip()
    cached_collab = bool(getattr(scan_ctx, "cached_collab_gacha_pools", None))
    is_activity_obtain = "活动获取" in obtain or "活动获得" in obtain
    if not is_main_theme_gui and is_activity_obtain:
        if gui and (gui in obtain or is_collab_activity_reward_obtain(obtain)):
            out["联动"] = True
        elif (
            not gui
            and cached_collab
            and cached_name
            and cached_name in obtain
        ):
            out["联动"] = True
    if not gui:
        return out
    cutoff = _collab_pool_cutoff_ts(out, scan_ctx)
    # ★ 防覆盖：B 站/DB 已有合理池 → 直接返回
    if _should_preserve_collab_pool(out, obtain, scan_ctx, cutoff):
        return out
    pools = collab_gacha_pools_at_or_before(scan_ctx, cutoff)
    if not pools:
        return out
    preferred = pick_collab_gacha_pool(pools)
    if not preferred:
        return out
    existing = _existing_collab_pool(out, obtain)
    # ★ 只「补全」空的标准寻访，不「改正」已有联动寻访
    if obtain in ("", "标准寻访"):
        out["联动"] = True
        out["联动卡池"] = preferred
        return out
    # ★ 仅当 obtain 写了错误联动池（如定向甄选）且 preferred 更合理时才改
    if (
        out.get("联动")
        and existing
        and existing != preferred
        and _has_collab_gacha_obtain(obtain)
        and not _pool_plausible_at_cutoff(existing, scan_ctx, cutoff)
        and _pool_plausible_at_cutoff(preferred, scan_ctx, cutoff)
    ):
        out["联动卡池"] = preferred
        out["获取途径"] = f"联动、联动寻访、【{preferred}】寻访"
    return out