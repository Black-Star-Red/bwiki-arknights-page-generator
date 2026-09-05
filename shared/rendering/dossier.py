"""Handbook dossier parsing/rendering helpers."""

from __future__ import annotations

import re

from data.mapper_helpers import bind_handbook_char

# 仅登记需要特殊预处理的标题；纯【】测试 / 纯文本履历可走通用分支或 else
_STORY_TITLE_ALIASES = {
    "特殊疾病筛查": "临床诊断分析",
}

_BRACKET_FIELD_RE = re.compile(r"【([^】]+)】([^\n【]*)")

# 整段正文：换行→<br/>，Wiki 键用 storyTitle（含履历类，按纯文本处理）
_PLAIN_STORY_TITLES = frozenset(
    {
        "客观履历",
        "学生概况",
        "档案资料一",
        "档案资料二",
        "档案资料三",
        "档案资料四",
        "晋升记录",
    }
)

# 【】表：标签原样输出（综合能力测试等未登记的走 else）
_BRACKET_SHEET_TITLES = frozenset(
    {
        "综合体检测试",
        "综合性能检测结果",
    }
)


# 【基础档案】游戏标签 → Wiki 参数（生日/感染/经验另有特殊处理）
_BASE_FIELD_TO_WIKI = (
    ("性别", "性别"),
    ("种族", "种族"),
    ("出身地", "出身"),
    ("产地", "产地"),
    ("身高", "身高"),
    ("高度", "高度"),
    ("设定性别", "设定性别"),
    ("重量", "重量"),
    ("制造商", "制造商"),
    ("出厂时间", "出厂时间"),
    ("入学年级", "入学年级"),
    ("维护检测报告", "维护检测报告"),
    ("维护检测情况", "维护检测报告"),  # 后者仅在前者为空时补上
)

_DATE_BRACKET_RE = re.compile(r"【([^】]*)】(\d+)月(\d+)日")
_EXPERIENCE_RE = re.compile(r"【(.*?)经验】(.+?)(?:\n|$)")


def _wiki_text_field(v) -> str:
    """避免把 Python/JSON 的 None 写成字面量 ``None`` 进 Wiki。"""
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() == "none":
        return ""
    return s


def _canonical_story_title(title: str) -> str:
    return _STORY_TITLE_ALIASES.get(title, title)


def parse_bracket_fields(text: str) -> dict[str, str]:
    """从档案正文扫描 ``【标签】值``（值到换行或下一个【为止）。"""
    out: dict[str, str] = {}
    for m in _BRACKET_FIELD_RE.finditer(text or ""):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if key:
            out[key] = val
    return out


def _bracket_value_or_next_line(text: str, label: str, fields: dict[str, str]) -> str:
    """同行值为空时，取【标签】下一行。"""
    val = (fields.get(label) or "").strip()
    if val:
        return val
    m = re.search(rf"【{re.escape(label)}】\s*\n(.+)", text or "")
    return m.group(1).strip() if m else ""


def _looks_like_bracket_sheet(title: str, fields: dict[str, str]) -> bool:
    """新出的测试/检测类（如综合能力测试）未登记时，仍按【】表处理。"""
    if not fields:
        return False
    if "测试" in title or "检测" in title:
        return True
    # 多组短值【】，避免把诊断长文里偶发的【】当成表
    return len(fields) >= 3 and all(len(v) <= 20 for v in fields.values())


def _apply_base_field_map(base_fields: dict[str, str]) -> dict[str, str]:
    """把基础档案【】标签填进 Wiki 键；同目标键先到先得。"""
    profile: dict[str, str] = {}
    for src, dst in _BASE_FIELD_TO_WIKI:
        val = (base_fields.get(src) or "").strip()
        if val and not profile.get(dst):
            profile[dst] = val
    return profile


