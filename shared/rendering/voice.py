"""Voice and CV rendering helpers."""

from __future__ import annotations


def render_operator_cv_fields(mapper, char_id):
    """干员CV模板"""
    lines: list[str] = []
    map_language = {}
    for language, language_name in (mapper.get_data_safe("charword_table", "voiceLangTypeDict") or {}).items():
        if language == "JP":
            map_language["JP"] = ""
            continue
        type_name = language_name["name"][0] if language_name["name"] != "中文-方言" else "方"
        map_language[language] = type_name
    for language, cv in (mapper.get_data_safe("charword_table", f"voiceLangDict.{char_id}.dict") or {}).items():
        lines.append(f"|CV{map_language[language]}={'，'.join([cv_name for cv_name in cv['cvName']])}")
    return lines


def render_operator_voice_template_lines(mapper, char_id, name, voice_map):
    """Render 干员语音/套 template lines."""
    lines: list[str] = []
    lines.append("{{干员语音/套")
    lines.append(f"|所属干员={name}")
    lines.append("|所属皮肤=默认")
    lines.append("|语言=中文-普通话")
    for number, description in voice_map.items():
        voice_text = mapper.get_data_safe("charword_table", f"charWords.{char_id}_CN_{number}.voiceText", default="") or ""
        if "Dr.{@nickname}" in voice_text:
            voice_text = voice_text.replace("Dr.{@nickname}", "博士")
        lines.append(f"|{description}={voice_text}")
    lines.append("}}")
    return lines


__all__ = ["render_operator_cv_fields", "render_operator_voice_template_lines"]
