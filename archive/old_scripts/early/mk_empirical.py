# -*- coding: utf-8 -*-
"""mk_empirical：从 all_classified_stats.json 生成最小无限集合文件（供 families/catalog 用）。"""
import json

BASE = r"G:\AI work\deepseek\work1\alchemy"
st = json.load(open(BASE + r"\all_classified_stats.json", encoding="utf-8"))
out = {"minimal": st["minimal"], "inf3": st["minimal"], "inf4": [], "inf5": []}
json.dump(out, open(BASE + r"\minimal_empirical.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("minimal:", len(st["minimal"]), st["minimal"])
