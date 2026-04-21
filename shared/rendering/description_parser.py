"""Description rendering helpers used by legacy template generation."""

from __future__ import annotations

import re
from collections import defaultdict


def _resolve_term_index_maps(term_description_dict, term_index_cache):
    """Build or reuse tag->(name,index) maps for term description ids."""
    if not isinstance(term_description_dict, dict):
        return {}, {}
    if not isinstance(term_index_cache, dict):
        term_index_cache = {}
    cache_key = id(term_description_dict)
    cached = term_index_cache.get(cache_key)
    if cached is not None:
        return cached["tag_to_name"], cached["tag_to_index"]

    name_count = defaultdict(int)
    tag_to_name = {}
    tag_to_index = {}
    for tid, info in term_description_dict.items():
        if not isinstance(info, dict):
            continue
        base = str(info.get("termName") or "").strip()
        if not base:
            continue
        name_count[base] += 1
        tag_to_name[tid] = base
        tag_to_index[tid] = name_count[base]

    term_index_cache[cache_key] = {
        "tag_to_name": tag_to_name,
        "tag_to_index": tag_to_index,
    }
    return tag_to_name, tag_to_index


def process_description(desc, trait_candidates, rich_styles, termDescriptionDict, blackboard=None, term_index_cache=None):
    """
        将明日方舟的富文本描述解析为维基模板文本。

        注意事项：
        - `blackboard` 是可选的，用于 `{key}` / `{key:0%}` 替换。
    """
    result_chars = []
    stack = []
    i = 0
    if desc is None:
        return ""
    length = len(desc)
    map_data = {}
    if blackboard:
        for data in blackboard:
            map_data[data["key"]] = data["value"]
    tag_to_name, tag_to_index = _resolve_term_index_maps(termDescriptionDict, term_index_cache)
    while i < length:
        ch = desc[i]
        if ch == "<" and i + 1 < length and desc[i + 1] in ("@", "$"):
            end_idx = desc.find(">", i + 2)
            if end_idx != -1:
                tag_id = desc[i + 2 : end_idx]
                tag_type = "<@" if desc[i + 1] == "@" else "<$"
                stack.append((tag_type, tag_id, len(result_chars)))
                i = end_idx + 1
                continue

        elif ch == "<" and i + 2 < length and desc[i : i + 3] == "</>":
            if not stack:
                result_chars.append(ch)
                i += 1
                continue

            tag_type, tag_id, start_idx = stack.pop()
            inner = "".join(result_chars[start_idx:])
            del result_chars[start_idx:]

            if tag_type == "<@":
                style = rich_styles.get(tag_id)
                if not style:
                    result_chars.append(f"{{{{释义|{inner}}}}}")
                    i += 3
                    continue

                color_match = re.match(r"<color=#([^>]*)>", style)
                if not color_match:
                    result_chars.append(f"{{{{释义|{inner}}}}}")
                    i += 3
                    continue
                color = color_match.group(1)

                left_brace = inner.find("{")
                if left_brace == -1:
                    processed = inner
                else:
                    prefix = inner[:left_brace]
                    right_brace = inner.find("}", left_brace)
                    if right_brace == -1:
                        processed = inner
                    else:
                        key_part = inner[left_brace + 1 : right_brace]
                        colon = key_part.find(":")
                        if colon == -1:
                            key = key_part
                            is_percent = False
                        else:
                            key = key_part[:colon]
                            is_percent = True
                        values = []
                        for cand in trait_candidates:
                            for board in cand.get("blackboard", []):
                                if board.get("key") == key:
                                    val = board.get("value")
                                    if val is not None:
                                        values.append(val)
                                    break
                        if not values:
                            value_str = key
                        elif is_percent:
                            value_str = str(int(values[-1] * 100)) + "%"
                        else:
                            value_str = "/".join(str(int(v)) for v in values)

                        processed = prefix + value_str

                result_chars.append(f"{{{{color|{color}|{processed}}}}}")

            elif tag_type == "<$":
                style = termDescriptionDict.get(tag_id, {}) if isinstance(termDescriptionDict, dict) else {}
                base_name = tag_to_name.get(tag_id) or style.get("termName") or inner
                name_index = tag_to_index.get(tag_id, 1)
                target_name = base_name if name_index <= 1 else f"{base_name}{name_index}"
                should_show_display = (name_index > 1) or tag_id.endswith("2")
                if should_show_display:
                    display_name = base_name.split("·", 1)[0] if (tag_id.endswith("2") and "·" in base_name) else base_name
                    glossary_text = f"{{{{释义|{target_name}|显示={display_name}}}}}"
                else:
                    glossary_text = f"{{{{释义|{target_name}}}}}"
                color_match = re.fullmatch(r"\{\{color\|([^|{}]+)\|(.*)\}\}", inner, flags=re.DOTALL)
                if color_match:
                    result_chars.append(f"{{{{color|{color_match.group(1)}|{glossary_text}}}}}")
                else:
                    result_chars.append(glossary_text)

            i += 3
            continue

        elif ch == "{":
            end = desc.find("}", i + 1)
            if end != -1:
                data = desc[i + 1 : end]
                i = end
                if data.endswith(":0%"):
                    data = map_data[data[:-3]] * 100
                    rounded = round(data)
                    if abs(data - rounded) < 1e-10:
                        data = int(rounded)
                    result_chars.append(f"{data}%")
                else:
                    data = map_data[data]
                    if data.is_integer():
                        data = int(data)
                    result_chars.append(f"{data}")
            else:
                result_chars.append(ch)
            i += 1
        else:
            result_chars.append(ch)
            i += 1

    return "".join(result_chars).replace(r"\n","<br/>")


__all__ = ["process_description"]
