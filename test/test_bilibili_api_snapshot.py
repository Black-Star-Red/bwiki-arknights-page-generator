"""
拉取 B 站官方 API 原始 JSON，便于对照动态结构。

用法（任选其一）:
  python test/test_bilibili_api_snapshot.py
  python test/test_bilibili_api_snapshot.py --pages 2
  pytest test/test_bilibili_api_snapshot.py -s

输出目录（默认）:
  test/output/bilibili_api/
    - polymer_feed_page0.json      # 动态 feed 完整响应 {code, message, data}
    - polymer_data_page0.json      # 仅 data 字段
    - space_articles.json          # 专栏/卡池文章列表
    - summary.txt                  # 每条动态摘要（orig_text 等）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import importlib.util

import pytest
import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bili = _load_module("bilibili_service", "shared/services/bilibili_service.py")
_headers_mod = _load_module("request_headers", "shared/services/request_headers.py")

_collect_rich_text_nodes = _bili._collect_rich_text_nodes
_dynamic_pub_ts = _bili._dynamic_pub_ts
_iter_dynamic_modules = _bili._iter_dynamic_modules
fetch_user_dynamics = _bili.fetch_user_dynamics
build_bilibili_headers = _headers_mod.build_bilibili_headers

from data.config_loader import load_config, resolve_config_path

DEFAULT_BILIBILI_MID = "161775300"
try:
    from shared.globals import DEFAULT_BILIBILI_MID as _MID
    DEFAULT_BILIBILI_MID = _MID
except Exception:
    pass

OUTPUT_DIR = _ROOT / "test" / "output" / "bilibili_api"
POLYMER_URL = "https://api.bilibili.com/x/polymer/web-dynamic/desktop/v1/feed/space"
ARTICLE_URL = "https://api.bilibili.com/x/space/article"


def build_snapshot_headers(cookies: str) -> dict[str, str]:
    """
    B 站 API 请求头。勿带 br：未安装 brotli 时 requests 可能得到无法解码的空 body。
    """
    h = build_bilibili_headers(cookies)
    h["Accept-Encoding"] = "gzip, deflate"
    h["Referer"] = f"https://space.bilibili.com/{DEFAULT_BILIBILI_MID}/dynamic"
    h["Origin"] = "https://space.bilibili.com"
    return h


class BilibiliApiResponseError(RuntimeError):
    """非 JSON 或空响应时抛出，并附带诊断信息。"""

    def __init__(self, message: str, *, debug_path: Path | None = None):
        super().__init__(message)
        self.debug_path = debug_path


def _fetch_json(
    url: str,
    *,
    headers: dict,
    params: dict,
    debug_dir: Path | None = None,
    debug_name: str = "response",
) -> dict:
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    text = resp.text or ""
    debug_path = None
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"{debug_name}_http{resp.status_code}.txt"
        debug_path.write_text(
            "\n".join(
                [
                    f"url: {resp.url}",
                    f"status: {resp.status_code}",
                    f"content-type: {resp.headers.get('Content-Type', '')}",
                    f"content-length: {len(resp.content)}",
                    f"body_text_len: {len(text)}",
                    "--- body ---",
                    text[:50000] if text else "(empty)",
                ]
            ),
            encoding="utf-8",
            errors="replace",
        )

    if resp.status_code != 200:
        raise BilibiliApiResponseError(
            f"HTTP {resp.status_code} url={resp.url}（原始响应已写入 {debug_path}）",
            debug_path=debug_path,
        )
    if not text.strip():
        raise BilibiliApiResponseError(
            f"响应体为空 url={resp.url}（检查 Cookie / 是否被风控；见 {debug_path}）",
            debug_path=debug_path,
        )
    try:
        body = resp.json()
    except json.JSONDecodeError as e:
        raise BilibiliApiResponseError(
            f"JSON 解析失败: {e} url={resp.url} 前 200 字符: {text[:200]!r}（见 {debug_path}）",
            debug_path=debug_path,
        ) from e
    if not isinstance(body, dict):
        raise TypeError(f"期望 JSON 对象，实际: {type(body)}")
    return body


def fetch_polymer_feed_full(
    mid: str,
    headers: dict[str, str],
    offset: str | None = None,
    *,
    debug_dir: Path | None = None,
) -> dict:
    """返回 polymer 接口完整 JSON（含 code / message / data）。"""
    params = {"host_mid": mid, "offset": offset or ""}
    return _fetch_json(
        POLYMER_URL,
        headers=headers,
        params=params,
        debug_dir=debug_dir,
        debug_name=f"polymer_feed_{offset or 'start'}",
    )


def fetch_space_articles_full(
    mid: str,
    headers: dict[str, str],
    ps: int = 12,
    *,
    debug_dir: Path | None = None,
) -> dict:
    """返回 space/article 完整 JSON（卡池文章，用于 pool_view）。"""
    return _fetch_json(
        ARTICLE_URL,
        headers=headers,
        params={"mid": mid, "ps": ps},
        debug_dir=debug_dir,
        debug_name="space_articles",
    )


def _summarize_dynamic_item(item: dict, index: int) -> dict:
    """从单条动态提取便于肉眼查看的摘要。"""
    nodes = _collect_rich_text_nodes(item)
    texts = [(n.get("orig_text") or "").strip() for n in nodes if n.get("orig_text")]
    module_types = []
    for mod in _iter_dynamic_modules(item):
        for key in mod:
            if key.startswith("module_") and key not in module_types:
                module_types.append(key)
    return {
        "index": index,
        "id_str": item.get("id_str"),
        "pub_ts": _dynamic_pub_ts(item),
        "module_keys": module_types,
        "rich_text_count": len(texts),
        "rich_text_preview": texts[:8],
    }


def build_summary(data: dict | None, *, pages_fetched: int) -> str:
    lines = [
        f"generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"pages_fetched: {pages_fetched}",
        "",
    ]
    if not data:
        lines.append("data: (empty)")
        return "\n".join(lines)

    items = data.get("items") or []
    lines.append(f"items_on_last_page: {len(items)}")
    lines.append(f"offset: {data.get('offset')!r}")
    lines.append(f"has_more: {data.get('has_more')!r}")
    lines.append("")
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        summary = _summarize_dynamic_item(item, i)
        lines.append(f"--- item {summary['index']} id={summary['id_str']} pub_ts={summary['pub_ts']} ---")
        lines.append(f"  modules: {summary['module_keys']}")
        for j, t in enumerate(summary["rich_text_preview"]):
            preview = t.replace("\n", "\\n")
            if len(preview) > 200:
                preview = preview[:200] + "…"
            lines.append(f"  text[{j}]: {preview}")
        lines.append("")
    return "\n".join(lines)


def dump_bilibili_api_snapshot(
    *,
    output_dir: Path = OUTPUT_DIR,
    pages: int = 1,
    config_path: str = "config/config.json",
) -> Path:
    """
    请求 B 站 API 并写入 JSON + 摘要。返回输出目录路径。
    """
    config = load_config(resolve_config_path(config_path)) if config_path else {}

    cookies = config.get("cookies", "")
    mid = str(config.get("bilibili_mid", DEFAULT_BILIBILI_MID))
    headers = build_snapshot_headers(cookies)

    output_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    if not cookies.strip():
        msg = (
            "config 中 cookies 为空：请在 config/config.local.json 填写 cookies，"
            "或设置环境变量 ARK_TOOL_COOKIES"
        )
        errors.append(msg)
        print(f"警告: {msg}")

    # 专栏文章（限定寻访标题等）
    try:
        articles_full = fetch_space_articles_full(mid, headers, debug_dir=output_dir)
        (output_dir / "space_articles.json").write_text(
            json.dumps(articles_full, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (BilibiliApiResponseError, requests.RequestException) as e:
        errors.append(f"space/article: {e}")
        print(f"space/article 失败: {e}")

    offset = None
    last_data = None
    for page in range(pages):
        try:
            full = fetch_polymer_feed_full(
                mid, headers, offset=offset, debug_dir=output_dir
            )
        except (BilibiliApiResponseError, requests.RequestException) as e:
            errors.append(f"polymer page{page}: {e}")
            print(f"polymer page{page} 失败: {e}")
            break
        (output_dir / f"polymer_feed_page{page}.json").write_text(
            json.dumps(full, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        data = full.get("data")
        if isinstance(data, dict):
            last_data = data
            (output_dir / f"polymer_data_page{page}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if full.get("code") != 0:
            print(f"polymer page{page} API code={full.get('code')} message={full.get('message')}")
            break
        offset = (data or {}).get("offset") if isinstance(data, dict) else None
        if not offset:
            break

    # 与生产代码同路径再拉一页，便于对比 fetch_user_dynamics 返回值
    via_helper = fetch_user_dynamics(mid, headers, offset=None)
    if via_helper is not None:
        (output_dir / "polymer_data_via_helper.json").write_text(
            json.dumps(via_helper, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary_path = output_dir / "summary.txt"
    summary_path.write_text(
        build_summary(last_data, pages_fetched=pages),
        encoding="utf-8",
    )

    meta = {
        "mid": mid,
        "has_cookie": bool(cookies.strip()),
        "output_dir": str(output_dir),
        "errors": errors,
        "files": sorted(p.name for p in output_dir.iterdir() if p.is_file()),
    }
    (output_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if errors and last_data is None and not (output_dir / "space_articles.json").is_file():
        raise BilibiliApiResponseError(
            "全部请求失败，请查看 test/output/bilibili_api/*_http*.txt 与 meta.json"
        )
    return output_dir


@pytest.mark.integration
def test_dump_bilibili_api_snapshot():
    """需要网络与有效 Cookie；失败时会在 output 目录留下 *_http*.txt 诊断文件。"""
    try:
        out = dump_bilibili_api_snapshot(pages=1)
    except BilibiliApiResponseError:
        pytest.skip("B 站 API 无有效 JSON（检查 cookies / test/output/bilibili_api/*_http*.txt）")
    assert out.is_dir()
    assert (out / "polymer_feed_page0.json").is_file() or (out / "summary.txt").is_file()


def main() -> None:
    parser = argparse.ArgumentParser(description="拉取 B 站 API JSON 快照")
    parser.add_argument("--pages", type=int, default=1, help="动态 feed 翻页数")
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help="输出目录",
    )
    parser.add_argument(
        "--config",
        default="config/config.json",
        help="配置文件路径",
    )
    args = parser.parse_args()
    out = dump_bilibili_api_snapshot(
        output_dir=args.out.resolve(),
        pages=max(1, args.pages),
        config_path=args.config,
    )
    print(f"已写入: {out}")
    print(f"  查看完整 JSON: {out / 'polymer_feed_page0.json'}")
    print(f"  查看文本摘要: {out / 'summary.txt'}")


if __name__ == "__main__":
    main()
