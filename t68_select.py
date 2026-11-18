# -*- coding: utf-8 -*-
"""t68_select.py — 从 t68_pool.json 里选定 36 个大分子/特大分子稳定物质，
pot_v4 复核稳定性，整理卡片渲染所需的全部字段，输出 t68_data.json。

选择原则（写入 docs/T68_GIANT_ATLAS.md）：
  * 全部为完全反应不动点 F(v_M)={M}（fast_pot 验证 + pot_v4 复核）；
  * 覆盖 T61/T62/T63/T64 四个实验来源，覆盖 7 个骨架家族；
  * 覆盖 38 库里的 20+ 种 6 级骨架形态、2~5 骨架、0~7 座二价桥、
    S/C/L/混合四种桥与唯一一个骨架融合实例（T61-004）；
  * 兼顾 14~22 原子的中型与 39~40 原子的特大分子。
"""
import json
import os
import sys
import time
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
import pot_v4
import t39_library_verify as V

FAMILY_ZH = {"O": "纯秩", "P": "纯势", "K": "纯散", "OP": "秩势",
             "OK": "秩散", "PK": "势散", "OPK": "秩势散"}

# (exp, formula) 选择表：36 个
SELECT = [
    # ---- 14~22 原子：中型（12）------------------------------------------------
    ("T63", "O2X3C3K3A3"),      # 单骨架 O2K3，纯散家族
    ("T64", "O3X3K2A3F3"),      # 单骨架 O3K2
    ("T64", "O2X3C3P3W3"),      # 单骨架 O2P3，纯秩势
    ("T64", "O3X3P2W3L3"),      # 单骨架 O3P2
    ("T62", "O3X2P4WK3A"),      # 2 骨架 S 桥
    ("T64", "O4X6P6"),          # 2×O2P3 + C 铰接桥
    ("T64", "O6X6P4"),          # 2×O3P2 + S 刚性桥
    ("T64", "O4X6K6A3"),        # 2×O2K3 + 3 混合桥
    ("T64", "O6X3K4A6"),        # 2×O3K2 + 3 混合桥
    ("T64", "O4X4P5W3K3"),      # 3 骨架（O2P3K+OPK+OPK）+ S 桥
    ("T64", "O4X6C2K6A4"),      # 2×O2K3 + 混合桥
    ("T62", "O3X3CP4W2K2A"),    # 2 骨架 混合桥
    # ---- 39~40 原子：特大分子（24）--------------------------------------------
    ("T61", "O3X4CP16W5LK5A3F2"),   # 唯一骨架融合实例（5 块→4 骨架）
    ("T61", "O3X4C5P14W3LK5A3F2"),  # 5 骨架 OP4K/OP3K/P2K
    ("T61", "O7X7P12W2LK4A7"),      # 2 骨架 + 4 桥
    ("T61", "O11X2CP13W3K5A5"),     # 5 骨架 + L 软桥
    ("T61", "O6X6C3P10W4LK4A6"),    # 2 骨架 + 1 桥（极简特大）
    ("T61", "O9X5P13WK6A6"),        # 5 骨架
    ("T61", "O4X2C2P14W3K3A6F5"),   # 4 骨架 + L 桥
    ("T61", "O4X10CP11W4K4A3F2"),   # 4 骨架 + S 桥
    ("T61", "O11X6P12W2K5A3"),      # 5 骨架 O3P4K + 4×O2P2K
    ("T61", "O7X6P13WK6A6"),        # 5 骨架 + 6 桥
    ("T62", "O2X5CP10W7LK2A12"),    # OP4K×2 + 两个孤立 P 单原子骨架
    ("T62", "O4X7C4P7W7L2K2A6F"),   # 单骨架 O4P7K2、0 桥（纯特大）
    ("T62", "O8X5P13W5K3A6"),       # 3 骨架 + 6 桥
    ("T62", "O4X10P13W3K5A4"),      # 5 骨架 + 7 桥
    ("T62", "O6X7CP11W5K4A6"),      # O4P7K2 + 2×OP2K
    ("T63", "O8X11C2K12A6"),        # 4×O2K3，纯散家族特大
    ("T63", "O5X16CK12A6"),         # OK3/OK2 纯散家族
    ("T64", "O8X11C2P12W6"),        # 4×O2P3 纯秩势特大
    ("T64", "O12X6K8A11F2"),        # 4×O3K2 纯散特大
    ("T64", "O9X11CP14W4"),         # 4×O2P3 + OP2
    ("T61", "O7X5CP11W4LK5A5F"),    # O3P5K2+O2P3K2+O2P3K
    ("T61", "O9X5C2P11W3K4A6"),     # 3×O2P2K + O3P5K
    ("T61", "O8X5P13W3K7A3"),       # O3P5K2+2×O2P3K2+OP2K
    ("T62", "O8X5P11W5K3A8"),       # O3P4K+O2P2K+O3P5K
]


def family_zh(fam):
    return FAMILY_ZH.get(fam, fam)


def bridge_desc(b):
    comps = "·".join("①②③④⑤⑥"[c] if c < 6 else str(c + 1) for c in b["comps"])
    kinds = Counter(b["types"])
    t = "".join("%s×%d" % (k, v) for k, v in sorted(kinds.items()))
    return "%s→%s %s（%s 键 ×%d）" % (comps, "", b["kind"], t, len(b["idx"]))


