"""干员模板 CLI（与 GUI 共用 pipeline）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.script_logging import script_print as print

from .gui_markers import strip_ark_gui_operator_markers
from .pipeline import run_character_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="干员模板脚本（CLI；入口 arknights_toolbox.core.character_script）"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config.json",
        help="配置路径；相对路径在 config/、项目根、cwd 下查找（见 data.config_loader）",
    )
    parser.add_argument(
        "--data-source",
        default=None,
        help="config.data_sources 顶层键，如 Kengxxiao/ArknightsGameData；省略时交互终端下标选择，非 tty 取第一项",
    )
    parser.add_argument(
        "--operator",
        default=None,
        help="仅生成指定干员（支持干员名或 charId）",
    )
    parser.add_argument(
        "--summon-charid",
        default=None,
        help="仅生成指定附属单位模板（传附属单位 charId / overrideTokenKey）",
    )
    parser.add_argument("--out", "-o", default=None, help="输出文件路径（若不指定则打印到 stdout）")
    parser.add_argument(
        "--log-file",
        default=None,
        help="日志文件路径（默认: log/YYYY-MM-DD.log，追加写入）",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="不写日志文件，仅控制台输出",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="控制台不显示 DEBUG 级别（文件仍为 DEBUG，便于排错）",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="不对 Wiki 逐项询问；由 --wiki-* 开关决定（适合自动化 / GUI 对齐）",
    )
    parser.add_argument(
        "--wiki-operator-page",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="非交互模式下是否创建干员页 / 召唤物页（默认：开）",
    )
    parser.add_argument(
        "--wiki-voice-page",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="非交互模式下是否创建语音页（默认：开）",
    )
    parser.add_argument(
        "--wiki-portrait",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="非交互模式下是否上传半身像（默认：关）",
    )
    parser.add_argument(
        "--wiki-test-page",
        dest="wiki_use_test_page",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Wiki 文本写入目标：开启时写入当前用户沙盒「用户:用户名/测试页」；"
            "关闭请用 --no-wiki-test-page，按真实词条标题写入（默认开启）"
        ),
    )
    args = parser.parse_args()

    wiki_flags = {
        "wiki_operator_page": args.wiki_operator_page,
        "wiki_voice_page": args.wiki_voice_page,
        "wiki_portrait": args.wiki_portrait,
    }

    voice_json: dict = {}

    try:
        tpl = run_character_pipeline(
            config_path=args.config,
            data_source_group=args.data_source,
            operator_filter=args.operator,
            wiki_flags=wiki_flags,
            voice_json=voice_json,
            log_path=args.log_file,
            no_log_file=args.no_log_file,
            quiet=args.quiet,
            interactive=not args.no_interactive,
            wiki_use_test_page=args.wiki_use_test_page,
            summon_charid=args.summon_charid,
        )
    except Exception:
        sys.exit(1)

    out_text = strip_ark_gui_operator_markers(tpl)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
