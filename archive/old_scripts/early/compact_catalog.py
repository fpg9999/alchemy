# -*- coding: utf-8 -*-
"""compact_catalog：把 180MB 的全量物质 JSON 压成轻量目录（formula/natoms/atoms）。"""
import json
import sys

BASE = r"G:\AI work\deepseek\work1\alchemy"
src = json.load(open(BASE + r"\substances_league_s6.json", encoding="utf-8"))
print("原始条数:", len(src), flush=True)
out = []
seen = set()
for x in src:
    f = x["formula"]
    if f in seen:
        continue
    seen.add(f)
    out.append({"formula": f, "natoms": x["natoms"], "atoms": x["atoms"]})
json.dump(out, open(BASE + r"\catalog_raw_compact.json", "w", encoding="utf-8"),
          ensure_ascii=False)
print("saved catalog_raw_compact.json:", len(out))
