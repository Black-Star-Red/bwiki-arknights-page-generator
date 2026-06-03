"""本地 character_table 无匹配时：仅保留 B 站补充字段，游戏内字段留空。"""

from __future__ import annotations

from shared.globals import VOICE_MAP
from shared.rendering import (
    process_description,
    render_operator_dossier_fields,
    render_operator_skin_template_lines,
    resolve_drawer_with_fallback,
)
from shared.rendering.voice import _CV_FIELD_SPECS
from shared.utils import safe_get

from .supplementary_labels import build_corner_labels, collab_obtain_path, is_limited_dynamic


def _empty_cv_field_lines() -> list[str]:
    return [f"|{field}=" for field, _ in _CV_FIELD_SPECS]


def _empty_voice_template_lines(name: str) -> list[str]:
    lines = [
        "{{干员语音/套",
        f"|所属干员={name}",
        "|所属皮肤=默认",
        "|语言=中文-普通话",
    ]
    for _number, description in VOICE_MAP.items():
        lines.append(f"|{description}=")
    lines.append("}}")
    return lines


def _empty_progression_and_skill_placeholders() -> list[str]:
    lines: list[str] = []
    for phase in (0, 1, 2):
        lines.append(f"|精英化材料{phase}=")
        lines.append(f"|精英化{phase}提升=")
    lines.append("|潜能提升=")
    for i in range(1, 4):
        for j in range(7, 10):
            lines.append(f"|{i}技能{j}→{j+1}材料=")
    for i in range(1, 7):
        lines.append(f"|技能{i}→{i+1}材料=")
    lines.append("|潜能1=")
    lines.append("|潜能2=")
    lines.append("|潜能3=")
    lines.append("|潜能4=")
    lines.append("|潜能5=")
    lines.append("|潜能6=")
    lines.append("|信赖加成50=")
    lines.append("|信赖加成100=")
    lines.append("|信赖加成150=")
    lines.append("|信赖加成200=")
    for i in range(1, 4):
        lines.append(f"|技能{i}=")
        lines.append(f"|技能{i}描述=")
        lines.append(f"|技能{i}范围=")
    lines.append("|基建技能=")
    lines.append("|画师=")
    return lines


def build_operator_parts_without_local_json(
    name: str,
    value: dict,
    mapper,
    *,
    char_id: str | None = None,
) -> list[str]:
    """生成干员 Wiki 模板：B 站 supplementary 有值，游戏 JSON 字段为空。"""
    obtain = collab_obtain_path(value) or value.get("获取途径") or ""
    label = build_corner_labels(value)

    parts: list[str] = []
    parts.append("{{干员")
    parts.append(f"|干员代号={name}")
    parts.append("|背景=")
    parts.append(f"|实装日期={value.get('实装日期', '')}")
    parts.append("|charId=")
    if label:
        parts.append("|角标=" + "、".join(label))
    if is_limited_dynamic(value):
        parts.append("|解限=否")
    parts.append(f"|获取途径={obtain}")
    cid = (char_id or "").strip()
    if cid:
        drawer = resolve_drawer_with_fallback(mapper, cid, db_drawer=value.get("画师"))
    else:
        drawer = (value.get("画师") or "").strip()
    parts.append(f"|画师={drawer}")
    parts.append("|英文名=")
    parts.append("|职业=")
    parts.append("|星级=")
    parts.append("|干员编号=")
    parts.append("|阵营=")
    parts.append("|副阵营=")
    parts.append("|标签=")
    parts.append("|特性=")
    parts.append("|特性攻击范围=")
    parts.append("|分支=")
    parts.append(f"|精二动态id={value.get('动态id', '')}")
    parts.extend(_empty_progression_and_skill_placeholders())
    parts.extend(render_operator_skin_template_lines(mapper, cid))

    rich_styles = mapper.get_data_safe("gamedata_const", "richTextStyles")
    term_description_dict = mapper.get_data_safe("gamedata_const", "termDescriptionDict")
    parts.extend(
        render_operator_dossier_fields(
            mapper,
            "",
            value,
            [],
            rich_styles,
            term_description_dict,
            safe_get_fn=safe_get,
            process_description_fn=process_description,
        )
    )
    parts.extend(_empty_cv_field_lines())
    parts.append("}}")
    return parts


__all__ = [
    "build_operator_parts_without_local_json",
    "_empty_voice_template_lines",
]
