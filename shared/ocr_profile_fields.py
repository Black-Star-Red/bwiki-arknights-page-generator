"""从 OCR 合并文本解析档案字段（无 Paddle 依赖，便于单测）。"""

from __future__ import annotations

import re
from typing import Callable

WarnFn = Callable[[str, object], None] | None


def split_artist_names(
    fragment: str,
    *,
    allow_single_char: bool = False,
) -> list[str]:
    """按顿号等拆分画师名，去掉空白段。"""
    fragment = (fragment or "").strip().lstrip("：:").strip()
    if not fragment:
        return []
    names: list[str] = []
    for part in re.split(r"[、,，/\\]", fragment):
        part = part.strip()
        if not part or part in ("绘制", "原案", "绑制"):
            continue
        if len(part) == 1 and part in _LABEL_FRAGMENT_CHARS:
            continue
        if len(part) == 1 and not allow_single_char:
            continue
        names.append(part)
    return names


def format_drawer_string(drawer_names: list[str], designer_names: list[str]) -> str:
    """
    拼接 Wiki |画师= 文案：绘制名用顿号连接，原案名追加（原案）。

    例：Studio Montagne、Skade（原案）
    """
    parts: list[str] = []
    for n in drawer_names:
        n = _clean_ocr_name_line(n)
        if n:
            parts.append(n)
    for n in designer_names:
        n = _clean_ocr_name_line(n)
        if n:
            parts.append(f"{n}（原案）")
    return "、".join(parts)


def _inline_has_multiple_artists(inline_tail: str) -> bool:
    """同行已用顿号列出多名画师时才续读多行。"""
    tail = inline_tail or ""
    return "、" in tail or "，" in tail or "," in tail


_DRAW_LABEL_RE = re.compile(r"^[\sO0o○●◯]*(?:绘制|绑制)\s*[：:]?\s*(.*)$", re.I)
_DESIGN_LABEL_RE = re.compile(r"^原案\s*[：:]?\s*(.*)$", re.I)

# OCR 预告图：绘制/原案 后常接档案其它字段
_STOP_LINE_RE = re.compile(
    r"^(?:专精|身高|特性|种族|出身|中文|日文|日CV|联动|第一|第二|第三|■|©|MONS|ARKN|HUNTER|期|先锋|近卫|狙击|术师|医疗|辅助|特种|重装|召唤)",
    re.I,
)

# 无「原案」时绘制后最多再读几行（正常 1 行画师名，留 1 行给标签碎片）
_MAX_FOLLOW_LINES_DRAW = 2
_MAX_FOLLOW_LINES_DESIGN = 2

# 「绘制/绑制」被 OCR 拆成单字时的标签残片（不作画师名）
_LABEL_FRAGMENT_CHARS = frozenset("制绘绑案")
# 弱锚点仅用「绑制」残片；「绘」常接下一行画师名（见 _find_weak_draw_label_index）
_WEAK_DRAW_LABEL_CHARS = frozenset("制绑案")
# 行首符号剥除（与「-StudioMontagne」同理，含 OCR 常见 •·）
_ARTIST_NAME_LEADING_JUNK_RE = re.compile(
    r"^[\u2022\u00b7\u30fb•·・\*＊\+\-–—\s]+"
)
_LEADING_NAME_STRIP = "-–—•·・*＊+ \t"

# 技能/特性描述误入画师区
_SKILL_DESC_RE = re.compile(
    r"援军|部署|攻击|伤害|天赋|特性|提升|阻挡|费用|引爆|晕眩|物理|法术|冷却|范围内|敌人|干员|回复\d|至\d+%|%；",
)


def _clean_ocr_name_line(line: str) -> str:
    """剥除行首 -、•、· 等 OCR 噪声，保留画师名本体。"""
    ln = (line or "").strip()
    ln = _ARTIST_NAME_LEADING_JUNK_RE.sub("", ln)
    return ln.lstrip(_LEADING_NAME_STRIP).strip()


def _is_label_fragment_line(line: str) -> bool:
    ln = _clean_ocr_name_line(line)
    return len(ln) == 1 and ln in _LABEL_FRAGMENT_CHARS


def _is_weak_draw_label_line(line: str) -> bool:
    """完整「绘制/绑制」未识别时，绑/制/案残片可作弱锚点（不含单独「绘」）。"""
    ln = _clean_ocr_name_line(line)
    return len(ln) == 1 and ln in _WEAK_DRAW_LABEL_CHARS


