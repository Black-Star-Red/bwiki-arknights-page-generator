"""Voice and CV rendering helpers."""

from __future__ import annotations

from data.mapper_helpers import bind_charword

# 与 B 站方舟 Wiki 常见一星干员页一致：中文 CV 在前，日配次之
_CV_FIELD_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CV", ("JP",)),
    ("CV中", ("CN_MANDARIN", "CHINESE", "CHINESE_MAINLAND")),
    ("CV英", ("ENGLISH", "EN_US", "EN_GB")),
    ("CV韩", ("KOREAN", "KR")),
    ("CV方", ("CUSTOM", "CN_TOPOLECT", "LINKAGE", "REGIONAL")),
)


def render_operator_cv_fields(mapper, char_id):
    """干员CV模板（固定顺序：CV中 → CV → CV英 → CV韩 → CV方）。"""
    lines: list[str] = []
    bind_charword(mapper, char_id)
    voice_dict = mapper.get_data_safe("charword_table", "voice_lang_dict") or {}
    for field, lang_keys in _CV_FIELD_SPECS:
        text = ""
        for lang in lang_keys:
            entry = voice_dict.get(lang)
            if not entry:
                continue
            names = entry.get("cvName") or []
            if names:
                text = "，".join(str(n) for n in names)
                break
        lines.append(f"|{field}={text}")
    return lines


def render_operator_voice_template_lines(mapper, char_id, name, voice_map):
    """Render 干员语音/套 template lines."""
    lines: list[str] = []
    lines.append("{{干员语音/套")
    lines.append(f"|所属干员={name}")
    lines.append("|所属皮肤=默认")
    lines.append("|语言=中文-普通话")
    for number, description in voice_map.items():
        bind_charword(mapper, char_id, voice_key=f"{char_id}_CN_{number}")
        voice_text = mapper.get_data_safe("charword_table", "voice_text", default="") or ""
        if "Dr.{@nickname}" in voice_text:
            voice_text = voice_text.replace("Dr.{@nickname}", "博士")
        lines.append(f"|{description}={voice_text}")
    lines.append("}}")
    return lines


__all__ = ["render_operator_cv_fields", "render_operator_voice_template_lines"]
