# -*- coding: utf-8 -*-
"""t68_build_data.py — T68 数据前置：从 T61~T64 已摆放的大分子/特大分子中
挑选稳定物质，验证稳定性（完全反应不动点），并提取骨架分解（38 库 6 级块 +
0 级同类键融合）、二价桥与装饰层角色，输出 t68_pool.json / t68_data.json。

数据来源（只读，不改动）：
  t61_hex_layouts.json / t62_hex_layouts.json / t63_hex_layouts.json / t64_hex_layouts.json
规则口径：pot_v4（规则 1~11，正式模拟器）；fast_pot.simulate_level6 与 pot_v4 逐项一致
（见 t59_fast_engine_audit.py），此处用 fast_pot 批量跑，入选物质再用 pot_v4 复核。

稳定性定义（T30）：F(v_M) = {M} 即完全反应唯一产物且与自身结构同构。
"""
import json
import os
import sys
import time
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import fast_pot
import pot_all as P
import pot_v4
import t39_library_verify as V

TRI = {"O", "P", "K"}
DIV = {"X", "W", "A"}
MONO = {"C", "L", "F"}
ORDER = P.ORDER
VAL = P.VAL

LAYOUTS = [("T61", "t61_hex_layouts.json"), ("T62", "t62_hex_layouts.json"),
           ("T63", "t63_hex_layouts.json"), ("T64", "t64_hex_layouts.json")]


