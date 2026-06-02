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
    _collect_rich_text_nodes_with_source,
    _dynamic_in_activity_window,
    _dynamic_is_collaboration,
    _dynamic_pub_ts,
    _effective_dynamic_start,
    _extract_collab_gacha_pools_from_nodes,
    _extract_limited_operators_from_article_summary,
    _extract_side_story_from_nodes,
    _first_dyn_draw_src,
    _is_limited_operator_in_pool,
    _obtain_path_for_gacha_pool,
    fetch_user_dynamics,
    get_dynamic_id,
    operator_photo_dir,
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
        if "限定寻访" not in article.get("title", ""):
            continue
        data = [article["title"][1:8]]
        left = article["title"].find("【")
        right = article["title"].find("】")
        ltime = article["summary"].find("活动时间：")
        rtime = article["summary"].find("日")
        data.append(article["summary"][ltime + 5 : rtime + 1])
        pool_key = article["title"][left + 1 : right]
        pool_view[pool_key] = data
        pool_limited_ops[pool_key] = _extract_limited_operators_from_article_summary(
            article.get("summary") or ""
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

    pools = hit.collab_gacha_pools
    in_collab_event = hit.is_collab or bool(pools)
    named_collab_pool = bool(
        gacha_pool
        and gacha_pool not in ("新增干员", "活动奖励干员")
        and (hit.is_collab or gacha_pool in pools)
    )
    collab_standard_pool = bool(
        gacha_pool in ("新增干员", "活动奖励干员") and in_collab_event
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
        character["获取途径"] = _obtain_path_for_gacha_pool(
            gacha_pool, acquisition_method, side_story=hit.side_story
        )
    elif implementation_data is not None:
        if implementation_data[1] and implementation_data[1][0] == "0":
            implementation_data = [implementation_data[0], implementation_data[1][1:]]
        release_time = implementation_data[1]
        prefix = acquisition_method.get(implementation_data[0])
        limited_in_pool = pool_limited_ops.get(gacha_pool, set())
        if prefix is not None:
            if not limited_in_pool or _is_limited_operator_in_pool(name, limited_in_pool):
                character["获取途径"] = prefix + f"{gacha_pool}】限定寻访"
                dynamic_id = get_dynamic_id(name)
                if dynamic_id:
                    character["动态id"] = dynamic_id
            else:
                character["获取途径"] = acquisition_method.get("新增干员", "标准寻访")
    else:
        character["获取途径"] = _obtain_path_for_gacha_pool(
            gacha_pool, acquisition_method, side_story=hit.side_story
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

    while True:
        if not dynamics or not isinstance(dynamics, dict):
            break
        diag["pages"] += 1
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
                photo_url = _first_dyn_draw_src(item)
                if not nodes or not photo_url:
                    continue
                is_collab = _dynamic_is_collaboration(item, collab_activity_re)
                if is_collab:
                    collab_gacha_pools |= _extract_collab_gacha_pools_from_nodes(nodes)
                side_story = _extract_side_story_from_nodes(nodes)
                for node, from_forward in nodes_with_src:
                    if from_forward:
                        continue
                    text = node.get("orig_text") or ""
                    if not announce_line_re.match(text):
                        continue
                    diag["announce_hits"] += 1
                    gacha_pool = text[text.find("【") + 1 : text.find("】")]
                    start = text.find("//")
                    end = text.find("\n", start)
                    name = text[start + 2 : end]
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
                    if not on_hit(hit):
                        return diag
            except Exception:
                diag["skipped_exceptions"] += 1

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
    character_num: int,
    dynamic_start_ts: int | None,
    dynamic_end_ts: int | None,
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
) -> list[str]:
    """仅扫描动态拿干员名列表（不下载图、不 OCR）。"""
    names: list[str] = []
    seen: set[str] = set()

    def on_hit(hit: _AnnounceHit) -> bool:
        if hit.name not in seen:
            seen.add(hit.name)
            names.append(hit.name)
        return len(names) < character_num

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
    return names[:character_num]


def _resolve_fetch_target_key(hit_name: str, targets: set[str]) -> str | None:
    from data.db.supplementary_repo import resolve_supplementary_batch_key

    return resolve_supplementary_batch_key(hit_name, targets)


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
) -> dict[str, dict[str, Any]]:
    """仅对 target_names 中的干员完整抓取（含 OCR）。"""
    targets = set(target_names)
    if not targets:
        return {}

    pool_view, pool_limited_ops = _load_pool_view(mid, headers)
    result: dict[str, dict[str, Any]] = {}
    scan_limit = max(len(targets) * 3, len(targets))

    def on_hit(hit: _AnnounceHit) -> bool:
        target_key = _resolve_fetch_target_key(hit.name, targets)
        if not target_key or target_key in result:
            return len(result) < len(targets)
        character = _build_character_from_hit(
            hit,
            pool_view=pool_view,
            pool_limited_ops=pool_limited_ops,
            acquisition_method=acquisition_method,
            run_ocr=True,
            log_warning=log_warning,
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
    )
    missing = sorted(targets - set(result.keys()))
    if missing:
        log_warning(
            "bilibili_fetch_incomplete missing=%s pages=%s announce_hits=%s",
            missing,
            diag.get("pages"),
            diag.get("announce_hits"),
        )
    return result


__all__ = [
    "discover_operator_names_from_bilibili",
    "fetch_character_supplementary_for_names",
]
