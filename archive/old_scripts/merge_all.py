# -*- coding: utf-8 -*-
"""merge_all：合并各范围结果 → substances_all.json（统一 9 元向量 + scope 字段）+ 统计。"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
SCOPE_NAME = {1: "动素", 2: "散素", 3: "聚素+散素", 4: "聚素+动素", 5: "动素+散素", 6: "三类混合"}


def load_dong_san(path, scope, elems):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for x in data:
        vec = [0] * 9
        feed = [0] * 9
        for e, c in zip(elems, x["vec"]):
            vec[P.ORDER.index(e)] = c
        for e, c in zip(elems, x["feed"]):
            feed[P.ORDER.index(e)] = c
        item = dict(x)
        item["scope"] = scope
        item["vec"] = vec
        item["feed"] = feed
        item["cats"] = "-".join(sorted({P.CAT[e] for e in x["atoms"]}, key=lambda c: "聚动散".index(c)))
        item["bonds"] = [x["bond"]] * len(x["edges"])
        out.append(item)
    return out


def main():
    allitems = []
    allitems += load_dong_san(BASE + r"\substances_dong.json", 1, ["P", "W", "L"])
    allitems += load_dong_san(BASE + r"\substances_san.json", 2, ["K", "A", "F"])
    for sid in (3, 4, 5, 6):
        path = BASE + rf"\substances_league_s{sid}.json"
        data = json.load(open(path, encoding="utf-8"))
        for x in data:
            x["scope"] = sid
        allitems += data
    # 每个范围补 scope_name
    for x in allitems:
        x["scope_name"] = SCOPE_NAME[x["scope"]]
    # 去重：同一 scope 内同 formula 只留一条
    seen = set()
    dedup = []
    for x in allitems:
        k = (x["scope"], x["formula"])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(x)
    dedup.sort(key=lambda x: (x["scope"], x["natoms"], x["vec"]))
    json.dump(dedup, open(BASE + r"\substances_all.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved substances_all.json:", len(dedup), "条")

    # 统计
    stat = defaultdict(lambda: defaultdict(int))
    for x in dedup:
        stat[x["scope"]][x["cats"]] += 1
    pure = {"聚", "动", "散"}
    for sid in sorted(stat):
        print(f"\n范围{sid} {SCOPE_NAME[sid]}:")
        for cats, n in sorted(stat[sid].items()):
            print(f"  {cats:12s} {n}")
        newcat = {"1": "动", "2": "散"}.get(str(sid))
        if newcat is None:
            cross = sum(n for cats, n in stat[sid].items() if "-" in cats)
            print(f"  → 跨类新物质（不计纯大类）: {cross}")
    # 三类混合
    tc = [x for x in dedup if x["scope"] == 6 and x["cats"] == "聚-动-散"]
    print(f"\n范围6 三类同时出现的物质: {len(tc)} 种（≤10 原子截断）")
    print("  例:", " ".join(f"{x['formula']}({x['natoms']})" for x in tc[:20]))


if __name__ == "__main__":
    main()
