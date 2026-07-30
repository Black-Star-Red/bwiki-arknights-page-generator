# -*- coding: utf-8 -*-
import re
import json
from pathlib import Path
from collections import defaultdict

log_dir = Path(__file__).resolve().parents[1] / "log"
files = sorted(log_dir.glob("*.log"))
SPECIAL = ["罗德岛隐秘队", "时隙", "机械师", "矩"]


def clean_name(raw: str) -> str:
    raw = raw.strip()
    raw = re.split(r"\s+char_id=", raw, maxsplit=1)[0].strip()
    return raw


def remark(mastery, src):
    flags = []
    if not mastery:
        flags.append("空")
    if mastery and (len(mastery) > 80 or (mastery.endswith("X") and "(" in mastery)):
        flags.append("截断")
    if mastery and re.search(r"[A-Za-z]{4,}", mastery) and ("<" in mastery or "|" in mastery):
        flags.append("噪声")
    return "/".join(dict.fromkeys(flags))


def parse_dict_line(line: str):
    """Extract (name, mastery) from {'干员': {... '专精': '...' ...}}"""
    m = re.search(r"\{'([^']+)':\s*\{", line)
    if not m:
        return None, None
    name = m.group(1)
    dm = re.search(r"['\"]专精['\"]\s*:\s*['\"]([^'\"]*)['\"]", line)
    if not dm:
        return name, None
    return name, dm.group(1)


records = []
for f in files:
    date_str = f.stem
    for lineno, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if "已写入 operator_supplementary" in line:
            m = re.search(r"已写入 operator_supplementary[：:]\s*(.+?)专精=(.*)$", line)
            if not m:
                continue
            name = clean_name(m.group(1))
            mastery = m.group(2).strip()
            records.append({"date": date_str, "name": name, "mastery": mastery, "src": "write", "prio": 2, "lineno": lineno})
            continue

        if "'专精'" not in line and '"专精"' not in line:
            continue
        if any(x in line for x in ("ocr_scan_hit", "ocr_coarse", "OCR干员点识别")):
            continue

        name, mastery = parse_dict_line(line)
        if name is not None:
            records.append({"date": date_str, "name": name, "mastery": mastery or "", "src": "dict", "prio": 1, "lineno": lineno})
            continue

        # bare {'专精': '...'} — skip unassociated noise
        if re.fullmatch(r"\s*\[?\d{4}-\d{2}-\d{2}.*\[INFO\]\s*\{'专精': '[^']*'\}\s*", line) or (
            line.strip().endswith("}") and "{'专精'" in line and line.count("'") <= 6
        ):
            continue

by = defaultdict(list)
for r in records:
    by[r["name"]].append(r)
for name in by:
    by[name].sort(key=lambda x: (x["date"], x["prio"], x["lineno"]))

chosen = {}
for name, recs in by.items():
    pick = None
    for r in reversed(recs):
        if r["mastery"]:
            pick = r
            break
    if pick is None:
        pick = recs[-1]
    chosen[name] = {**pick, "remark": remark(pick["mastery"], pick["src"])}

empty_events = sorted(set((r["name"], r["date"]) for r in records if not r["mastery"]))

result = {
    "log_files": [f.name for f in files],
    "raw_hits": len(records),
    "unique": sorted([{"name": n, "date": v["date"], "mastery": v["mastery"], "remark": v["remark"], "src": v["src"]} for n, v in chosen.items()], key=lambda x: x["name"]),
    "empty_mastery_events": [{"name": n, "date": d} for n, d in empty_events],
    "special": {s: {k: chosen[s][k] for k in ("date", "mastery", "remark", "src")} if s in chosen else None for s in SPECIAL},
}
Path(__file__).resolve().parent.joinpath("_mastery_result.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
