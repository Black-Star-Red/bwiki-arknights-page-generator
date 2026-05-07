"""Bilibili related service functions for character supplementary data."""

from __future__ import annotations

import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from bs4 import BeautifulSoup
import json
import requests
def slice_json_object_after_key(text: str, key: str = "initialData") -> dict:
    # 常见：\"initialData\":{  或  "initialData":{
    markers = [f'\\"{key}\\":{{', f'"{key}":{{']
    start_brace = -1
    for m in markers:
        pos = text.find(m)
        if pos != -1:
            start_brace = text.find("{", pos)
            break
    if start_brace == -1:
        # 兜底：只找 key，再找后面第一个 {
        pos = text.find(key)
        if pos == -1:
            raise ValueError(f"找不到 {key}")
        start_brace = text.find("{", pos)
    if start_brace == -1:
        raise ValueError(f"{key} 后没有 {{")
    depth = 0
    for i in range(start_brace, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                blob = text[start_brace : i + 1]
                return json.loads(blob)
    raise ValueError("括号不配对，可能截断了")
def get_dynamic_id(name:str):
    response = requests.get("https://ak.hypergryph.com/archive/dynamicCompile")
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        scripts = [
            s.string
            for s in soup.find_all("script")
            if s.string and "__next_f.push" in s.string and "initialData" in s.string
        ]
        # 用法：scripts[0] 是整段 script 字符串（str），不是 BeautifulSoup 节点的话要 .string
        text =scripts[0].replace("\\","")
        print(text)
        text = text if isinstance(text, str) else text.string
        data = slice_json_object_after_key(text)
        print(data.keys())
        for i in data["0"]["list"]:
            if i["name"]==name:
                return i["cid"]
        return ""


def _toolbox_package_root() -> Path:
    """`arknights_toolbox` 包目录（本文件位于 shared/services/）。"""
    return Path(__file__).resolve().parents[2]


def operator_photo_dir() -> Path:
    """B 站动态配图与 OCR 用图目录：包内 `photo/`。"""
    return _toolbox_package_root() / "photo"


def fetch_user_dynamics(mid: str, headers: dict[str, str], offset: str | None = None):
    """Fetch user dynamics from Bilibili API."""
    api_url = "https://api.bilibili.com/x/polymer/web-dynamic/desktop/v1/feed/space"
    params = {
        "host_mid": mid,
        "offset": "" if offset is None else offset,
    }

    for attempt in range(5):
        try:
            response = requests.get(api_url, headers=headers, params=params, timeout=10)
            text = response.text or ""
            if response.status_code != 200:
                print(f"请求失败: status={response.status_code}")
            elif not text.strip():
                print("请求失败: empty response body")
            else:
                try:
                    data = response.json()
                    if data.get("code") == 0:
                        return data.get("data")
                    print(f"API错误: {data.get('message')}")
                except ValueError as e:
                    print(f"请求失败: JSON解析失败 {e}; 响应前200字符: {text[:200]}")
        except requests.RequestException as e:
            print(f"请求失败: {e}")

        sleep_s = (2**attempt) * 0.5 + random.random() * 0.2
        time.sleep(sleep_s)
    return None


def fetch_character_supplementary_data(
    mid: str,
    headers: dict[str, str],
    *,
    announce_line_re: re.Pattern[str],
    acquisition_method: dict[str, str],
    ocr_specialization: Callable[[str], str],
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
    character_num: int = 3,
) -> dict[str, dict[str, str]]:
    """Fetch supplementary character data from Bilibili APIs."""
    result: dict[str, dict[str, str]] = {}
    diag = {"pages": 0, "items_total": 0, "skipped_exceptions": 0}
    url = "https://api.bilibili.com/x/space/article"
    params = {
        "mid": "161775300",
        "ps": 12,
    }
    request = None
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200 and (resp.text or "").strip():
                request = resp
                break
            print(f"获取卡池失败: status={resp.status_code}, body前120={resp.text[:120] if resp.text else ''}")
        except requests.RequestException as e:
            print(f"获取卡池失败: {e}")
        time.sleep((2**attempt) * 0.4 + random.random() * 0.2)

    pool_view: dict[str, list[str]] = {}
    if request is not None:
        try:
            req_json = request.json()
            articles = req_json.get("data", {}).get("articles", [])
        except ValueError as e:
            print(f"获取卡池失败: JSON解析失败 {e}; 响应前200字符: {request.text[:200]}")
            articles = []
        for article in articles:
            if "限定寻访" in article["title"]:
                data = [article["title"][1:8]]
                left = article["title"].find("【")
                right = article["title"].find("】")
                ltime = article["summary"].find("活动时间：")
                rtime = article["summary"].find("日")
                data.append(article["summary"][ltime + 5 : rtime + 1])
                pool_view[article["title"][left + 1 : right]] = data
    else:
        print("获取卡池失败")

    print(pool_view)
    dynamics = fetch_user_dynamics(mid, headers)

    side_story = None
    release_time = None
    while len(result.keys()) < character_num:
        if not dynamics:
            break
        diag["pages"] += 1
        items_page = dynamics.get("items") or []
        diag["items_total"] += len(items_page)
        for item in items_page:
            try:
                data = item["modules"][1]["module_desc"]["rich_text_nodes"]
                photo_url = item["modules"][2]["module_dynamic"]["dyn_draw"]["items"][0]["src"]
                for index, node in enumerate(data):
                    text = node["orig_text"]
                    if side_story is None:
                        m = re.match(r"SideStory「([^」]+)」", text)
                        if m is None:
                            m = re.search(r"主题曲「([^」]+)」", text)
                        if m:
                            side_story = m.group(0)
                    if announce_line_re.match(text):
                        character: dict[str, str] = {}
                        gacha_pool = text[text.find("【") + 1 : text.find("】")]
                        start = text.find("//")
                        end = text.find("\n", start)
                        name = text[start + 2 : end]
                        photo_path = operator_photo_dir() / f"{name}.jpg"
                        if not photo_path.exists():
                            photo = requests.get(photo_url, timeout=10)
                            photo_path.parent.mkdir(parents=True, exist_ok=True)
                            if photo.status_code == 200:
                                photo_path.write_bytes(photo.content)
                        # try:
                        #     character["专精"] = ocr_specialization(str(photo_path))
                        # except Exception:
                        #     character["专精"] = ""
                        #     log_warning("专精OCR失败，已降级为空 name=%s", name)
                        character["专精"] = ""
                        print(character)
                        implementation_data = pool_view.get(gacha_pool)
                        if implementation_data is not None:
                            if implementation_data[1] and implementation_data[1][0] == "0":
                                implementation_data[1] = implementation_data[1][1:]
                            release_time = implementation_data[1]
                            if acquisition_method.get(implementation_data[0]) is not None:
                                dynamic_id  = get_dynamic_id(name)
                                if dynamic_id != "":
                                    character["动态id"] = dynamic_id

                                    character["获取途径"] = (
                                        acquisition_method.get(implementation_data[0], "")
                                        + f"{gacha_pool}】限定寻访"
                                    )
                                else:
                                    character["获取途径"] = acquisition_method.get("新增干员", "标准寻访")
                        else:
                            if gacha_pool == "活动奖励干员":
                                if "主题曲" in side_story:
                                    character["获取途径"]= "主题曲获得 / "
                                else:
                                    l = side_story.find("「")
                                    r = side_story.rfind("」")
                                    character["获取途径"] = acquisition_method.get(gacha_pool, "") + (side_story[l+1:r] or "") + "】活动获取"

                            else:
                                character["获取途径"] = acquisition_method.get(gacha_pool, "标准寻访")
                        if release_time:
                            character["实装日期"] = (
                                "[https://t.bilibili.com/"
                                + item["id_str"]
                                + "?spm_id_from=333.1387.0.0 "
                                + release_time
                                + "]"
                            )
                        else:
                            character["实装日期"] = (
                                "[https://t.bilibili.com/"
                                + item["id_str"]
                                + "?spm_id_from=333.1387.0.0 "
                                + datetime.now().strftime("%Y年%m月%d日")
                                + "]"
                            )
                        intro = text[text.rfind("_") + 2 :].rstrip("\n")
                        intro = intro.replace("\n", "<br/>\n")
                        character["宣传介绍"] = intro.replace("<br/>\n<br/>\n关注并转发本条动态，我们将抽取10位博士赠送【现金648元】一份。","")
                        result[name] = character
                        if len(result) >= character_num:
                            break
            except Exception:
                diag["skipped_exceptions"] += 1
                if len(result) >= character_num:
                    break
                continue
        offset = dynamics.get("offset")
        if not offset:
            break
        dynamics = fetch_user_dynamics(mid, headers, offset)
    log_info("result:%s", result)
    if not result:
        log_warning(
            "supplementary_data_empty mid=%s pool_keys=%s pages=%s items_total=%s skipped_exceptions=%s",
            mid,
            len(pool_view),
            diag["pages"],
            diag["items_total"],
            diag["skipped_exceptions"],
        )
    return result


__all__ = ["fetch_user_dynamics", "fetch_character_supplementary_data", "operator_photo_dir"]