def main():
    pool = json.load(open(os.path.join(BASE, "t68_pool.json"),
                          encoding="utf-8"))["pool"]
    by_key = {(r["exp"], r["formula"]): r for r in pool}
    lib = V.load_library()
    libmulti = lib["multi"]
    lib_formulas = set(f["formula"] for f in lib["t8"])
    # 单元素 7 模块也算库内
    module_formulas = {"O", "P", "K"}
    print("lib forms:", len(lib_formulas), "libmulti:", len(libmulti))

    mols = []
    t0 = time.time()
    for i, (exp, formula) in enumerate(SELECT):
        key = (exp, formula)
        if key not in by_key:
            raise SystemExit("NOT IN POOL: %s" % (key,))
        r = json.loads(json.dumps(by_key[key]))  # deep copy
        # ---- pot_v4 复核：F(v_M) = {M}
        atoms = r["atoms"]
        edges = [tuple(e) for e in r["edges"]]
        lab = r["mol_label"]
        out = pot_v4.simulate(atoms)
        stable4 = (out is not None and len(out) == 1 and
                   len(out[0]["atoms"]) == len(atoms) and
                   P.mol_label(out[0]["atoms"], out[0]["edges"]) == lab)
        r["stable_pot_v4"] = bool(stable4)
        # ---- 展示字段
        r["mid"] = "G%02d" % (i + 1)
        r["family_zh"] = family_zh("".join(sorted(set(
            e for s in r["skeletons"] for e in s["family"]),
            key=lambda e: "OPK".index(e))))
        for k, s in enumerate(r["skeletons"]):
            s["num"] = k + 1
            s["family_zh"] = family_zh(s["family"])
            # 6 级块公式列表（融合时 >1）
            s["block_forms"] = [b["lib_formula"] or b["formula"] for b in s["blocks"]]
            s["block_size"] = len(s["blocks"])
            s["all_blocks_in_lib"] = all(b["in_lib"] for b in s["blocks"])
            # 融合元素（0 级同类键的两种元素）
            s["fusion_elems"] = {}
            for fb in s["fusion"]:
                s["fusion_elems"][fb["elements"]] = \
                    s["fusion_elems"].get(fb["elements"], 0) + 1
        for b in r["bridges"]:
            b["desc"] = bridge_desc(b)
        # 装饰统计
        dec = r["decoration"]
        role = r["role"]
        r["deco_stats"] = {
            "intra": sum(1 for v in dec["intra"] if role.get(str(v)) == "intra"),
            "arms": sum(1 for v in dec["arms"] if role.get(str(v)) == "arm"),
            "mono": len(dec["mono"]),
            "free": len(dec["free"]),
        }
        r["n_intra_bridge"] = sum(1 for v, k in role.items() if k == "intra")
        r["n_arm"] = sum(1 for v, k in role.items() if k == "arm")
        r["n_mono"] = sum(1 for v, k in role.items() if k == "mono")
        r["n_bridge_atoms"] = sum(1 for v, k in role.items() if k == "bridge")
        # 单原子骨架数
        r["n_single_atom_skel"] = sum(1 for s in r["skeletons"] if s["n"] == 1)
        mols.append(r)
        print(r["mid"], exp, formula, r["n_atoms"], "skel", len(r["skeletons"]),
              "bridge", len(r["bridges"]), "v4_stable", stable4,
              "%.1fs" % (time.time() - t0), flush=True)

    # ---- 校验
    bad_stable = [m["mid"] for m in mols if not m["stable_pot_v4"]]
    print("pot_v4 unstable:", bad_stable)
    skel_forms = Counter()
    not_in_lib = []
    for m in mols:
        for s in m["skeletons"]:
            if s["n"] == 1:
                skel_forms["%s(单原子)" % s["formula"]] += 1
            else:
                for bf in s["block_forms"]:
                    skel_forms[bf] += 1
                if not all(s["block_forms"]):
                    not_in_lib.append((m["mid"], s["formula"]))
    print("骨架块形态使用次数:")
    for f, c in skel_forms.most_common():
        print("  ", f, c)
    print("不在库内:", not_in_lib)
    print("融合骨架:", [(m["mid"], s["formula"], s["block_forms"])
                        for m in mols for s in m["skeletons"] if s["block_size"] > 1])
    print("桥类型分布:", Counter(b["kind"] for m in mols for b in m["bridges"]))
    print("家族分布:", Counter(m["family_zh"] for m in mols))
    print("来源分布:", Counter(m["exp"] for m in mols))
    print("原子数分布:", Counter(m["n_atoms"] for m in mols))
    print("骨架数分布:", Counter(len(m["skeletons"]) for m in mols))

    meta = {
        "n_mols": len(mols),
        "n_atoms_total": sum(m["n_atoms"] for m in mols),
        "n_skeletons_total": sum(len(m["skeletons"]) for m in mols),
        "n_bridges_total": sum(len(m["bridges"]) for m in mols),
        "n_fusion_mols": sum(1 for m in mols
                             if any(s["block_size"] > 1 for s in m["skeletons"])),
        "skel_block_usage": dict(skel_forms),
        "all_v4_stable": not bad_stable,
        "sources": sorted(set(m["exp"] for m in mols)),
        "lib_forms": sorted(lib_formulas),
    }
    json.dump({"meta": meta, "molecules": mols},
              open(os.path.join(BASE, "t68_data.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print("saved t68_data.json;", meta["n_mols"], "molecules,",
          meta["n_atoms_total"], "atoms,", meta["n_skeletons_total"],
          "skeletons,", meta["n_bridges_total"], "bridges")


if __name__ == "__main__":
    main()
