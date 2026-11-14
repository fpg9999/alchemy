# -*- coding: utf-8 -*-
"""classify_from_all：根据 all511.json 的实测证据，给 511 类别做最终分类。

证据分级：
  强：T=32 成功整锅且最大分子 >=24  或 T=24 最大 >=20
  中：最大 >=17
  弱（有限）：≤16
单调性：若类别 S 有证据（无限），其超集也无限。因此取"有证据类别"的极小 antichain 作为无限核心；
其余类别：含核心 → 无限；否则有限（≤16 实测封顶）。
"""
import itertools
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def key(elems):
    return "/".join(sorted(elems, key=lambda e: P.ORDER.index(e)))


def main():
    raw = json.load(open(BASE + r"\all511.json", encoding="utf-8"))
    cat = {}
    for k, v in raw.items():
        elems = k.split("/")
        m24 = v.get("24", {}).get("max", 0)
        m32 = v.get("32", {}).get("max", 0)
        strong = (m32 >= 24) or (m24 >= 20)
        medium = (m32 >= 17) or (m24 >= 17)
        cat[k] = {"elems": elems, "n": len(elems), "max24": m24, "max32": m32,
                  "strong": strong, "evidence": strong or medium,
                  "info32": v.get("32", {}).get("info"),
                  "info24": v.get("24", {}).get("info")}
    ev = {frozenset(v["elems"]) for v in cat.values() if v["evidence"]}
    # 极小证据集合（antichain）
    minimal = [m for m in ev if not any(o < m for o in ev)]
    minimal = sorted(minimal, key=lambda m: (len(m), [P.ORDER.index(e) for e in sorted(m, key=lambda e: P.ORDER.index(e))]))
    # 每个类别是否含核心
    out = {}
    for k, v in cat.items():
        S = frozenset(v["elems"])
        cores = [m for m in minimal if m <= S]
        v["infinite"] = bool(cores)
        v["cores"] = [key(m) for m in cores]
        v["direct_evidence"] = v["evidence"]
        out[k] = v
    stats = {
        "n_categories": len(out),
        "n_infinite": sum(1 for v in out.values() if v["infinite"]),
        "n_finite": sum(1 for v in out.values() if not v["infinite"]),
        "n_minimal_evidence": len(minimal),
        "minimal": [key(m) for m in minimal],
        "infinite_by_size": {r: sum(1 for v in out.values() if v["infinite"] and v["n"] == r) for r in range(1, 10)},
        "finite_by_size": {r: sum(1 for v in out.values() if not v["infinite"] and v["n"] == r) for r in range(1, 10)},
        "evidence_by_size": {r: sum(1 for v in out.values() if v["evidence"] and v["n"] == r) for r in range(1, 10)},
        "strong_by_size": {r: sum(1 for v in out.values() if v["strong"] and v["n"] == r) for r in range(1, 10)},
    }
    json.dump(out, open(BASE + r"\all511_classified.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(stats, open(BASE + r"\all511_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print("\n最小实测无限集合:")
    for m in minimal:
        print("  ", key(m), "max24=", cat[key(m)]["max24"], "max32=", cat[key(m)]["max32"],
              cat[key(m)]["info32"])
    print("\n未覆盖的'中等证据'类别:")
    for k, v in out.items():
        if v["evidence"] and not any(frozenset(m) < frozenset(v["elems"]) for m in minimal):
            pass
    print("saved all511_classified.json / all511_stats.json")


if __name__ == "__main__":
    main()