def _is_split_draw_label_pair(lines: list[str], index: int) -> bool:
    """OCR 把「绘制/绑制」拆成「P」+「制」两行。"""
    if index + 1 >= len(lines):
        return False
    head = _clean_ocr_name_line(lines[index])
    return len(head) == 1 and head in "P绘绑" and _is_label_fragment_line(lines[index + 1])


def _is_draw_fragment_then_artist(lines: list[str], index: int) -> bool:
    """「绘」独占一行且下一行像画师名（风絮：绘 / •二开）。"""
    if index + 1 >= len(lines):
        return False
    if _clean_ocr_name_line(lines[index]) != "绘":
        return False
    return _looks_like_artist_name_line(lines[index + 1], allow_single_char=False)


def _find_weak_draw_label_index(lines: list[str]) -> int | None:
    for i, line in enumerate(lines):
        if _DRAW_LABEL_RE.match(line):
            continue
        if _is_weak_draw_label_line(line):
            return i
        if _is_split_draw_label_pair(lines, i):
            return i
        if _is_draw_fragment_then_artist(lines, i):
            return i
    return None


def _names_start_after_weak_label(lines: list[str], index: int) -> int:
    if _is_split_draw_label_pair(lines, index):
        return index + 2
    if _clean_ocr_name_line(lines[index]) == "绘":
        return index + 1
    return index + 1


def _is_drawer_stop_line(line: str) -> bool:
    line = _clean_ocr_name_line(line)
    if not line:
        return True
    if _DESIGN_LABEL_RE.match(line) or _DRAW_LABEL_RE.match(line):
        return True
    return bool(_STOP_LINE_RE.match(line))


def _looks_like_artist_name_line(line: str, *, allow_single_char: bool = False) -> bool:
    """画师名通常较短；技能说明等长句应在此截断。"""
    ln = _clean_ocr_name_line(line)
    if not ln or _is_drawer_stop_line(ln):
        return False
    if re.fullmatch(r"\d+", ln):
        return False
    if ln in "*#＊":
        return False
    if len(ln) == 1:
        if ln in _LABEL_FRAGMENT_CHARS or not allow_single_char:
            return False
        return True
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


def _append_name(
    names: list[str],
    raw_line: str,
    *,
    allow_single_char: bool,
    warn: WarnFn,
) -> None:
    ln = _clean_ocr_name_line(raw_line)
    for part in split_artist_names(ln, allow_single_char=allow_single_char):
        part = _clean_ocr_name_line(part)
        if not part or part in "*#＊":
            continue
        if len(part) == 1 and warn is not None:
            warn("ocr_drawer_single_char_name name=%s", part)
        names.append(part)


def _collect_names_after_label(
    lines: list[str],
    start: int,
    inline_tail: str,
    *,
    max_follow: int,
    warn: WarnFn = None,
    allow_single_char_name: bool = False,
    only_first_line: bool = False,
) -> tuple[list[str], int]:
    """同行有内容则用之；否则读取后续行直至原案/档案字段/非画师行/行数上限。"""
    names: list[str] = []
    tail = _clean_ocr_name_line(inline_tail)
    if tail:
        _append_name(
            names,
            tail,
            allow_single_char=allow_single_char_name,
            warn=warn,
        )
        return names, start

    j = start
    taken = 0
    saw_fragment = False
    scan_end = start
    awaiting_after_fragment = False

    while j < len(lines) and taken < max_follow:
        raw = lines[j]
        ln = _clean_ocr_name_line(raw)
        scan_end = j + 1
        if _is_drawer_stop_line(ln):
            break
        if _is_label_fragment_line(ln):
            saw_fragment = True
            awaiting_after_fragment = True
            j += 1
            continue
        if awaiting_after_fragment:
            awaiting_after_fragment = False
            if _looks_like_artist_name_line(
                raw, allow_single_char=allow_single_char_name
            ):
                _append_name(
                    names,
                    raw,
                    allow_single_char=allow_single_char_name,
                    warn=warn,
                )
                taken += 1
            elif warn is not None:
                warn("ocr_drawer_after_fragment_rejected line=%s", ln)
            j += 1
            break
        if not _looks_like_artist_name_line(raw, allow_single_char=allow_single_char_name):
            break
        _append_name(
            names,
            raw,
            allow_single_char=allow_single_char_name,
            warn=warn,
        )
        taken += 1
        j += 1
        if only_first_line:
            break

    if not names and allow_single_char_name and not only_first_line:
        for k in range(start, scan_end):
            raw = lines[k]
            ln = _clean_ocr_name_line(raw)
            if _is_drawer_stop_line(ln) or _is_label_fragment_line(ln):
                continue
            if _looks_like_artist_name_line(raw, allow_single_char=True):
                if warn is not None:
                    warn("ocr_drawer_fallback_single_char line=%s", ln)
                _append_name(names, raw, allow_single_char=True, warn=warn)
                if names:
                    break

    if not names and saw_fragment and warn is not None:
        warn("ocr_drawer_label_fragment_no_name after_label_line=%s", start - 1)

    return names, j


