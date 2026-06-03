"""B 站动态扫描：仅发现干员名 / 按名完整抓取（OCR 等）。"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import requests

from .bilibili_service import (
    BILIBILI_PRE_START_SECONDS,
    BilibiliScanContext,
    _collect_rich_text_nodes_with_source,
    _dynamic_in_activity_window,
    _dynamic_is_collaboration,
    _dynamic_pub_ts,
    _effective_dynamic_start,
    _extract_collab_gacha_pools_from_nodes,
    _extract_limited_operators_from_article_summary,
    extract_article_pool_keys,
    _extract_side_story_from_nodes,
    _first_dyn_draw_src,
    _is_limited_operator_in_pool,
    _obtain_path_for_gacha_pool,
    fetch_user_dynamics,
    get_dynamic_id,
    operator_photo_dir,
    effective_side_story_for_hit,
    pick_collab_gacha_pool,
    refresh_scan_activity_cache,
    resolve_activity_reward_name,
    resolve_collab_activity_name,
    should_use_main_theme_reward_obtain,
    _main_theme_reward_obtain_path,
)


@dataclass
class _AnnounceHit:
    name: str
    text: str
    item: dict[str, Any]
    photo_url: str
    gacha_pool: str
    is_collab: bool
    side_story: str | None
    collab_gacha_pools: set[str] = field(default_factory=set)


def _try_parse_announce_text(
    text: str,
    announce_line_re: re.Pattern[str],
) -> tuple[str, str] | None:
    """解析干员预告行 → (卡池名, 干员名)；干员名已 strip。"""
    text = text or ""
    if not announce_line_re.match(text):
        return None
    start = text.find("//")
    end = text.find("\n", start)
    if start == -1 or end == -1 or end <= start + 2:
        return None
    gacha_pool = text[text.find("【") + 1 : text.find("】")].strip()
    name = text[start + 2 : end].strip()
    if not name:
        return None
    return gacha_pool, name


def _remember_discovered_announce(
    scan_ctx: BilibiliScanContext | None,
    hit: _AnnounceHit,
) -> None:
    if scan_ctx is None:
        return
    nm = (hit.name or "").strip()
    sid = str(hit.item.get("id_str") or "")
    if nm and sid:
        scan_ctx.discovered_dynamic_ids[nm] = sid


def _load_pool_view(
    mid: str,
    headers: dict[str, str],
) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    pool_view: dict[str, list[str]] = {}
    pool_limited_ops: dict[str, set[str]] = {}
    url = "https://api.bilibili.com/x/space/article"
    params = {"mid": mid, "ps": 12}
    request = None
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200 and (resp.text or "").strip():
                request = resp
                break
        except requests.RequestException:
            pass
        time.sleep((2**attempt) * 0.4 + random.random() * 0.2)
    if request is None:
        return pool_view, pool_limited_ops
    try:
        articles = request.json().get("data", {}).get("articles", [])
    except ValueError:
        articles = []
    for article in articles:
        title = article.get("title") or ""
        summary = article.get("summary") or ""
        if "限定寻访" not in title and "限定寻访" not in summary:
            continue
        pool_key, banner_type = extract_article_pool_keys(title, summary)
        if not pool_key:
            left = title.find("【")
            right = title.find("】")
            if left != -1 and right > left:
                pool_key = title[left + 1 : right].strip()
        if not pool_key:
            continue
        if not banner_type and len(title) > 8:
            banner_type = title[1:8]
        ltime = summary.find("活动时间：")
        rtime = summary.find("日")
        release = ""
        if ltime != -1 and rtime != -1 and rtime >= ltime:
            release = summary[ltime + 5 : rtime + 1]
        data = [banner_type or "", release]
        pool_view[pool_key] = data
        pool_limited_ops[pool_key] = _extract_limited_operators_from_article_summary(
            summary
        )
    return pool_view, pool_limited_ops


def _build_character_from_hit(
    hit: _AnnounceHit,
    *,
    pool_view: dict[str, list[str]],
    pool_limited_ops: dict[str, set[str]],
    acquisition_method: dict[str, str],
    run_ocr: bool,
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
    scan_ctx: BilibiliScanContext | None = None,
) -> dict[str, Any]:
    character: dict[str, Any] = {}
    name = hit.name
    text = hit.text
    item = hit.item
    gacha_pool = hit.gacha_pool
    photo_path = operator_photo_dir() / f"{name}.jpg"

    if run_ocr:
        if not photo_path.exists():
            photo = requests.get(hit.photo_url, timeout=10)
            photo_path.parent.mkdir(parents=True, exist_ok=True)
            if photo.status_code == 200:
                photo_path.write_bytes(photo.content)
        try:
            from .ocr_service import ocr_operator_profile

            profile = ocr_operator_profile(str(photo_path))
            character["专精"] = profile.get("专精") or ""
            character["画师"] = profile.get("画师") or ""
        except Exception:
            character["专精"] = ""
            character["画师"] = ""
            log_warning("预告图 OCR 失败（专精/画师），已降级为空 name=%s", name)

    pools = set(hit.collab_gacha_pools)
    if scan_ctx is not None:
        pools |= scan_ctx.cached_collab_gacha_pools
    is_collab_dynamic = hit.is_collab
    named_collab_pool = bool(
        is_collab_dynamic
        and gacha_pool
        and gacha_pool not in ("新增干员", "活动奖励干员", "主题曲奖励干员")
    )
    collab_standard_pool = bool(
        is_collab_dynamic
        and gacha_pool in ("新增干员", "活动奖励干员", "主题曲奖励干员")
    )
    gui_activity = (
        (scan_ctx.gui_activity_name or "").strip() if scan_ctx else ""
    )
    collab_period_new_ops = bool(
        not is_collab_dynamic
        and gacha_pool == "新增干员"
        and bool(pools)
        and not gui_activity
    )
    release_time = None
    implementation_data = pool_view.get(gacha_pool)

    if named_collab_pool:
        character["联动"] = True
        character["联动卡池"] = gacha_pool
        character["获取途径"] = _obtain_path_for_gacha_pool(
            gacha_pool, acquisition_method, collab=True
        )
        dynamic_id = get_dynamic_id(name)
        if dynamic_id:
            character["动态id"] = dynamic_id
    elif collab_standard_pool:
        character["联动"] = True
        reward_activity = (
            resolve_activity_reward_name(side_story=hit.side_story, scan_ctx=scan_ctx)
            if gacha_pool in ("活动奖励干员", "主题曲奖励干员")
            else None
        )
        if gacha_pool in ("活动奖励干员", "主题曲奖励干员"):
            log_info(
                "collab_activity_reward name=%s pool=%s activity=%s gui=%s side_story=%s",
                name,
                gacha_pool,
                reward_activity,
                (scan_ctx.gui_activity_name if scan_ctx else None),
                hit.side_story,
            )
        collab_pool = (
            pick_collab_gacha_pool(pools) if gacha_pool == "新增干员" else None
        )
        if collab_pool:
            character["联动卡池"] = collab_pool
        if should_use_main_theme_reward_obtain(
            gacha_pool, hit.side_story, scan_ctx
        ):
            character["获取途径"] = _main_theme_reward_obtain_path(reward_activity)
        else:
            character["获取途径"] = _obtain_path_for_gacha_pool(
                gacha_pool,
                acquisition_method,
                side_story=hit.side_story,
                collab=True,
                activity_name=reward_activity,
                collab_pool=collab_pool,
            )
    elif should_use_main_theme_reward_obtain(
        gacha_pool, hit.side_story, scan_ctx
    ):
        reward_activity = resolve_activity_reward_name(
            side_story=hit.side_story, scan_ctx=scan_ctx
        )
        log_info(
            "main_theme_reward name=%s pool=%s activity=%s gui=%s side_story=%s",
            name,
            gacha_pool,
            reward_activity,
            (scan_ctx.gui_activity_name if scan_ctx else None),
            hit.side_story,
        )
        character["获取途径"] = _main_theme_reward_obtain_path(reward_activity)
    elif gacha_pool == "活动奖励干员":
        reward_activity = resolve_activity_reward_name(
            side_story=hit.side_story, scan_ctx=scan_ctx
        )
        log_info(
            "activity_reward name=%s activity=%s gui=%s side_story=%s",
            name,
            reward_activity,
            (scan_ctx.gui_activity_name if scan_ctx else None),
            hit.side_story,
        )
        character["获取途径"] = _obtain_path_for_gacha_pool(
            "活动奖励干员",
            acquisition_method,
            side_story=hit.side_story,
            collab=False,
            activity_name=reward_activity,
        )
    elif collab_period_new_ops:
        character["联动"] = True
        collab_pool = pick_collab_gacha_pool(pools)
        if collab_pool:
            character["联动卡池"] = collab_pool
        character["获取途径"] = acquisition_method.get("新增干员", "标准寻访")
    elif (
        pool_view.get(gacha_pool) is not None
        or pool_limited_ops.get(gacha_pool)
    ):
        implementation_data = pool_view.get(gacha_pool) or ["", ""]
        if implementation_data[1] and implementation_data[1][0] == "0":
            implementation_data = [implementation_data[0], implementation_data[1][1:]]
        release_time = implementation_data[1] or None
        prefix = acquisition_method.get(implementation_data[0] or "")
        limited_in_pool = pool_limited_ops.get(gacha_pool, set())
        is_limited = bool(
            limited_in_pool
            and prefix is not None
            and _is_limited_operator_in_pool(name, limited_in_pool)
        )
        log_info(
            "pool_obtain name=%s pool=%s banner=%s limited_tags=%s is_limited=%s",
            name,
            gacha_pool,
            implementation_data[0],
            sorted(limited_in_pool) or None,
            is_limited,
        )
        if is_limited:
            character["获取途径"] = prefix + f"{gacha_pool}】限定寻访"
            dynamic_id = get_dynamic_id(name)
            if dynamic_id:
                character["动态id"] = dynamic_id
        else:
            character["获取途径"] = acquisition_method.get("新增干员", "标准寻访")
    else:
        log_info(
            "pool_obtain_fallback name=%s pool=%s (no article match)",
            name,
            gacha_pool,
        )
        character["获取途径"] = _obtain_path_for_gacha_pool(
            gacha_pool,
            acquisition_method,
            side_story=hit.side_story,
        )

    if release_time:
        character["实装日期"] = (
            f"[https://t.bilibili.com/{item['id_str']}?spm_id_from=333.1387.0.0 {release_time}]"
        )
    else:
        character["实装日期"] = (
            f"[https://t.bilibili.com/{item['id_str']}?spm_id_from=333.1387.0.0 "
            f"{datetime.now().strftime('%Y年%m月%d日')}]"
        )
    intro = text[text.rfind("_") + 2 :].rstrip("\n")
    intro = intro.replace("\n", "<br/>\n")
    character["宣传介绍"] = intro.replace(
        "<br/>\n<br/>\n关注并转发本条动态，我们将抽取10位博士赠送【现金648元】一份。",
        "",
    )
    return character


def _prefill_activity_cache_from_feed(
    mid: str,
    headers: dict[str, str],
    scan_ctx: BilibiliScanContext,
    *,
    announce_line_re: re.Pattern[str],
    collab_activity_re: re.Pattern[str] | None,
    dynamic_start_ts: int | None,
    dynamic_end_ts: int | None,
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
) -> None:
    """无 GUI 活动名时先扫 feed，缓存 SideStory/联动活动名（供后续预告动态共用）。"""
    if (scan_ctx.gui_activity_name or "").strip():
        return
    if (scan_ctx.cached_side_story or "").startswith("SideStory"):
        log_info(
            "bilibili_activity_cache skip prefill side_story=%s name=%s",
            scan_ctx.cached_side_story,
            scan_ctx.cached_activity_name,
        )
        return

    def on_hit(_hit: _AnnounceHit) -> bool:
        return True

    _scan_announces(
        mid,
        headers,
        announce_line_re=announce_line_re,
        collab_activity_re=collab_activity_re,
        character_num=1,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        log_warning=log_warning,
        log_info=log_info,
        on_hit=on_hit,
        scan_ctx=scan_ctx,
        cache_only=True,
    )
    if scan_ctx.cached_side_story or scan_ctx.cached_activity_name:
        log_info(
            "bilibili_activity_cache prefill side_story=%s name=%s pools=%s",
            scan_ctx.cached_side_story,
            scan_ctx.cached_activity_name,
            sorted(scan_ctx.cached_collab_gacha_pools) or None,
        )
    else:
        log_warning(
            "bilibili_activity_cache prefill empty start=%s end=%s",
            dynamic_start_ts,
            dynamic_end_ts,
        )


def _scan_announces(
    mid: str,
    headers: dict[str, str],
    *,
    announce_line_re: re.Pattern[str],
    collab_activity_re: re.Pattern[str] | None,
    character_num: int,
    dynamic_start_ts: int | None,
    dynamic_end_ts: int | None,
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
    on_hit: Callable[[_AnnounceHit], bool],
    scan_ctx: BilibiliScanContext | None = None,
    cache_only: bool = False,
    fetch_targets: set[str] | None = None,
) -> dict[str, int]:
    """
    扫描动态 feed，对每个干员预告调用 on_hit(hit)。
    on_hit 返回 False 时停止整次扫描。
    """
    diag: dict[str, int] = {
        "pages": 0,
        "items_total": 0,
        "skipped_exceptions": 0,
        "announce_hits": 0,
    }
    eff_start = _effective_dynamic_start(dynamic_start_ts)
    collab_gacha_pools: set[str] = set()
    time_filter = dynamic_start_ts is not None or dynamic_end_ts is not None
    if time_filter:
        log_info(
            "bilibili_dynamic_time_filter start=%s end=%s effective_start=%s (pre_%ss)",
            dynamic_start_ts,
            dynamic_end_ts,
            eff_start,
            BILIBILI_PRE_START_SECONDS,
        )

    dynamics = fetch_user_dynamics(mid, headers, log_warning=log_warning)
    fetch_page_cap: int | None = None
    wanted_dynamic_ids: set[str] = set()
    if not cache_only and scan_ctx is not None and fetch_targets:
        for t in fetch_targets:
            sid = scan_ctx.discovered_dynamic_ids.get((t or "").strip())
            if sid:
                wanted_dynamic_ids.add(sid)
        # 有发现阶段动态 id 时不再用页数封顶，避免扫不到第三条联动预告
        if not wanted_dynamic_ids and scan_ctx.discover_feed_pages:
            fetch_page_cap = scan_ctx.discover_feed_pages + 10

    while True:
        if not dynamics or not isinstance(dynamics, dict):
            break
        diag["pages"] += 1
        if fetch_page_cap is not None and diag["pages"] > fetch_page_cap:
            log_info(
                "bilibili_fetch_scan_cap pages=%s cap=%s",
                diag["pages"],
                fetch_page_cap,
            )
            break
        items_page = dynamics.get("items") or []
        if not isinstance(items_page, list):
            break
        diag["items_total"] += len(items_page)
        reached_before_window = False

        for item in items_page:
            if time_filter:
                window = _dynamic_in_activity_window(
                    _dynamic_pub_ts(item),
                    dynamic_start_ts=eff_start,
                    dynamic_end_ts=dynamic_end_ts,
                )
                if window == "before":
                    reached_before_window = True
                    break
                if window == "after":
                    continue
            try:
                nodes_with_src = _collect_rich_text_nodes_with_source(item)
                nodes = [n for n, _ in nodes_with_src]
                item_id = str(item.get("id_str") or "")
                is_wanted_dynamic = bool(
                    wanted_dynamic_ids and item_id in wanted_dynamic_ids
                )
                photo_url = _first_dyn_draw_src(item) or ""
                if not nodes:
                    continue
                if not cache_only and not photo_url and not is_wanted_dynamic:
                    continue
                is_collab = _dynamic_is_collaboration(item, collab_activity_re)
                if is_collab:
                    collab_gacha_pools |= _extract_collab_gacha_pools_from_nodes(nodes)
                side_story = _extract_side_story_from_nodes(nodes)
                refresh_scan_activity_cache(scan_ctx, nodes)
                if (
                    cache_only
                    and scan_ctx is not None
                    and (scan_ctx.cached_side_story or "").startswith("SideStory")
                ):
                    reached_before_window = True
                    break
                if cache_only:
                    continue
                matched_wanted_announce = False
                for node, from_forward in nodes_with_src:
                    if from_forward:
                        continue
                    text = node.get("orig_text") or ""
                    parsed = _try_parse_announce_text(text, announce_line_re)
                    if not parsed:
                        continue
                    gacha_pool, name = parsed
                    diag["announce_hits"] += 1
                    hit = _AnnounceHit(
                        name=name,
                        text=text,
                        item=item,
                        photo_url=photo_url,
                        gacha_pool=gacha_pool,
                        is_collab=is_collab,
                        side_story=side_story,
                        collab_gacha_pools=set(collab_gacha_pools),
                    )
                    if is_wanted_dynamic:
                        matched_wanted_announce = True
                    if not on_hit(hit):
                        return diag
                if is_wanted_dynamic and not matched_wanted_announce:
                    log_warning(
                        "bilibili_wanted_dynamic_no_announce id=%s",
                        item_id,
                    )
            except Exception as exc:
                diag["skipped_exceptions"] += 1
                log_warning(
                    "bilibili_scan_item_error id=%s err=%s",
                    item.get("id_str"),
                    exc,
                )

        if reached_before_window:
            break
        offset = dynamics.get("offset")
        if not offset:
            break
        dynamics = fetch_user_dynamics(mid, headers, offset, log_warning=log_warning)

    return diag


def discover_operator_names_from_bilibili(
    mid: str,
    headers: dict[str, str],
    *,
    announce_line_re: re.Pattern[str],
    collab_activity_re: re.Pattern[str] | None,
    character_num: int | None,
    dynamic_start_ts: int | None,
    dynamic_end_ts: int | None,
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
    scan_ctx: BilibiliScanContext | None = None,
) -> list[str]:
    """仅扫描动态拿干员名列表（不下载图、不 OCR）。character_num=None 表示不限制人数（按活动时间窗）。"""
    if scan_ctx is not None:
        _prefill_activity_cache_from_feed(
            mid,
            headers,
            scan_ctx,
            announce_line_re=announce_line_re,
            collab_activity_re=collab_activity_re,
            dynamic_start_ts=dynamic_start_ts,
            dynamic_end_ts=dynamic_end_ts,
            log_warning=log_warning,
            log_info=log_info,
        )

    names: list[str] = []
    seen: set[str] = set()
    unlimited = character_num is None

    def on_hit(hit: _AnnounceHit) -> bool:
        nm = (hit.name or "").strip()
        _remember_discovered_announce(scan_ctx, hit)
        if nm and nm not in seen:
            seen.add(nm)
            names.append(nm)
        if unlimited:
            return True
        return len(seen) < character_num

    diag = _scan_announces(
        mid,
        headers,
        announce_line_re=announce_line_re,
        collab_activity_re=collab_activity_re,
        character_num=character_num,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        log_warning=log_warning,
        log_info=log_info,
        on_hit=on_hit,
        scan_ctx=scan_ctx,
    )
    log_info(
        "bilibili_discover_names count=%s names=%s announce_hits=%s",
        len(names),
        names,
        diag.get("announce_hits"),
    )
    if not names:
        log_warning(
            "bilibili_discover_names_empty pages=%s items_total=%s",
            diag.get("pages"),
            diag.get("items_total"),
        )
    if scan_ctx is not None:
        scan_ctx.discover_feed_pages = int(diag.get("pages") or 0)
    if unlimited:
        return names
    return names[: character_num]


def _resolve_fetch_target_key(hit_name: str, targets: set[str]) -> str | None:
    from data.db.supplementary_repo import resolve_supplementary_batch_key

    hit_name = (hit_name or "").strip()
    if not hit_name:
        return None
    key = resolve_supplementary_batch_key(hit_name, targets)
    if key:
        return key
    stripped_targets = {(t or "").strip() for t in targets if (t or "").strip()}
    return resolve_supplementary_batch_key(hit_name, stripped_targets)


def _resolve_fetch_target_key_for_hit(
    hit: _AnnounceHit,
    targets: set[str],
    scan_ctx: BilibiliScanContext | None,
) -> str | None:
    """发现阶段已记下动态 id 时，按 id 对齐目标名，避免预告名解析偏差。"""
    sid = str(hit.item.get("id_str") or "")
    if scan_ctx and sid:
        for t in targets:
            key = (t or "").strip()
            if key and scan_ctx.discovered_dynamic_ids.get(key) == sid:
                return key
    return _resolve_fetch_target_key(hit.name, targets)


def fetch_character_supplementary_for_names(
    mid: str,
    headers: dict[str, str],
    target_names: set[str] | list[str],
    *,
    announce_line_re: re.Pattern[str],
    acquisition_method: dict[str, str],
    collab_activity_re: re.Pattern[str] | None,
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
    scan_ctx: BilibiliScanContext | None = None,
) -> dict[str, dict[str, Any]]:
    """仅对 target_names 中的干员完整抓取（含 OCR）。"""
    targets = set(target_names)
    if not targets:
        return {}

    if scan_ctx is not None:
        _prefill_activity_cache_from_feed(
            mid,
            headers,
            scan_ctx,
            announce_line_re=announce_line_re,
            collab_activity_re=collab_activity_re,
            dynamic_start_ts=dynamic_start_ts,
            dynamic_end_ts=dynamic_end_ts,
            log_warning=log_warning,
            log_info=log_info,
        )

    pool_view, pool_limited_ops = _load_pool_view(mid, headers)
    result: dict[str, dict[str, Any]] = {}
    scan_limit = max(len(targets) * 3, len(targets))

    def on_hit(hit: _AnnounceHit) -> bool:
        target_key = _resolve_fetch_target_key_for_hit(hit, targets, scan_ctx)
        if not target_key or target_key in result:
            return len(result) < len(targets)
        character = _build_character_from_hit(
            hit,
            pool_view=pool_view,
            pool_limited_ops=pool_limited_ops,
            acquisition_method=acquisition_method,
            run_ocr=True,
            log_warning=log_warning,
            log_info=log_info,
            scan_ctx=scan_ctx,
        )
        result[target_key] = character
        if target_key != hit.name:
            log_info(
                "bilibili_fetch_name_alias hit=%s target=%s 画师=%s",
                hit.name,
                target_key,
                (character.get("画师") or "")[:60],
            )
        log_info("bilibili_fetch_one name=%s fields=%s", target_key, list(character.keys()))
        return len(result) < len(targets)

    diag = _scan_announces(
        mid,
        headers,
        announce_line_re=announce_line_re,
        collab_activity_re=collab_activity_re,
        character_num=scan_limit,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        log_warning=log_warning,
        log_info=log_info,
        on_hit=on_hit,
        scan_ctx=scan_ctx,
        fetch_targets=targets,
    )
    missing = sorted(targets - set(result.keys()))
    if missing:
        hints = []
        if scan_ctx is not None:
            for nm in missing:
                sid = scan_ctx.discovered_dynamic_ids.get((nm or "").strip())
                if sid:
                    hints.append(f"{nm}@{sid}")
        log_warning(
            "bilibili_fetch_incomplete missing=%s pages=%s announce_hits=%s discover_ids=%s",
            missing,
            diag.get("pages"),
            diag.get("announce_hits"),
            hints or None,
        )
    return result


__all__ = [
    "BilibiliScanContext",
    "discover_operator_names_from_bilibili",
    "fetch_character_supplementary_for_names",
]