def render_operator_dossier_fields(
    mapper,
    char_id,
    value,
    trait_candidates,
    rich_styles,
    term_description_dict,
    *,
    safe_get_fn,
    process_description_fn,
):
    """干员档案模板"""
    lines: list[str] = []
    # 基础档案 Wiki 字段（含特殊处理写入的生日/感染/经验等）
    profile: dict[str, str] = {}
    month = day = is_infection = ""
    # 【】表：综合体检测试、综合性能检测结果，以及 else 中新出的测试/检测
    bracket_fields: dict[str, str] = {}
    # 整段正文：履历、档案资料、晋升/升变、诊断等（键用 storyTitle）
    story_text_fields: dict[str, str] = {}

    bind_handbook_char(mapper, char_id)
    char_text = mapper.get_data_safe("handbook_info_table", "handbook_dict_entry") or {}
    for story_idx, story_text in enumerate(char_text.get("storyTextAudio") or []):
        mapper.add_mapping("handbook_info_table", "handbook_story_index", str(story_idx))
        raw_title = story_text.get("storyTitle") or ""
        canon = _canonical_story_title(raw_title)
        raw = safe_get_fn(story_text, ["stories", 0, "storyText"]) or ""

        if canon == "基础档案":
            if "【代号】" in raw or "【姓名】" in raw:
                base_fields = parse_bracket_fields(raw)
                profile = _apply_base_field_map(base_fields)

                # 特殊：生日 / 出厂日（拆月日）
                birthday_data = _DATE_BRACKET_RE.search(raw)
                if birthday_data:
                    label, mo, da = birthday_data.group(1), birthday_data.group(2), birthday_data.group(3)
                    date_text = f"{mo}月{da}日"
                    month, day = mo, da
                    if label == "生日":
                        profile["生日"] = date_text
                    elif label == "出厂日":
                        profile["出厂日"] = date_text
                elif base_fields.get("生日"):
                    profile["生日"] = base_fields["生日"]

                # 特殊：感染情况（可能在下一行）+ 是否感染
                infection = _bracket_value_or_next_line(raw, "矿石病感染情况", base_fields)
                profile["矿石病毒感染情况"] = infection
                is_infection = "是" if "确认为感染者" in infection else "否"

                # 特殊：【xx经验】→ 经验 + 经验名称
                experience_data = _EXPERIENCE_RE.search(raw)
                if experience_data:
                    profile["经验"] = experience_data.group(2).strip()
                    profile["经验名称"] = experience_data.group(1) + "经验"

                # 维护检测：同行空则取下一行
                if not profile.get("维护检测报告"):
                    for label in ("维护检测报告", "维护检测情况"):
                        got = _bracket_value_or_next_line(raw, label, base_fields)
                        if got:
                            profile["维护检测报告"] = got
                            break

        elif canon in _BRACKET_SHEET_TITLES:
            bracket_fields.update(parse_bracket_fields(raw))

        elif canon == "临床诊断分析":
            unlock_type = mapper.get_data_safe(
                "handbook_info_table", "handbook_story_unlock_type", default=None
            )
            story_txt = (
                mapper.get_data_safe("handbook_info_table", "handbook_story_text", default="")
                or ""
            )
            unlock_param = (
                mapper.get_data_safe(
                    "handbook_info_table", "handbook_story_unlock_param", default=""
                )
                or ""
            )
            if unlock_type in ("DIRECT", "FAVOR"):
                diagnosis = story_txt.replace("\n", "<br/>")
            elif unlock_type == "AWAKE":
                parts_param = (unlock_param or "").split(";")
                p0 = parts_param[0] if len(parts_param) > 0 else ""
                p1 = parts_param[1] if len(parts_param) > 1 else ""
                diagnosis = f"{p0}等级{p1}<br/>{story_txt.replace(chr(10), '<br/>')}"
            else:
                diagnosis = ""
            story_text_fields[raw_title] = diagnosis

        elif canon in _PLAIN_STORY_TITLES or "升变档案" in raw_title:
            story_text_fields[raw_title] = raw.replace("\n", "<br/>").replace("{@nickname}","博士")

        else:
            # 未登记标题：综合能力测试等 →【】表；其余 → 整段纯文本
            if not raw_title:
                continue
            fields = parse_bracket_fields(raw)
            if _looks_like_bracket_sheet(raw_title, fields):
                bracket_fields.update(fields)
            else:
                story_text_fields[raw_title] = raw.replace("\n", "<br/>")

    secret_record = []
    for i in range(1, 4):
        secret_record.append(
            [
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "storySetName"]),
                safe_get_fn(
                    char_text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam1"]
                ),
                safe_get_fn(
                    char_text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam1"]
                ),
                safe_get_fn(
                    char_text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam2"]
                ),
                safe_get_fn(
                    char_text, ["handbookAvgList", i - 1, "unlockParam", 1, "unlockParam1"]
                ),
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "avgList", 0, "storyIntro"]),
            ]
        )

    p = profile  # 基础档案 Wiki 字段
    lines.append(f"|生日={p.get('生日', '')}")
    lines.append(f"|出厂日={p.get('出厂日', '')}")
    lines.append(f"|入学年级={p.get('入学年级', '')}")
    lines.append(f"|月={month}")
    lines.append(f"|日={day}")
    lines.append(f"|性别={p.get('性别', '')}")
    lines.append("|真实姓名=")
    lines.append("|职能=")
    lines.append(f"|种族={p.get('种族', '')}")
    lines.append(f"|出身={p.get('出身', '')}")
    lines.append(f"|身高={p.get('身高', '')}")
    lines.append(f"|高度={p.get('高度', '')}")
    lines.append(f"|是否感染={is_infection}")
    lines.append(f"|设定性别={_wiki_text_field(p.get('设定性别', ''))}")
    spec = _wiki_text_field(value.get("专精", ""))
    lines.append(f"|专精={spec}")
    lines.append(f"|经验={_wiki_text_field(p.get('经验', ''))}<!--类似十年这样的文本-->")
    lines.append(
        f"|经验名称={_wiki_text_field(p.get('经验名称', ''))}<!--不填写即显示战斗经验-->"
    )
    lines.append(f"|制造商={p.get('制造商', '')}")
    lines.append(f"|产地={p.get('产地', '')}")
    lines.append(f"|出厂时间={p.get('出厂时间', '')}")
    lines.append(f"|重量={p.get('重量', '')}")
    lines.append(f"|维护检测报告={p.get('维护检测报告', '')}")
    lines.append(f"|矿石病毒感染情况={p.get('矿石病毒感染情况', '')}")
    for key, val in bracket_fields.items():
        lines.append(f"|{key}={val}")
    for title, text in story_text_fields.items():
        lines.append(f"|{title}={text}")
    # 档案资料五仍来自 item「宣传介绍」，不是 handbook story
    promo5 = _wiki_text_field(value.get("宣传介绍", ""))
    lines.append(f"|档案资料五={promo5}")
    lines.append("|档案资料五标题=宣传介绍")
    lines.append("|体检描述=")
    for i in range(1, 4):
        rec = secret_record[i - 1]
        lines.append(f"|干员密录{i}={rec[0] if rec[0] else ''}")
        lines.append(
            f"|干员密录{i}解锁条件="
            + (
                f"[[文件: icon_e{rec[1]}_need.png|20px|link=|class=invert-color]]提升至精英阶段{rec[2]}等级{rec[3]}<br/>[[文件:icon_信赖.png|20px|link=|class=invert-color]]提升信赖至{rec[4]}"
                if rec[1]
                else ""
            )
        )
        lines.append(f"|干员密录{i}描述={rec[5] if rec[5] else ''}")
        lines.append(f"|干员密录{i}述描视频=")
    lines.append("|悖论模拟标题=")
    return lines


__all__ = [
    "parse_bracket_fields",
    "render_operator_dossier_fields",
]
