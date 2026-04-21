"""Bilibili related service functions for character supplementary data."""

from __future__ import annotations

import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests


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
                    if side_story is None and re.match(r"SideStory「(.*)」", text):
                        side_story = text[text.find("「") + 1 : text.find("」")]
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
                        try:
                            character["专精"] = ocr_specialization(str(photo_path))
                        except Exception:
                            character["专精"] = ""
                            log_warning("专精OCR失败，已降级为空 name=%s", name)
                        print(character)
                        implementation_data = pool_view.get(gacha_pool)
                        if implementation_data is not None:
                            if implementation_data[1] and implementation_data[1][0] == "0":
                                implementation_data[1] = implementation_data[1][1:]
                            release_time = implementation_data[1]
                            if acquisition_method.get(implementation_data[0]) is not None:
                                if len(data) > index + 1:
                                    split_index = data[index + 1]["orig_text"].rfind("/")
                                    character["动态id"] = data[index + 1]["orig_text"][split_index + 1 :]
                                    character["获取途径"] = (
                                        acquisition_method.get(implementation_data[0], "")
                                        + f"{gacha_pool}】限定寻访"
                                    )
                                else:
                                    character["获取途径"] = acquisition_method.get("新增干员", "标准寻访")
                        else:
                            if gacha_pool == "活动奖励干员":
                                character["获取途径"] = acquisition_method.get(gacha_pool, "") + (side_story or "") + "】活动获取"
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
                        character["宣传介绍"] = intro
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