def _collect_one_drawer_name_after_anchor(
    lines: list[str],
    anchor_index: int,
    *,
    warn: WarnFn = None,
) -> list[str]:
    """「绘/制」弱锚点后只取紧邻一行画师名（风絮/矩：无二连画师、无 *）。"""
    start = _names_start_after_weak_label(lines, anchor_index)
    if start >= len(lines):
        return []
    raw = lines[start]
    if not _looks_like_artist_name_line(raw, allow_single_char=False):
        if warn is not None:
            warn(
                "ocr_drawer_after_fragment_rejected line=%s",
                _clean_ocr_name_line(raw),
            )
        return []
    names: list[str] = []
    _append_name(names, raw, allow_single_char=False, warn=warn)
    return names


def _scan_labeled_sections(
    lines: list[str],
    *,
    warn: WarnFn,
    use_weak_draw_label: bool,
) -> tuple[list[str], list[str]]:
    drawer_names: list[str] = []
    designer_names: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        dm = _DRAW_LABEL_RE.match(line)
        if dm:
            inline = dm.group(1) or ""
            multi = _inline_has_multiple_artists(inline)
            chunk, nxt = _collect_names_after_label(
                lines,
                i + 1,
                inline,
                max_follow=_MAX_FOLLOW_LINES_DRAW if multi else 1,
                warn=warn,
                allow_single_char_name=False,
                only_first_line=not multi,
            )
            drawer_names.extend(chunk)
            i = max(i + 1, nxt)
            continue
        ym = _DESIGN_LABEL_RE.match(line)
        if ym:
            inline = ym.group(1) or ""
            multi = _inline_has_multiple_artists(inline)
            chunk, nxt = _collect_names_after_label(
                lines,
                i + 1,
                inline,
                max_follow=_MAX_FOLLOW_LINES_DESIGN if multi else 1,
                warn=warn,
                allow_single_char_name=False,
                only_first_line=not multi,
            )
            designer_names.extend(chunk)
            i = max(i + 1, nxt)
            continue
        i += 1

    if use_weak_draw_label and not drawer_names:
        weak_at = _find_weak_draw_label_index(lines)
        if weak_at is not None:
            if warn is not None:
                warn(
                    "ocr_drawer_weak_label line=%s",
                    _clean_ocr_name_line(lines[weak_at]),
                )
            chunk = _collect_one_drawer_name_after_anchor(
                lines, weak_at, warn=warn
            )
            drawer_names.extend(chunk)

    return drawer_names, designer_names


