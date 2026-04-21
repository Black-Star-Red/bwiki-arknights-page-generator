"""Operator attribute field renderers."""

from __future__ import annotations

from arknights_toolbox.shared.globals import TRUST_ATTRIBUTE_LABELS


def render_operator_potential_fields(mapper):
    """渲染潜能字段。"""
    lines: list[str] = []
    potential_ranks = mapper.get_data_safe("character_table", "potentialRanks")
    for i in range(2, 7):
        description = ""
        if potential_ranks and len(potential_ranks) > i - 2:
            description = potential_ranks[i - 2].get("description", "")
        lines.append(f"|潜能{i}={description}")
    return lines


def render_operator_trust_fields(mapper):
    """渲染信赖加成字段。"""
    lines: list[str] = []
    favor_data = mapper.get_data_safe("character_table", "{favorKeyFrames}[1].data")
    for attribute_key, attribute_value in TRUST_ATTRIBUTE_LABELS.items():
        data = favor_data.get(attribute_key, 0) if favor_data else 0
        lines.append(f"|信赖{attribute_value}={('+' + str(data)) if data > 0 else ''}")
    return lines


__all__ = ["render_operator_potential_fields", "render_operator_trust_fields"]
