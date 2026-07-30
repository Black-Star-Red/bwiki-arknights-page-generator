import re, json
from pathlib import Path
log_dir = Path(r"F:/项目/arknights_toolbox/log")
out=[]
for f in sorted(log_dir.glob("*.log")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if "已写入 operator_supplementary" not in line:
            continue
        m=re.search(r"已写入 operator_supplementary[：:]\s*(.+?)专精=(.*)$", line)
        if m and not m.group(2).strip():
            name=re.split(r"\s+char_id=", m.group(1).strip(),1)[0]
            out.append((f.stem,name))
print(json.dumps(out, ensure_ascii=False, indent=2))