def extract_drawer(text: str, *, warn: WarnFn = None) -> str | None:
    """从 OCR 全文提取「绘制」「原案」并合成画师字符串。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    drawer_names, designer_names = _scan_labeled_sections(
        lines,
        warn=warn,
        use_weak_draw_label=False,
    )
    if not drawer_names:
        extra_drawer, _ = _scan_labeled_sections(
            lines,
            warn=warn,
            use_weak_draw_label=True,
        )
        drawer_names.extend(extra_drawer)

    if not drawer_names and not designer_names:
        return None
    out = format_drawer_string(drawer_names, designer_names)
    return out or None


# 预告图 OCR 常把「专精」识别为 ·专精·、专精· 等，仅允许标签前为符号
_MASTERY_LINE_PREFIX_RE = re.compile(
    r"^[\s\u2022\u00b7\u30fb•·・\*＊\+\-–—【\[\]】]*专精"
)
_MASTERY_STOP_RE = re.compile(
    r"^(?:绘制|绑制|原案|绘|精英化|等级|职业|分支|标签|综合体检测|初始开放|基建技能|特性|天赋|"
    r"招聘合同|客观履历|临床诊断|造影检测|矿石病感染情况|体细胞与源石|血液源石结晶密度|"
    r"物理强度|战场机动|生理耐受|战术规划|战斗技巧|后勤技能|源石技艺适应性|"
    r"模组|潜能|再部署|部署费用|阻挡数|攻击范围|初始携带|"
    r"身高|体重|性别|种族|生日|出身|中文CV|中)",
    re.I,
)
_MAX_FOLLOW_LINES_MASTERY = 12


def _mastery_label_core(line: str) -> str | None:
    """从「·专精·」等行取出以专精开头的片段；非标签行（如协助专精训练）返回 None。"""
    ln = (line or "").strip()
    if "专精" not in ln or not _MASTERY_LINE_PREFIX_RE.match(ln):
        return None
    return ln[ln.find("专精") :]


def _is_mastery_label_line(line: str) -> bool:
    core = _mastery_label_core(line)
    if not core:
        return False
    if re.match(r"^[\s·•・\*＊\+\-–—：:]*专精[\s·•・\*＊\+\-–—：:]*$", core):
        return True
    return bool(re.match(r"^专精\s*[：:]", core))


def _is_valid_mastery_part(part: str) -> bool:
    p = _clean_ocr_name_line(part).lstrip("：:").strip()
    if not p or p == "专精":
        return False
    if len(p) == 1 and p in _LABEL_FRAGMENT_CHARS:
        return False
    if p in "*＊" or re.fullmatch(r"[\s·•・\*＊、，,]+", p):
        return False
    return len(p) >= 2 or any("\u4e00" <= c <= "\u9fff" for c in p)


def _split_mastery_parts(fragment: str) -> list[str]:
    fragment = (fragment or "").strip().lstrip("：:").strip()
    if not fragment:
        return []
    parts: list[str] = []
    for segment in re.split(r"[、,，]", fragment):
        p = _clean_ocr_name_line(segment).lstrip("：:").strip()
        if _is_valid_mastery_part(p):
            parts.append(p)
    return parts


def _inline_mastery_from_label(line: str) -> list[str]:
    core = _mastery_label_core(line)
    if not core:
        return []
    same = re.search(r"^专精\s*[：:]\s*(.+)$", core)
    if same:
        return _split_mastery_parts(same.group(1))
    if re.match(r"^专精[\s·•・\*＊\-–—：:]*$", core):
        return []
    tail = re.search(r"^专精\s*(.+)$", core)
    if tail:
        return _split_mastery_parts(tail.group(1))
    return []


def _append_mastery_follow_parts(parts: list[str], raw_line: str) -> bool:
    """
    追加「专精」标签后的续行。返回本行是否以顿号结尾（还需续读下一行）。
    """
    line = (raw_line or "").strip()
    if not line:
        return False
    if line.endswith("、"):
        parts.extend(_split_mastery_parts(line[:-1]))
        return True
    cleaned = _clean_ocr_name_line(line)
    if not _is_valid_mastery_part(cleaned):
        return False
    for p in _split_mastery_parts(cleaned):
        if p not in parts:
            parts.append(p)
    return False


def extract_mastery(text: str) -> str | None:
    """从 OCR 全文提取「专精」研究方向列表（须以「专精」标签行起锚）。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    for i, line in enumerate(lines):
        if not _is_mastery_label_line(line):
            continue
        parts = _inline_mastery_from_label(line)
        continuation = False

        j = i + 1
        n = 0
        while j < len(lines) and n < _MAX_FOLLOW_LINES_MASTERY:
            nxt = lines[j]
            if _MASTERY_STOP_RE.match(nxt) or nxt.isdigit():
                break
            if len(nxt) < 2 and not _is_valid_mastery_part(nxt):
                n += 1
                j += 1
                continue

            before = len(parts)
            more = _append_mastery_follow_parts(parts, nxt)
            if len(parts) == before:
                n += 1
                j += 1
                continue

            if more:
                continuation = True
            elif continuation:
                continuation = False
                break
            else:
                break
            n += 1
            j += 1

        if parts:
            return "、".join(parts)
    return None


__all__ = [
    "extract_drawer",
    "extract_mastery",
    "format_drawer_string",
    "split_artist_names",
]
