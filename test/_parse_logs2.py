# -*- coding: utf-8 -*-
import re
import json
from pathlib import Path

log_dir = Path(r"F:/项目/arknights_toolbox/log")
files = sorted(log_dir.glob("*.log"))
SPECIAL = ["罗德岛隐秘队", "时隙", "机械师", "矩"]

records = []  # all hits chronologically

for f in files:
    date_str = f.stem
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    last_operator = None
    for lineno, line in enumerate(lines, 1):
        # track operator from OCR warning lines
        wm = re.search(r"OCR.*?path=\./photo/([^\s]+\.jpg).*?final=([^\s]+)", line)
        if wm:
            last_operator = wm.group(1).replace(".jpg", "")

        if "已写入 operator_supplementary" in line:
            m = re.search(r"已写入 operator_supplementary[：:]\s*(.+?)专精=(.*)$", line)
            if not m:
                continue
            name = m.group(1).strip()
            name = re.sub(r"\s+(技能|模块|信赖|等级|潜能)=.*$", "", name).strip()
            mastery = m.group(2).strip()
            flags = remark_flags(name, mastery, "write")
            records.append(dict(date=date_str, name=name, mastery=mastery, file=f.name, flags=flags, src="write"))
            last_operator = name
            continue

        if "'专精'" in line or '"专精"' in line:
            if any(x in line for x in ("ocr_scan_hit", "ocr_coarse", "OCR干员点识别")):
                continue
            dm = re.search(r"['\"]专精['\"]\s*:\s*['\"]([^'\"]*)['\"]", line)
            if not dm:
                continue
            mastery = dm.group(1)
            name = None
            for key in ("干员", "name", "operator", "charName"):
                nm = re.search(rf"['\"]{key}['\"]\s*:\s*['\"]([^'\"]+)['\"]", line)
                if nm:
                    name = nm.group(1)
                    break
            if not name:
                name = last_operator
            flags = remark_flags(name or "", mastery, "dict")
            if not name:
                flags = list(dict.fromkeys(flags + ["噪声"]))
            records.append(dict(date=date_str, name=name or "", mastery=mastery, file=f.name, flags=flags, src="dict"))


def remark_flags(name, mastery, src):
    flags = []
    if not mastery:
        flags.append("空")
    if mastery and (len(mastery) > 80 or mastery.endswith("|") or mastery.count("<") >= 2):
        flags.append("截断")
    if mastery and re.search(r"[A-Za-z]{3,}.*[<>\|]", mastery):
        flags.append("噪声")
    if src == "dict" and not name:
        flags.append("噪声")
    return flags

# fix forward reference
def remark_flags(name, mastery, src):
    flags = []
    if not mastery:
        flags.append("空")
    if mastery and (len(mastery) > 80 or mastery.endswith("|") or mastery.count("<") >= 2):
        flags.append("截断")
    if mastery and re.search(r"[A-Za-z]{3,}.*[<>\|]", mastery):
        flags.append("噪声")
    return flags

# re-run parse with function defined first - rewrite cleanly below
