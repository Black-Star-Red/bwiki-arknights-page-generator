"""干员补充数据：B 站发现名单，库内命中则用库，否则 B 站合并。"""



from __future__ import annotations



from typing import Any, Callable



from core.script_logging import log_info, log_warning, script_print as print

from data.db import (

    OperatorSupplementaryRepository,

    apply_db_with_bili_meta,

    merge_supplementary,

    merge_supplementary_bilibili_first,

    is_supplementary_complete,

    empty_supplementary_dict,

    has_meaningful_supplementary,

)

from data.db.engine import resolve_database_settings



from .bilibili_bridge import get_character_supplementary_data

from .mapper_ops import (
    collect_cid_name_pairs,
    find_char_id_by_name,
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

) -> tuple[list[str], dict[str, dict[str, Any]]]:

    """

    用 B 站动态发现待处理干员名；B 站为空时再回退库内完整记录名单。



    未指定活动时间时：仅以 B 站最新动态名单为准（不先用库名单顶替 B 站请求）。

    """

    bili_batch: dict[str, dict[str, Any]] = {}
    db_names: list[str] = (
        repo.list_complete_names(character_num, settings["required_fields"]) if use_db else []
    )

    skip_bili_discover = (
        not has_activity_filter
        and use_db
        and settings.get("skip_bilibili_discover_if_db_complete", True)
        and len(db_names) >= character_num
        and settings["fallback_bilibili"]
    )

    if skip_bili_discover:
        log_info(
            "数据库已有 %s 条完整补充记录（≥%s），跳过 B 站发现/OCR，名单来自库",
            len(db_names),
            character_num,
        )
    elif settings["fallback_bilibili"]:
        bili_batch = (
            fetch_bilibili(
                mid,
                headers,
                character_num,
                dynamic_start_ts=dynamic_start_ts,
                dynamic_end_ts=dynamic_end_ts,
            )
            or {}
        )

    if not has_activity_filter:
        if skip_bili_discover:
            names = db_names[:character_num]
        else:
            names = list(bili_batch.keys())[:character_num]

        if not names and use_db:

            names = repo.list_complete_names(character_num, settings["required_fields"])[

                :character_num

            ]

            if names:

                log_warning(

                    "B 站未发现干员（动态 feed 为空或未匹配干员预告），回退数据库名单 %s 条；"

                    "请查看上一条 supplementary_data_empty / bilibili_feed_empty 日志",

                    len(names),

                )

        elif names:

            log_info(

                "名单来自 B 站动态 %s 人（本批有 B 站数据则以 B 站为准）",

                len(names),

            )

        return names, bili_batch



    names = list(dict.fromkeys([*bili_batch.keys(), *db_names]))[:character_num]

    return names, bili_batch





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

    fetch_bilibili = fetch_bilibili_fn or get_character_supplementary_data

    has_activity_filter = _has_activity_time_filter(dynamic_start_ts, dynamic_end_ts)



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

            mid=mid,

            headers=headers,

            character_num=character_num,

            dynamic_start_ts=dynamic_start_ts,

            dynamic_end_ts=dynamic_end_ts,

            fetch_bilibili=fetch_bilibili,

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

        mid=mid,

        headers=headers,

        character_num=character_num,

        dynamic_start_ts=dynamic_start_ts,

        dynamic_end_ts=dynamic_end_ts,

        fetch_bilibili=fetch_bilibili,

        bili_prefetch=bili_batch,

    )





def _resolve_for_names(

    mapper,

    names: list[str],

    *,

    repo: OperatorSupplementaryRepository,

    use_db: bool,

    settings: dict,

    required: list[str],

    mid: str,

    headers: dict,

    character_num: int,

    dynamic_start_ts: int | None,

    dynamic_end_ts: int | None,

    fetch_bilibili: Callable,

    bili_prefetch: dict[str, dict[str, Any]] | None = None,

) -> dict[str, dict[str, Any]]:

    result: dict[str, dict[str, Any]] = {}

    need_bili: list[str] = []

    bili_batch = bili_prefetch if bili_prefetch is not None else {}



    for name in names:

        db_part = None

        if use_db:

            stored_cid = repo.get_char_id_by_name(name)
            cid = resolve_operator_char_id_for_name(
                mapper, name, stored_char_id=stored_cid
            )

            db_part = repo.get_by_name(name)

            if db_part is None and cid:

                db_part = repo.get_by_char_id(cid)

            if db_part and is_supplementary_complete(db_part, required):

                bili_part = bili_batch.get(name)

                if name in bili_batch and has_meaningful_supplementary(bili_part or {}):

                    merged = merge_supplementary_bilibili_first(db_part, bili_part)

                    result[name] = merged

                    log_info("补充数据 B 站优先合并：%s", name)

                    if use_db and settings["write_after_fallback"]:

                        repo.upsert(name, merged, char_id=cid, source="bilibili")

                    continue

                result[name] = apply_db_with_bili_meta(db_part, bili_part)

                log_info(

                    "补充数据来自数据库：%s（%s）",

                    name,

                    "无本批 B 站字段" if name in bili_batch else "仅本地/指定",

                )

                continue

        need_bili.append(name)



    if need_bili and settings["fallback_bilibili"] and not bili_batch:

        bili_batch = (

            fetch_bilibili(

                mid,

                headers,

                character_num,

                dynamic_start_ts=dynamic_start_ts,

                dynamic_end_ts=dynamic_end_ts,

            )

            or {}

        )



    for name in names:

        if name in result:

            continue

        db_part = repo.get_by_name(name) if use_db else None

        stored_cid = repo.get_char_id_by_name(name) if use_db else None
        cid = resolve_operator_char_id_for_name(
            mapper, name, stored_char_id=stored_cid
        )

        if use_db and db_part is None and cid:

            db_part = repo.get_by_char_id(cid)

        bili_part = bili_batch.get(name) or empty_supplementary_dict()

        if name in bili_batch and has_meaningful_supplementary(bili_part):

            merged = merge_supplementary_bilibili_first(db_part, bili_part)

        else:

            merged = merge_supplementary(db_part, bili_part)

        result[name] = merged



        sources: list[str] = []

        if db_part and has_meaningful_supplementary(db_part):

            sources.append("db")

        if has_meaningful_supplementary(bili_part):

            sources.append("bilibili")

        log_info(

            "补充数据合并 name=%s sources=%s complete=%s",

            name,

            "+".join(sources) or "fallback",

            is_supplementary_complete(merged, required),

        )



        if use_db and settings["write_after_fallback"] and has_meaningful_supplementary(merged):

            source = "bilibili" if has_meaningful_supplementary(bili_part) else "db"

            repo.upsert(name, merged, char_id=cid, source=source)



    return result


