"""干员补充数据：B 站发现名单 → 按人查库补缺 → 仅对缺口完整抓取 B 站。"""



from __future__ import annotations



from typing import Any, Callable



from core.script_logging import log_info, log_warning, script_print as print

from data.db import (

    OperatorSupplementaryRepository,

    apply_db_with_bili_meta,

    apply_bili_ocr_over_empty,

    merge_supplementary,

    merge_supplementary_bilibili_first,

    is_supplementary_complete,

    empty_supplementary_dict,

    has_meaningful_supplementary,

    lookup_supplementary_in_batch,

    needs_supplementary_fetch,

    missing_supplementary_fields,

    supplementary_for_upsert,
    supplementary_payload_changed,

)

from data.db.engine import resolve_database_settings

from shared.collab_supplementary import apply_collab_period_supplementary_meta, enrich_collab_meta
from shared.services.bilibili_service import (
    BilibiliScanContext,
    apply_gui_activity_obtain_path,
)



from .bilibili_bridge import (
    ANNOUNCE_LINE_RE,
    COLLAB_ACTIVITY_RE,
    discover_operator_names,
    fetch_supplementary_for_names,
)


def _bind_scan_ctx(
    fetch_fn: Callable,
    scan_ctx: BilibiliScanContext | None,
) -> Callable:
    if scan_ctx is None:
        return fetch_fn

    def wrapped(
        mid: str,
        headers: dict,
        names: set[str] | list[str],
        *,
        dynamic_start_ts: int | None = None,
        dynamic_end_ts: int | None = None,
    ):
        return fetch_fn(
            mid,
            headers,
            names,
            dynamic_start_ts=dynamic_start_ts,
            dynamic_end_ts=dynamic_end_ts,
            scan_ctx=scan_ctx,
        )

    return wrapped

from .mapper_ops import (
    collect_cid_name_pairs,
    resolve_operator_char_id_for_name,
)





def _match_operator_names(mapper, operator_filter: str) -> list[str]:

    selected_lower = operator_filter.strip().lower()

    matched: list[str] = []

    for _cid, name in collect_cid_name_pairs(mapper):

        if (

            name.lower() == selected_lower

            or selected_lower in name.lower()

            or _cid.lower() == selected_lower

        ):

            matched.append(name)

    return matched





def _warm_collab_scan_cache(
    mid: str,
    headers: dict,
    scan_ctx: BilibiliScanContext | None,
    *,
    dynamic_start_ts: int | None,
    dynamic_end_ts: int | None,
) -> None:
    """指定 GUI 联动活动时预扫 feed，填充 cached_collab_gacha_pools（单干员路径也走）。"""
    if scan_ctx is None:
        return
    if not (scan_ctx.gui_activity_name or "").strip():
        return
    from shared.services.bilibili_supplementary_fetch import (
        _prefill_collab_gacha_pools_from_feed,
    )

    _prefill_collab_gacha_pools_from_feed(
        mid,
        headers,
        scan_ctx,
        announce_line_re=ANNOUNCE_LINE_RE,
        collab_activity_re=COLLAB_ACTIVITY_RE,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        log_warning=log_warning,
        log_info=log_info,
    )


def _has_activity_time_filter(

    dynamic_start_ts: int | None,

    dynamic_end_ts: int | None,

) -> bool:

    return dynamic_start_ts is not None or dynamic_end_ts is not None





def _discover_names_from_bilibili(

    *,

    settings: dict,

    use_db: bool,

    repo: OperatorSupplementaryRepository,

    mid: str,

    headers: dict,

    character_num: int,

    dynamic_start_ts: int | None,

    dynamic_end_ts: int | None,

    fetch_bilibili: Callable,

    has_activity_filter: bool,

    scan_ctx: BilibiliScanContext | None = None,

) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """
    名单始终优先从 B 站动态发现（仅解析预告行，不 OCR）。
    B 站为空时回退库内完整记录名；不预取 bili_batch。
    """
    del fetch_bilibili  # 保留签名兼容

    # 按活动筛动态时与「干员数量」互斥：收集时间窗内全部预告干员
    discover_limit: int | None = None if has_activity_filter else character_num

    names: list[str] = []
    if settings["fallback_bilibili"]:
        names = discover_operator_names(
            mid,
            headers,
            discover_limit,
            dynamic_start_ts=dynamic_start_ts,
            dynamic_end_ts=dynamic_end_ts,
            scan_ctx=scan_ctx,
        )

    if not names and use_db:
        if has_activity_filter:
            log_warning(
                "活动窗口内 B 站未发现干员预告，无法按活动批量（请检查活动时间或改按干员数量）"
            )
        else:
            names = repo.list_complete_names(character_num, settings["required_fields"])[
                :character_num
            ]
            if names:
                log_warning(
                    "B 站未发现干员预告，回退数据库名单 %s 条",
                    len(names),
                )
    elif names:
        if has_activity_filter:
            log_info("名单来自 B 站动态（活动窗口内全部预告）%s 人", len(names))
        else:
            log_info("名单来自 B 站动态（仅发现名）%s 人", len(names))

    if discover_limit is None:
        return names, {}
    return names[:discover_limit], {}