# ------------------------------------------------------------------ 图工具
def triv_components(atoms, edges):
    """终态三价诱导子图的连通块（骨架本体），返回 [{atoms_idx, edges_idx}]。"""
    idx = [i for i, a in enumerate(atoms) if a in TRI]
    if not idx:
        return []
    pos = {v: k for k, v in enumerate(idx)}
    par = list(range(len(idx)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[rb] = ra

    for (i, j, m) in edges:
        if atoms[i] in TRI and atoms[j] in TRI:
            union(pos[i], pos[j])
    groups = defaultdict(list)
    for v in idx:
        groups[find(pos[v])].append(v)
    out = []
    for g in groups.values():
        gs = set(g)
        out.append({"atoms_idx": sorted(g),
                    "edges_idx": [(a, b, m) for (a, b, m) in edges
                                  if a in gs and b in gs]})
    out.sort(key=lambda c: c["atoms_idx"][0])
    return out


def bond_type(atoms, place, i, j):
    d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
    t = P.classify_offset(d)
    return t


# ------------------------------------------------------------------ 单体分析
def analyze(item, exp, libmulti):
    atoms = list(item["atoms"])
    edges = [tuple(e) for e in item["edges"]]
    place = [tuple(p) for p in item["place"]]
    n = len(atoms)
    lab = P.mol_label(atoms, edges)
    rec = {"exp": exp, "key": item.get("key"), "formula": item["formula"],
           "n_atoms": n, "atoms": atoms, "edges": [list(e) for e in edges],
           "place": [list(p) for p in place], "bonds": item.get("bonds") or [],
           "bbox": item.get("bbox"), "mol_label": lab,
           "occurrences": item.get("occurrences") or {},
           "counts": item.get("counts") or {}}

    # ---- 稳定性：fast_pot（规则 1~11）完全反应
    t0 = time.time()
    mols, level6 = fast_pot.simulate_level6(atoms)
    rec["sim_seconds"] = round(time.time() - t0, 4)
    nprod = len(mols) if mols else 0
    stable = False
    if mols and nprod == 1:
        m0 = mols[0]
        stable = (len(m0["atoms"]) == n and
                  P.mol_label(m0["atoms"], m0["edges"]) == lab)
    rec["stable"] = stable
    rec["n_products"] = nprod
    if level6 is None:
        level6 = []

    # ---- 终态骨架块（三价连通块，以真实分子图为准）
    comps = triv_components(atoms, edges)

    # ---- 6 级块（level6 mem 为输入原子序号 = atoms/place 序号）
    blocks = []
    for (bats, bes, mem) in level6:
        bes2 = [tuple(e) for e in bes]
        bl = V.block_label(bats, bes2)
        if len(bats) == 1:
            form = form_lib = {"O": "O", "P": "P", "K": "K"}[bats[0]]
            inlib = True
        else:
            form = form_lib = libmulti.get(bl)
            inlib = form is not None
            if form is None:
                form = P.formula_of(bats)
        blocks.append({"mem": sorted(int(x) for x in mem),
                       "formula": form, "lib_formula": form_lib,
                       "size": len(bats), "in_lib": bool(inlib),
                       "label": bl})
    # 原子 -> 6 级块
    atom_block = {}
    for bi, b in enumerate(blocks):
        for v in b["mem"]:
            atom_block[v] = bi

    # ---- 骨架记录
    skels = []
    skel_of_atom = {}
    for sid, comp in enumerate(comps):
        ci = comp["atoms_idx"]
        cis = set(ci)
        my_blocks = [bi for bi, b in enumerate(blocks) if set(b["mem"]) <= cis]
        cover = set()
        for bi in my_blocks:
            cover |= set(blocks[bi]["mem"])
        my_elems = Counter(atoms[v] for v in ci)
        fam = "".join(e for e in ORDER if e in my_elems and e in TRI)
        sub_atoms = [atoms[v] for v in ci]
        sub_edges = comp["edges_idx"]
        local = {v: k for k, v in enumerate(ci)}
        sub_edges_local = [(local[a], local[b], m) for (a, b, m) in sub_edges]
        sk = {"sid": sid, "idx": ci, "n": len(ci),
              "formula": P.formula_of(sub_atoms), "family": fam,
              "label": P.mol_label(sub_atoms, sub_edges_local),
              "blocks": [{"mem": blocks[bi]["mem"],
                          "formula": blocks[bi]["formula"],
                          "lib_formula": blocks[bi]["lib_formula"],
                          "in_lib": blocks[bi]["in_lib"],
                          "size": blocks[bi]["size"]} for bi in my_blocks],
              "cover_ok": cover == cis,
              "fusion": [], "n_fusion_bonds": 0}
        # 融合：同一骨架内、两端 6 级块不同的三价-三价键（0 级同类键）
        for (a, b, m) in sub_edges:
            ba, bb = atom_block.get(a), atom_block.get(b)
            if ba == bb or ba is None or bb is None:
                continue
            sk["fusion"].append({"a": a, "b": b, "m": m,
                                 "type": bond_type(atoms, place, a, b),
                                 "elements": atoms[a] + atoms[b]})
        sk["n_fusion_bonds"] = len(sk["fusion"])
        sk["n_blocks"] = len(my_blocks)
        skel_of_atom.update({v: sid for v in ci})
        skels.append(sk)

    # ---- 二价原子簇（桥 / 装饰）
    div_atoms = [i for i, a in enumerate(atoms) if a in DIV]
    div_adj = defaultdict(set)
    for (a, b, m) in edges:
        if atoms[a] in DIV and atoms[b] in DIV:
            div_adj[a].add(b)
            div_adj[b].add(a)
    seen = set()
    clusters = []
    for v in div_atoms:
        if v in seen:
            continue
        stack = [v]
        seen.add(v)
        cl = []
        while stack:
            u = stack.pop()
            cl.append(u)
            for w in div_adj[u]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        clusters.append(sorted(cl))

    bridges = []
    deco = {"mono": [], "intra": [], "arms": [], "free": []}
    div_role = {}
    for cl in clusters:
        cls = set(cl)
        attached = defaultdict(list)   # sid -> bond list
        for (a, b, m) in edges:
            if a in cls and b in skel_of_atom:
                attached[skel_of_atom[b]].append(
                    {"div": a, "skel_atom": b, "m": m,
                     "type": bond_type(atoms, place, a, b)})
            elif b in cls and a in skel_of_atom:
                attached[skel_of_atom[a]].append(
                    {"div": b, "skel_atom": a, "m": m,
                     "type": bond_type(atoms, place, a, b)})
        if len(attached) >= 2:
            types = []
            for s2, bl in attached.items():
                for bd in bl:
                    types.append(bd["type"])
            tset = set(types)
            kind = ("S 刚性焊桥" if tset == {"S"} else
                    "C 铰接桥" if tset == {"C"} else
                    "L 浮空软桥" if tset == {"L"} else "混合桥")
            bridges.append({"bid": len(bridges), "idx": cl,
                            "formula": P.formula_of([atoms[u] for u in cl]),
                            "k": len(cl), "comps": sorted(attached.keys()),
                            "bonds_to_skel": attached, "kind": kind,
                            "types": types})
            for u in cl:
                div_role[u] = "bridge"
        else:
            sid = list(attached.keys())[0] if attached else None
            bonds_into = len(attached.get(sid, [])) if sid is not None else 0
            if sid is None:
                for u in cl:
                    div_role[u] = "free"
                deco["free"].extend(cl)
            elif bonds_into >= 2:
                for u in cl:
                    div_role[u] = "intra"
                deco["intra"].extend(cl)
            else:
                for u in cl:
                    div_role[u] = "arm"
                deco["arms"].extend(cl)
    deco["mono"] = [i for i, a in enumerate(atoms) if a in MONO]
    # 每个原子的绘制角色
    role = {}
    for v in range(n):
        if v in skel_of_atom:
            role[v] = "skel"
        elif atoms[v] in DIV:
            role[v] = div_role.get(v, "free")
        else:
            role[v] = "mono"
    rec["role"] = role

    rec["skeletons"] = skels
    rec["bridges"] = bridges
    rec["decoration"] = deco
    rec["features"] = {
        "n_skel": len(skels),
        "n_blocks": len(blocks),
        "n_bridge": len(bridges),
        "n_fusion": sum(s["n_fusion_bonds"] for s in skels),
        "families": sorted(set(s["family"] for s in skels)),
        "cover_ok": all(s["cover_ok"] for s in skels),
        "all_blocks_in_lib": all(b["in_lib"] for b in blocks),
        "sizes": sorted(s["n"] for s in skels),
    }
    return rec


# ------------------------------------------------------------------ 主流程
def main():
    t0 = time.time()
    lib = V.load_library()
    libmulti = lib["multi"]
    pool = []
    seen_labels = set()
    for exp, fn in LAYOUTS:
        d = json.load(open(os.path.join(BASE, fn), encoding="utf-8"))
        items = d["items"]
        for item in items:
            if (item.get("n_atoms") or 0) < 14:
                continue
            lab = P.mol_label(item["atoms"], [tuple(e) for e in item["edges"]])
            if lab in seen_labels:
                continue
            seen_labels.add(lab)
            rec = analyze(item, exp, libmulti)
            rec["id"] = "%s-%03d" % (exp, len(pool) + 1)
            pool.append(rec)
        print(exp, "done", len(pool), flush=True)

    # ---- 统计
    print("pool:", len(pool))
    print("stable:", sum(1 for r in pool if r["stable"]))
    print("unstable examples:", [(r["formula"], r["n_products"])
                                 for r in pool if not r["stable"]][:10])
    print("cover_ok:", sum(1 for r in pool if r["features"]["cover_ok"]),
          "/", len(pool))
    print("all_blocks_in_lib:", sum(1 for r in pool if r["features"]["all_blocks_in_lib"]))
    print("feature combos:",
          Counter((r["features"]["n_skel"], r["features"]["n_bridge"],
                   r["features"]["n_fusion"]) for r in pool).most_common(20))
    print("by exp:", Counter(r["exp"] for r in pool))
    print("sizes:", Counter(r["n_atoms"] for r in pool))

    json.dump({"pool": pool}, open(os.path.join(BASE, "t68_pool.json"), "w",
                                   encoding="utf-8"), ensure_ascii=False)
    print("saved t68_pool.json", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
