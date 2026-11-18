# -*- coding: utf-8 -*-
"""extract_feed_map：从全扫描 substances_league_s6.json 提取每个分子式的"一个真实投料例"。

该投料例来自实际成功反应（整锅产物都可摆），可直接作为物质清单里的"投料例"。
输出 catalog_feed_map.json（formula -> 9 元投料计数）。
"""
import json

BASE = r"G:\AI work\deepseek\work1\alchemy"
src = json.load(open(BASE + r"\substances_league_s6.json", encoding="utf-8"))
print("条数:", len(src), flush=True)
out = {}
for x in src:
    f = x["formula"]
    if f in out:
        continue
    feed = x.get("feed")
    if feed:
        out[f] = list(feed)
json.dump(out, open(BASE + r"\catalog_feed_map.json", "w", encoding="utf-8"),
          ensure_ascii=False)
print("saved catalog_feed_map.json:", len(out))
