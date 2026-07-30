import re
from pathlib import Path
log_dir = Path(r"F:/项目/arknights_toolbox/log")
empty_lines = []
for f in sorted(log_dir.glob("*.log")):
    for i,line in enumerate(f.read_text(encoding="utf-8").splitlines(),1):
        if re.search(r"['\"]专精['\"]\s*:\s*['\"]['\"]", line):
            empty_lines.append(f"{f.name}:{i}")
        if "已写入 operator_supplementary" in line and re.search(r"专精=\s*$", line):
            empty_lines.append(f"{f.name}:{i}:write")
print(len(empty_lines))
for x in empty_lines[:20]:
    print(x)