def resolve_supplementary_data(

    mapper,

    *,

    operator_filter: str | None,

    voice_json: Any,

    mid: str,

    headers: dict,

    character_num: int,

    dynamic_start_ts: int | None,

    dynamic_end_ts: int | None,

    fetch_bilibili_fn: Callable | None = None,

    activity_name: str | None = None,

    activity_is_main_theme: bool = False,

    force_bilibili_fetch: bool = False,

) -> dict[str, dict[str, Any]]:

    """

    返回 {干员名: {获取途径, 实装日期, ...}}。



    批量且未指定活动：先请求 B 站拿最新干员名；本批 B 站有数据的干员以 B 站为准合并。

    指定干员：本批无 B 站数据时库完整则用库，否则与 B 站合并。

    """

    settings = resolve_database_settings(mapper.config)

    repo = OperatorSupplementaryRepository(

        mapper.config,

        config_path=getattr(mapper, "config_path", None),

    )

    use_db = repo.available and settings["prefer_db"]

    required = settings["required_fields"]

    fetch_bilibili = fetch_bilibili_fn or fetch_supplementary_for_names
    fill_fields = settings.get("fill_fields") or required

    has_activity_filter = _has_activity_time_filter(dynamic_start_ts, dynamic_end_ts)

    scan_ctx: BilibiliScanContext | None = None
    if settings["fallback_bilibili"]:
        scan_ctx = BilibiliScanContext(
            gui_activity_name=(activity_name or "").strip() or None,
            gui_activity_is_main_theme=bool(activity_is_main_theme),
            gui_activity_start_ts=(
                dynamic_start_ts
                if (activity_name or "").strip() and dynamic_start_ts is not None
                else None
            ),
            gui_activity_end_ts=(
                dynamic_end_ts
                if (activity_name or "").strip() and dynamic_end_ts is not None
                else None
            ),
        )
    fetch_bilibili = _bind_scan_ctx(fetch_bilibili, scan_ctx)



    selected = (operator_filter or "").strip()



    if selected:

        matched_names = _match_operator_names(mapper, selected)

        if not matched_names:

            log_warning("未匹配到指定干员：%s", selected)

            return {}

        return _resolve_for_names(

            mapper,

            matched_names,

            repo=repo,

            use_db=use_db,

            settings=settings,

            required=required,

            fill_fields=fill_fields,

            mid=mid,

            headers=headers,

            character_num=character_num,

            dynamic_start_ts=dynamic_start_ts,

            dynamic_end_ts=dynamic_end_ts,

            fetch_bilibili=fetch_bilibili,

            activity_name=activity_name,

            activity_is_main_theme=activity_is_main_theme,

            scan_ctx=scan_ctx,

            force_bilibili_fetch=force_bilibili_fetch,

        )



    if voice_json != {}:

        return {}



    names, bili_batch = _discover_names_from_bilibili(

        settings=settings,

        use_db=use_db,

        repo=repo,

        mid=mid,

        headers=headers,

        character_num=character_num,

        dynamic_start_ts=dynamic_start_ts,

        dynamic_end_ts=dynamic_end_ts,

        fetch_bilibili=fetch_bilibili,

        has_activity_filter=has_activity_filter,

        scan_ctx=scan_ctx,

    )

    if not names:

        log_info("无可用干员补充数据（B 站为空且库中无完整记录）")

        return {}



    if not settings["fallback_bilibili"] and not use_db:

        log_warning("数据库未启用且 fallback_bilibili=false，无补充数据")

        return {}



    return _resolve_for_names(

        mapper,

        names,

        repo=repo,

        use_db=use_db,

        settings=settings,

        required=required,

        fill_fields=fill_fields,

        mid=mid,

        headers=headers,

        character_num=character_num,

        dynamic_start_ts=dynamic_start_ts,

        dynamic_end_ts=dynamic_end_ts,

        fetch_bilibili=fetch_bilibili,

        bili_prefetch=bili_batch,

        activity_name=activity_name,

        activity_is_main_theme=activity_is_main_theme,

        scan_ctx=scan_ctx,

        force_bilibili_fetch=force_bilibili_fetch,

    )

