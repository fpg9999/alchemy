# -*- coding: utf-8 -*-
"""t4_validate_catalog：用严格校验器复核既有目录（league s3/s4/s5/s6、dong、san）的摆放是否合法。

pot_all.embed_mol 有 L 中间格 bug（可能产出非法摆放）；但 scan_league 导出时会重新计算键型并检查
L 中点，因此目录条目应仍合法。本脚本逐条核对：价数、连通、坐标唯一、每条边偏移允许、L 中点空。
"""
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"


def check_item(x):
    atoms = x["atoms"]
    edges = [tuple(e) for e in x["edges"]]
    place = x.get("place")
    if place is None:
        return False, "no place"
    place = {int(k): tuple(v) for k, v in place.items()}
    return pot_v2.validate_place(place, atoms, edges)


def main():
    files = ["substances_league_s3.json", "substances_league_s4.json",
             "substances_league_s5.json", "substances_league_s6.json",
             "substances_dong.json", "substances_san.json"]
    for fn in files:
        try:
            data = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
        except FileNotFoundError:
            print(fn, "missing")
            continue
        bad = []
        for x in data:
            ok, msg = check_item(x)
            if not ok:
                bad.append((x.get("formula"), msg))
        print(f"{fn}: {len(data)} 条, 非法 {len(bad)} 条", flush=True)
        for b in bad[:5]:
            print("   ", b)


if __name__ == "__main__":
    main()
