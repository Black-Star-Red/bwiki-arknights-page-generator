"""干员生成流水线入口（GUI / CLI 共用）。"""

from __future__ import annotations

import time
import uuid
from typing import Callable

from data import DataMapper

from core.script_logging import (
    default_log_path,
    script_log,
    setup_script_logger,
)

from .generate_operator_template import generate_template
from .summon_template import generate_summon_template_by_charid


def run_character_pipeline(
    *,
    config_path: str,
    data_source_group: str | None,
    operator_filter: str | None = None,
    wiki_flags: dict | None,
    voice_json=None,
    log_path=None,
    no_log_file: bool = False,
    quiet: bool = False,
    interactive: bool = True,
    wiki_use_test_page: bool = True,
    wiki_confirm: Callable[[str, str], bool] | None = None,
    character_num: int = 3,
    summon_charid: str | None = None,
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
) -> str:
    """
    供 GUI 与 CLI 共用的执行入口：配置日志 → DataMapper → generate_template。
    interactive=False 时：先按 wiki_flags 过滤；若传入 wiki_confirm，则在每次写入前再询问。
    """
    if voice_json is None:
        voice_json = {}
    if no_log_file:
        eff_log = None
    else:
        eff_log = log_path or default_log_path()
    debug = not quiet
    setup_script_logger(eff_log, quiet)
    run_id = uuid.uuid4().hex[:8]
    started_at = time.time()
    script_log.info("run_start run_id=%s log_file=%s debug=%s", run_id, eff_log, debug)

    mapper = None
    try:
        mapper = DataMapper.from_file(
            config_path,
            debug=debug,
            log_path=eff_log,
            data_source_group=data_source_group,
        )
        mapper.set_run_context(run_id)
        script_log.info("数据映射器初始化成功 source=%s", getattr(mapper, "current_data_sources", None))
    except Exception:
        script_log.exception("数据映射器初始化失败")
        raise

    try:
        script_log.info("stage_start run_id=%s stage=generate_template", run_id)
        if summon_charid:
            tpl = generate_summon_template_by_charid(mapper, summon_charid)
        else:
            tpl = generate_template(
                voice_json,
                mapper,
                operator_filter=operator_filter,
                wiki_flags=wiki_flags,
                interactive=interactive,
                wiki_use_test_page=wiki_use_test_page,
                wiki_confirm=wiki_confirm,
                character_num=character_num,
                dynamic_start_ts=dynamic_start_ts,
                dynamic_end_ts=dynamic_end_ts,
            )
        script_log.info("stage_end run_id=%s stage=generate_template output_len=%d", run_id, len(tpl or ""))
        return tpl or ""
    except Exception:
        script_log.exception("stage_error run_id=%s stage=generate_template", run_id)
        raise
    finally:
        if mapper is not None:
            mapper.flush_missing_path_summary()
        elapsed_ms = int((time.time() - started_at) * 1000)
        script_log.info("run_end run_id=%s elapsed_ms=%d", run_id, elapsed_ms)
