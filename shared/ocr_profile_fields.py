"""从 OCR 合并文本解析档案字段（无 Paddle 依赖，便于单测）。"""

from __future__ import annotations

import re


def split_artist_names(fragment: str) -> list[str]:
    """按顿号等拆分画师名，去掉空白段。"""
    fragment = (fragment or "").strip().lstrip("：:").strip()
    if not fragment:
        return []
    names: list[str] = []
    for part in re.split(r"[、,，/\\]", fragment):
        part = part.strip()
        if part and part not in ("绘制", "原案"):
            names.append(part)
    return names


def format_drawer_string(drawer_names: list[str], designer_names: list[str]) -> str:
    """
    拼接 Wiki |画师= 文案：绘制名用顿号连接，原案名追加（原案）。

    例：Studio Montagne、Skade（原案）
    """
    parts: list[str] = []
    for n in drawer_names:
        n = (n or "").strip()
        if n:
            parts.append(n)
    for n in designer_names:
        n = (n or "").strip()
        if n:
            parts.append(f"{n}（原案）")
    return "、".join(parts)


_DRAW_LABEL_RE = re.compile(r"^(?:绘制|绑制)\s*[：:]?\s*(.*)$", re.I)
_DESIGN_LABEL_RE = re.compile(r"^原案\s*[：:]?\s*(.*)$", re.I)

# OCR 预告图：绘制/原案 后常接档案其它字段
_STOP_LINE_RE = re.compile(
    r"^(?:专精|身高|特性|种族|出身|中文|日文|日CV|联动|第一|第二|第三|■|©|MONS|ARKN|HUNTER|期|先锋|近卫|狙击|术师|医疗|辅助|特种|重装|召唤)",
    re.I,
)

# 无「原案」时绘制后最多再读几行（正常 1 行画师名）
_MAX_FOLLOW_LINES_DRAW = 1
_MAX_FOLLOW_LINES_DESIGN = 1

# 技能/特性描述误入画师区
_SKILL_DESC_RE = re.compile(
    r"援军|部署|攻击|伤害|天赋|特性|提升|阻挡|费用|引爆|晕眩|物理|法术|冷却|范围内|敌人|干员|回复\d|至\d+%|%；",
)


def _clean_ocr_name_line(line: str) -> str:
    return (line or "").strip().lstrip("-–—").strip()


def _is_drawer_stop_line(line: str) -> bool:
    line = _clean_ocr_name_line(line)
    if not line:
        return True
    if _DESIGN_LABEL_RE.match(line) or _DRAW_LABEL_RE.match(line):
        return True
    return bool(_STOP_LINE_RE.match(line))


def _looks_like_artist_name_line(line: str) -> bool:
    """画师名通常较短；技能说明等长句应在此截断。"""
    ln = _clean_ocr_name_line(line)
    if not ln or _is_drawer_stop_line(ln):
        return False
    if len(ln) > 48:
        return False
    if _SKILL_DESC_RE.search(ln):
        return False
    if re.search(r"[，。；！？、%（）《》「」“”]", ln):
        return False
    cjk = len(re.findall(r"[\u4e00-\u9fff]", ln))
    if cjk >= 5:
        return False
    return True


def _collect_names_after_label(
    lines: list[str],
    start: int,
    inline_tail: str,
    *,
    max_follow: int,
) -> tuple[list[str], int]:
    """同行有内容则用之；否则读取后续行直至原案/档案字段/非画师行/行数上限。"""
    names: list[str] = []
    tail = _clean_ocr_name_line(inline_tail)
    if tail:
        names.extend(split_artist_names(tail))
        return names, start
    j = start
    taken = 0
    while j < len(lines) and taken < max_follow:
        raw = lines[j]
        ln = _clean_ocr_name_line(raw)
        if _is_drawer_stop_line(ln):
            break
        if not _looks_like_artist_name_line(raw):
            break
        names.extend(split_artist_names(ln))
        taken += 1
        j += 1
    return names, j


def extract_drawer(text: str) -> str | None:
    """从 OCR 全文提取「绘制」「原案」并合成画师字符串。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    drawer_names: list[str] = []
    designer_names: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        dm = _DRAW_LABEL_RE.match(line)
        if dm:
            chunk, nxt = _collect_names_after_label(
                lines, i + 1, dm.group(1), max_follow=_MAX_FOLLOW_LINES_DRAW
            )
            drawer_names.extend(chunk)
            i = max(i + 1, nxt)
            continue
        ym = _DESIGN_LABEL_RE.match(line)
        if ym:
            chunk, nxt = _collect_names_after_label(
                lines, i + 1, ym.group(1), max_follow=_MAX_FOLLOW_LINES_DESIGN
            )
            designer_names.extend(chunk)
            i = max(i + 1, nxt)
            continue
        i += 1

    if not drawer_names and not designer_names:
        return None
    out = format_drawer_string(drawer_names, designer_names)
    return out or None


__all__ = [
    "extract_drawer",
    "format_drawer_string",
    "split_artist_names",
]
