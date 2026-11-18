# -*- coding: utf-8 -*-
"""build_finite_lists：生成"有限类别完整物质清单"附录（分子式+中文名+原子数+投料例）。

- 数据来源：`catalog_raw_compact.json`（≤16 原子全目录）+ `extended_finite*.json`（>16 的扩展扫描）。
- 对每个"有限"类别：列出组成 ⊆ 类别的全部物质（≥16 部分若有扩展数据则补齐），
  投料例 = 该物质自身组成（9 元计数，已验证可由组成直接投料复现）。
输出：CATALOG_FINITE_LISTS.md
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def load(name):
    try:
        return json.load(open(BASE + "\\" + name, encoding="utf-8"))
    except Exception:
        return None


def main():
    cats = json.load(open(BASE + r"\catalog2_subsets.json", encoding="utf-8"))
    raw = load("catalog_raw_compact.json")
    extm = load("extended_finite_merged.json") or {}
    ext = load("extended_finite2.json") or {}
    ext1 = load("extended_finite.json") or {}
    feed_map = load("catalog_feed_map.json") or {}
    groups = defaultdict(dict)
    for x in raw:
        E = frozenset(x["atoms"])
        groups[E][x["formula"]] = x["natoms"]
    # 扩展数据：按类别缓存
    ext_by_cat = {}
    for src in (ext1, ext, extm):
        for cat, v in (src or {}).items():
            d = ext_by_cat.setdefault(cat, {})
            for s in v["substances"]:
                d[s["formula"]] = {"natoms": s["natoms"], "feed": s.get("feed")}

    finite = [x for x in cats if not x["infinite"]]
    print("有限类别:", len(finite), flush=True)
    L = []
    A = L.append
    A("# 有限类别 · 完整物质清单（分子式 + 中文名 + 原子数 + 投料例）")
    A("")
    A("> 投料例 = 全扫描中实际产生该物质的一个投料（9 元计数，顺序 O,X,C,P,W,L,K,A,F；整锅反应成功）。")
    A("> 绝大多数物质也可用它自身的元素组成直接投料复现（`verify_selfprod_all.py`），少数例外已改用真实投料例。")
    A("> 带 ★ 的类别含 >16 原子物质，其清单由扩展枚举补齐；其余类别物质 ≤16 原子。")
    A("")
    for ci, x in enumerate(finite, 1):
        S = set(x["elems"])
        key = "/".join(x["elems"])
        items = {}
        for E, fs in groups.items():
            if E <= S:
                items.update(fs)
        ex = ext_by_cat.get(key, {})
        for f, rec in ex.items():
            items[f] = rec["natoms"]
        cap = max(items.values()) if items else 0
        star = "★" if cap > 16 else ""
        A(f"## {ci}. {'/'.join(x['elems'])}（{x['zh']}）{star}")
        A("")
        A(f"- 元素：{'、'.join(x['elems'])}；物质数：**{len(items)}**；最大原子数：{cap}；类型：有限")
        A("")
        A("| # | 分子式 | 中文名 | 原子数 | 投料例 (O,X,C,P,W,L,K,A,F) |")
        A("|---|---|---|---|---|")
        for j, (f, natoms) in enumerate(sorted(items.items(), key=lambda kv: (kv[1], kv[0])), 1):
            vec = feed_map.get(f)
            if vec is None:
                exrec = ext_by_cat.get(key, {}).get(f)
                if exrec and exrec.get("feed"):
                    vec = exrec["feed"]
            if vec is None:
                vec = list(P.parse_formula(f))
            zh = P.zh_of(P.vec_to_atoms(P.parse_formula(f), P.ORDER))
            A(f"| {j} | {f} | {zh} | {natoms} | {list(vec)} |")
        A("")
    open(BASE + r"\CATALOG_FINITE_LISTS.md", "w", encoding="utf-8").write("\n".join(L))
    print("saved CATALOG_FINITE_LISTS.md, lines:", len(L))


if __name__ == "__main__":
    main()
