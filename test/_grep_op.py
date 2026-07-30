import re, json
from pathlib import Path
ops = ["矩", "望", "时隙", "机械师", "罗德岛隐秘队"]
log_dir = Path(r"F:/项目/arknights_toolbox/log")
res={}
for op in ops:
    hits=[]
    for f in sorted(log_dir.glob("*.log")):
        for i,line in enumerate(f.read_text(encoding="utf-8").splitlines(),1):
            if op not in line: continue
            if "专精" in line or "operator_supplementary" in line:
                hits.append(f"{f.name}:{i}:{line[:200]}")
    res[op]=hits[-8:]
print(json.dumps(res, ensure_ascii=False, indent=2))
