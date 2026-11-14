# -*- coding: utf-8 -*-
"""make_index：把 substances_all.json 压成轻量索引（分子式/原子数/投料例/分类），便于查看。"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
data = json.load(open(BASE + r"\substances_all.json", encoding="utf-8"))
out = []
for x in data:
    out.append({
        "scope": x.get("scope"),
        "scope_name": x.get("scope_name"),
        "formula": x["formula"],
        "zh": x.get("zh"),
        "natoms": x["natoms"],
        "vec": x["vec"],
        "feed": x["feed"],
        "cats": x.get("cats"),
    })
json.dump(out, open(BASE + r"\substances_index.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved substances_index.json:", len(out), "条")
