"""刷新 BWIKI 聚合页缓存：purge + parse（首页 / 干员一览等）。"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = "https://wiki.biligame.com/arknights/api.php"
USER_AGENT = "Mozilla/5.0 (compatible; WikiPurgeBot/1.0)"
CHUNK_SIZE = 10
PARSE_DELAY = 1.0
MAX_RETRIES = 3

CST = timezone(timedelta(hours=8))

DEFAULT_PAGES = [
    "首页",
    "干员一览",
    "干员图鉴-先锋",
    "干员图鉴-近卫",
    "干员图鉴-重装",
    "干员图鉴-狙击",
    "干员图鉴-术师",
    "干员图鉴-医疗",
    "干员图鉴-辅助",
    "干员图鉴-特种",
]

# 兼容旧脚本名
PAGES = DEFAULT_PAGES


def _api_post(params: dict) -> dict:
    """POST 请求 API，遇到限流自动重试。"""
    post_data = urllib.parse.urlencode({**params, "format": "json"}).encode("utf-8")
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(API_URL, data=post_data)
            req.add_header("User-Agent", USER_AGENT)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 567 and attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 5
                time.sleep(wait)
                continue
            raise


def _api_get(params: dict) -> dict:
    """GET 语义参数通过 POST 发送，避免 CDN 对 GET 的限流。"""
    post_data = urllib.parse.urlencode({**params, "format": "json"}).encode("utf-8")
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(API_URL, data=post_data)
            req.add_header("User-Agent", USER_AGENT)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 567 and attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 5
                time.sleep(wait)
                continue
            raise


def _chunks(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def phase1_purge(titles: list[str]) -> tuple[list[str], list[str]]:
    """分批 purge（forcelinkupdate）。返回 (成功, 失败)。"""
    purged: list[str] = []
    failed: list[str] = []
    total = len(titles)

    for batch in _chunks(titles, CHUNK_SIZE):
        try:
            result = _api_post({
                "action": "purge",
                "titles": "|".join(batch),
                "forcelinkupdate": "1",
            })
            for entry in result.get("purge", []):
                title = entry.get("title", "")
                if "purged" in entry:
                    purged.append(title)
                else:
                    failed.append(title)
                    reason = entry.get("invalidreason") or entry.get("missing") or "未知"
                    print(f"  ❌ {title} — purge 失败 ({reason})")
        except Exception as e:
            failed.extend(batch)
            print(f"  ❌ 批次 [{batch[0]} ...] — 请求异常: {e}")

        time.sleep(0.3)
        done = len(purged) + len(failed)
        print(f"  [purge] {done}/{total}", end="\r", flush=True)

    print()
    return purged, failed


def phase2_parse(titles: list[str]) -> tuple[list[str], list[str]]:
    """逐页 parse 重建渲染缓存。返回 (成功, 失败)。"""
    parsed: list[str] = []
    failed: list[str] = []
    total = len(titles)

    for i, title in enumerate(titles):
        ok = False
        last_error = ""

        for attempt in range(MAX_RETRIES):
            try:
                result = _api_post({
                    "action": "parse",
                    "page": title,
                    "prop": "text",
                    "disablelimitreport": "1",
                    "disableeditsection": "1",
                })
                if "parse" in result and result["parse"].get("title"):
                    parsed.append(title)
                    ok = True
                elif "error" in result:
                    last_error = result["error"].get("info", "未知错误")
                    break
                else:
                    last_error = "响应异常"
            except urllib.error.HTTPError as e:
                if e.code == 567 and attempt < MAX_RETRIES - 1:
                    wait = (attempt + 1) * 3
                    print(
                        f"  [{i+1}/{total}] {title} — 限流，{wait}s 后重试",
                        end="\r",
                        flush=True,
                    )
                    time.sleep(wait)
                    continue
                last_error = f"HTTP {e.code}"
                break
            except Exception as e:
                last_error = str(e)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                    continue
                break

            break

        if ok:
            print(f"  [{i+1}/{total}] ✅ {title}" + " " * 30, end="\r", flush=True)
        else:
            failed.append(title)
            print(f"  [{i+1}/{total}] ❌ {title} — {last_error}")
            time.sleep(0.5)

        if i < total - 1:
            time.sleep(PARSE_DELAY)

    print()
    return parsed, failed


def fetch_touched_times(titles: list[str]) -> dict[str, str]:
    """查询页面缓存时间戳。返回 {title: touched_iso}。"""
    result = _api_get({
        "action": "query",
        "titles": "|".join(titles),
        "prop": "info",
        "inprop": "touched",
    })
    touched_map: dict[str, str] = {}
    for _page_id, info in result.get("query", {}).get("pages", {}).items():
        title = info.get("title", "")
        touched = info.get("touched", "")
        if title:
            touched_map[title] = touched
    return touched_map


def _format_timestamp(iso_str: str) -> str:
    if not iso_str:
        return "未知"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_str


def refresh_wiki_aggregate_pages(titles: list[str] | None = None) -> int:
    """
    刷新聚合页：阶段 1 purge，阶段 2 parse，并打印摘要。
    返回 0 表示全部成功，非 0 表示有失败。
    """
    page_list = list(titles) if titles is not None else list(DEFAULT_PAGES)
    total = len(page_list)
    print(f"共 {total} 个页面待刷新\n")

    start = time.time()
    all_ok: list[str] = []
    all_fail: list[str] = []

    print("━" * 40)
    print("阶段 1/2: 清理服务器缓存 (purge + forcelinkupdate)")
    print("━" * 40)
    purged, purge_fail = phase1_purge(page_list)
    print(f"purge 完成: {len(purged)} 成功, {len(purge_fail)} 失败\n")
    all_fail.extend(purge_fail)

    if purged:
        print("━" * 40)
        print("阶段 2/2: 逐页解析重建 (action=parse)")
        print("━" * 40)
        parsed, parse_fail = phase2_parse(purged)
        all_ok = parsed
        all_fail.extend(parse_fail)
        print(f"解析完成: {len(parsed)} 成功, {len(parse_fail)} 失败\n")
    else:
        print("没有可解析的页面，阶段 2 跳过。\n")

    if all_ok:
        print("━" * 40)
        print("验证: 查询缓存时间戳")
        print("━" * 40)
        try:
            touched_map = fetch_touched_times(all_ok)
            for title in all_ok:
                ts = touched_map.get(title, "")
                print(f"  ✅ {title} — 缓存时间: {_format_timestamp(ts)}")
        except Exception as e:
            print(f"  ⚡ 验证失败: {e}")
            for title in all_ok:
                print(f"  ✅ {title}")

    elapsed = time.time() - start
    print(f"\n{'━' * 40}")
    print(f"总耗时 {elapsed:.1f}s | 成功 {len(all_ok)} | 失败 {len(all_fail)}")

    if all_ok:
        print("🎉 全部页面刷新完成！")
    if all_fail:
        print(f"⚠️  {len(all_fail)} 个失败:")
        for t in all_fail:
            print(f"    - {t}")

    return 1 if all_fail else 0


__all__ = [
    "API_URL",
    "DEFAULT_PAGES",
    "PAGES",
    "fetch_touched_times",
    "phase1_purge",
    "phase2_parse",
    "refresh_wiki_aggregate_pages",
]

