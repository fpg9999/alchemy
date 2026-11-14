# -*- coding: utf-8 -*-
"""merge_extended_inputs：把多轮扩展扫描的"新增物质"合并成按类别完整清单，供 build_finite_lists 用。

extended_finite.json    = 第一轮全枚举（已含 ≤16 与部分 >16）
extended_finite2.json   = 增量高原子数档（5/6 元类别等）
extended_finite3.json   = 5 元类别更高档
extended_finite4.json   = 6 元类别更高档
输出 extended_finite_merged.json（每类别完整物质列表）
"""
import json

BASE = r"G:\AI work\deepseek\work1\alchemy"


def load(name):
    try:
        return json.load(open(BASE + "\\" + name, encoding="utf-8"))
    except Exception:
        return {}


def main():
    merged = {}
    for name in ("extended_finite.json", "extended_finite2.json",
                 "extended_finite3.json", "extended_finite4.json", "extended_finite4b.json"):
        d = load(name)
        for cat, v in d.items():
            m = merged.setdefault(cat, {})
            for s in v.get("substances", []):
                m[s["formula"]] = s
    out = {}
    for cat, items in merged.items():
        lst = list(items.values())
        lst.sort(key=lambda x: (x["natoms"], x["formula"]))
        out[cat] = {"substances": lst,
                    "max": max((x["natoms"] for x in lst), default=0),
                    "count": len(lst)}
    json.dump(out, open(BASE + r"\extended_finite_merged.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("merged 类别:", len(out))
    for k in sorted(out):
        print(f"  {k}: {out[k]['count']} 种, 最大 {out[k]['max']} 原子")


if __name__ == "__main__":
    main()