def _resolve_for_names(

    mapper,

    names: list[str],

    *,

    repo: OperatorSupplementaryRepository,

    use_db: bool,

    settings: dict,

    required: list[str],

    fill_fields: list[str],

    mid: str,

    headers: dict,

    character_num: int,

    dynamic_start_ts: int | None,

    dynamic_end_ts: int | None,

    fetch_bilibili: Callable,

    bili_prefetch: dict[str, dict[str, Any]] | None = None,

    activity_name: str | None = None,

    activity_is_main_theme: bool = False,

    scan_ctx: BilibiliScanContext | None = None,

    force_bilibili_fetch: bool = False,

) -> dict[str, dict[str, Any]]:
    del bili_prefetch, character_num  # 不再使用 discover 阶段预取
    gui_activity = (activity_name or "").strip() or None
    _warm_collab_scan_cache(
        mid,
        headers,
        scan_ctx,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
    )

    result: dict[str, dict[str, Any]] = {}
    need_fetch: list[str] = []
    cid_by_name: dict[str, str | None] = {}

    for name in names:
        db_part = None
        cid = None
        if use_db:
            stored_cid = repo.get_char_id_by_name(name)
            cid = resolve_operator_char_id_for_name(
                mapper, name, stored_char_id=stored_cid
            )
            cid_by_name[name] = cid
            db_part = repo.get_by_name(name)
            if db_part is None and cid:
                db_part = repo.get_by_char_id(cid)

        if use_db and db_part and not force_bilibili_fetch and not needs_supplementary_fetch(db_part, fill_fields):
            merged = enrich_collab_meta(apply_db_with_bili_meta(db_part, None))
            merged = apply_collab_period_supplementary_meta(merged, scan_ctx)
            if gui_activity:
                merged = apply_gui_activity_obtain_path(
                    merged,
                    gui_activity,
                    gui_activity_is_main_theme=activity_is_main_theme,
                )
            result[name] = merged
            missing = missing_supplementary_fields(db_part, fill_fields)
            log_info(
                "补充数据来自数据库：%s（跳过 B 站抓取，fill 已齐 missing=%s）",
                name,
                missing,
            )
            if (
                use_db
                and settings["write_after_fallback"]
                and has_meaningful_supplementary(merged)
                and supplementary_payload_changed(merged, db_part)
            ):
                stored_now = repo.get_char_id_by_name(name)
                cid = cid_by_name.get(name) or resolve_operator_char_id_for_name(
                    mapper, name, stored_char_id=stored_now
                )
                repo.upsert(
                    name,
                    supplementary_for_upsert(merged),
                    char_id=cid,
                    clear_char_id=bool(stored_now) and not cid,
                    source="gui_reconcile",
                )
            continue
        need_fetch.append(name)

    bili_batch: dict[str, dict[str, Any]] = {}
    if need_fetch and settings["fallback_bilibili"]:
        log_info("B 站完整抓取 %s 人（缺记录或缺字段）: %s", len(need_fetch), need_fetch)
        bili_batch = (
            fetch_bilibili(
                mid,
                headers,
                need_fetch,
                dynamic_start_ts=dynamic_start_ts,
                dynamic_end_ts=dynamic_end_ts,
            )
            or {}
        )

    for name in names:
        if name in result:
            continue
        db_part = None
        if use_db:
            db_part = repo.get_by_name(name)
            cid = cid_by_name.get(name)
            if db_part is None and cid:
                db_part = repo.get_by_char_id(cid)

        _bili_key, bili_part_raw = lookup_supplementary_in_batch(bili_batch, name)
        bili_part = bili_part_raw or empty_supplementary_dict()
        if _bili_key and _bili_key != name:
            log_info("补充数据 B 站键对齐 name=%s bili_key=%s", name, _bili_key)
        if name in need_fetch and not has_meaningful_supplementary(bili_part):
            log_warning(
                "B 站未抓到有效补充数据 name=%s，将保留库内已有字段（若有）",
                name,
            )
        if db_part and has_meaningful_supplementary(db_part):
            merged = merge_supplementary(db_part, bili_part)
        elif has_meaningful_supplementary(bili_part):
            merged = merge_supplementary_bilibili_first(db_part, bili_part)
        else:
            merged = merge_supplementary(db_part, bili_part)
        merged = apply_bili_ocr_over_empty(merged, bili_part)
        merged = enrich_collab_meta(merged)
        merged = apply_collab_period_supplementary_meta(merged, scan_ctx)
        if gui_activity:
            merged = apply_gui_activity_obtain_path(
                merged,
                gui_activity,
                gui_activity_is_main_theme=activity_is_main_theme,
            )
        result[name] = merged

        sources: list[str] = []
        if db_part and has_meaningful_supplementary(db_part):
            sources.append("db")
        if has_meaningful_supplementary(bili_part):
            sources.append("bilibili")
        log_info(
            "补充数据合并 name=%s sources=%s fill_missing=%s complete=%s",
            name,
            "+".join(sources) or "empty",
            missing_supplementary_fields(merged, fill_fields),
            is_supplementary_complete(merged, required),
        )

        if use_db and settings["write_after_fallback"] and has_meaningful_supplementary(merged):
            stored_now = repo.get_char_id_by_name(name) if use_db else None
            cid = cid_by_name.get(name)
            if cid is None:
                cid = resolve_operator_char_id_for_name(
                    mapper, name, stored_char_id=stored_now
                )
            source = "bilibili" if has_meaningful_supplementary(bili_part) else "db"
            repo.upsert(
                name,
                supplementary_for_upsert(merged),
                char_id=cid,
                clear_char_id=bool(stored_now) and not cid,
                source=source,
            )

    return result


