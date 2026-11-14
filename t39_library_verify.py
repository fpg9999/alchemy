# -*- coding: utf-8 -*-
"""t39_library_verify.py：复核「骨架库」与「库外骨架」结论（T39 验证轮）

背景：T38 曾报告「并列歧义会让 6 级中间态骨架块出 38 库」（200 物质抽样中 14 个）。
本脚本发现该结论的实例是**假阳性**：
  t15_forms_examples.wl_key 的 WL 颜色细化在同色类（对称等价原子）内按输入下标
  稳定排序，没有做规范破缺，因此同一张带标签多重图在不同输入顺序下会得到不同
  wl_key —— 它不是同构不变量（38 库中有 8 个形态会受影响）。
用 pot_all.mol_label（回溯规范形，已验证对随机置换不变）复核后，T38 的库外
块 0 个；但**真正**的库外 6 级块仍然存在，只是出现得更晚：穷举三价计数
≤10 时，唯一一族反例在 counts=(O3,P5,K2)，可复现到目录物质 O3P5K2。

本脚本输出：
  1) 38 库 / 7×3 库组成与唯一性
  2) wl_key 非同构不变（8/38 形态）
  3) 6 级并列全分支枚举（≤10 三价原子）：真·库外块 = 1 族
  4) T38 原始 100 物质检查 + T38b 200 物质策略检查的 wl_key vs mol_label 复核
  5) T15 695 个「45 库外终态形态」复核（真/假）
  6) T37 并列多解数复核（wl_key 会虚增）
  7) 真·库外实例：O3P5K2 的另一并列分支（6 级块出库、产物可摆放、同分子式）
运行：python t39_library_verify.py
输出：t39_library_verify.json
"""
import json
import random
import sys
import time
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2
import pot_v3
import t37_tie_analysis as T
from pot_v3 import rule9_extra
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = P.VAL
ORDER = P.ORDER

SINGLE_TEMPLATES = [
    (1, []),
    (2, [(0, 1, 1)]),
    (2, [(0, 1, 2)]),
    (2, [(0, 1, 3)]),
    (3, [(0, 1, 1), (1, 2, 1)]),
    (3, [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    (3, [(0, 1, 2), (1, 2, 1), (0, 2, 1)]),
]

# 注：真·库外块的分支由 find_bad_l6_branch() 在物质实际原子顺序下 DFS 搜索得到


# ---------------------------------------------------------------- 规范形工具
def block_label(atoms, edges):
    """带元素标签多重图的正确规范形；单元素类型块统一记为 O（与 wl_key 口径一致）。"""
    if len(set(atoms)) == 1:
        atoms = ["O"] * len(atoms)
    return P.mol_label(atoms, [tuple(e) for e in edges])


def load_library():
    t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
    multi_forms = [f for f in t8 if len(f["atoms"]) > 1]
    single_forms = [f for f in t8 if len(f["atoms"]) == 1]
    multi = {}
    for f in multi_forms:
        multi[block_label(f["atoms"], [tuple(e) for e in f["edges"]])] = f["formula"]
    single = {}
    for n, es in SINGLE_TEMPLATES:
        single[block_label(["O"] * n, es)] = n
    wl_multi = {wl_key(f["atoms"], [tuple(e) for e in f["edges"]]): f["formula"]
                for f in t8 if len(set(f["atoms"]) & TRI) >= 2}
    wl_single = {wl_key(["A"] * n, [tuple(e) for e in es]) for n, es in SINGLE_TEMPLATES}
    return {"t8": t8, "multi": multi, "single": single,
            "multi_forms": multi_forms, "wl_multi": wl_multi, "wl_single": wl_single,
            "n_single_atoms": len(single_forms)}


def classify_block(lib, atoms, edges, use_wl=False):
    types = set(atoms) & TRI
    if use_wl:
        k = wl_key(atoms, [tuple(e) for e in edges])
        if len(types) >= 2:
            return "multi" if k in lib["wl_multi"] else "BAD"
        return "single" if k in lib["wl_single"] else "BAD"
    if len(types) >= 2:
        return "multi" if block_label(atoms, edges) in lib["multi"] else "BAD"
    if len(types) == 1:
        return "single" if block_label(atoms, edges) in lib["single"] else "BAD"
    return "BAD"


# ---------------------------------------------------------------- 1) 库组成
def verify_library(lib):
    by_types = Counter()
    for f in lib["multi_forms"]:
        by_types["".join(sorted(set(f["atoms"])))] += 1
    sizes = Counter(len(f["atoms"]) for f in lib["multi_forms"])
    active = Counter(sum(1 for r in f["rems"] if r > 0) for f in lib["multi_forms"])
    return {
        "t8_total": len(lib["t8"]),
        "n_single_atoms": lib["n_single_atoms"],
        "n_multi": len(lib["multi_forms"]),
        "multi_by_typesets": dict(by_types),
        "multi_sizes": dict(sorted(sizes.items())),
        "multi_active_dist": dict(sorted(active.items())),
        "multi_unique_under_mol_label": len(lib["multi"]) == len(lib["multi_forms"]),
        "n_single_templates": len(lib["single"]),
        "max_multi_size": max(sizes),
    }


# ---------------------------------------------------------------- 2) wl_key 不变性
def verify_wl_key(lib, seed=1):
    rng = random.Random(seed)
    bad = []
    for f in lib["t8"]:
        atoms = list(f["atoms"])
        edges = [tuple(e) for e in f["edges"]]
        base = wl_key(atoms, edges)
        for _ in range(30):
            perm = list(range(len(atoms)))
            rng.shuffle(perm)
            inv = {o: k for k, o in enumerate(perm)}
            a2 = [atoms[o] for o in perm]
            e2 = sorted((min(inv[a], inv[b]), max(inv[a], inv[b]), m) for (a, b, m) in edges)
            if wl_key(a2, e2) != base:
                bad.append(f["formula"])
                break
    # 具体演示：库内 O2P3 与另一个原子顺序的同一形态
    lib_o2p3 = next(f for f in lib["t8"] if f["formula"] == "O2P3")
    alt_atoms = ["O", "O", "P", "P", "P"]
    alt_edges = [(0, 2, 1), (0, 4, 2), (1, 2, 1), (1, 3, 2)]
    return {
        "wl_key_non_invariant_forms": bad,
        "n_bad": len(bad), "of_total": len(lib["t8"]),
        "demo": {
            "formula": "O2P3",
            "wl_key_library_form": str(wl_key(lib_o2p3["atoms"], [tuple(e) for e in lib_o2p3["edges"]])),
            "wl_key_alt_order": str(wl_key(alt_atoms, alt_edges)),
            "mol_label_library_form": block_label(lib_o2p3["atoms"], [tuple(e) for e in lib_o2p3["edges"]]),
            "mol_label_alt_order": block_label(alt_atoms, alt_edges),
            "same_under_mol_label": block_label(lib_o2p3["atoms"], [tuple(e) for e in lib_o2p3["edges"]])
                                    == block_label(alt_atoms, alt_edges),
        },
    }


# ---------------------------------------------------------------- 3) 6 级全分支枚举
def enum_level6(counts, lib):
    """枚举三价计数 counts 的 6 级并列全部可达结果（状态去重），返回库外块 dict。"""
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return {}
    rem0 = [VAL[e] for e in atoms]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]

    def comps(bond):
        comp = [-1] * n
        groups = []
        for s in range(n):
            if comp[s] != -1:
                continue
            cid = len(groups)
            comp[s] = cid
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v in range(n):
                    if comp[v] == -1 and bond[u][v] > 0:
                        comp[v] = cid
                        st.append(v)
                        mem.append(v)
            groups.append(mem)
        dists = []
        for mem in groups:
            d = {}
            for s in mem:
                dd = {s: 0}
                dq = deque([s])
                while dq:
                    u = dq.popleft()
                    for v in range(n):
                        if bond[u][v] > 0 and v not in dd:
                            dd[v] = dd[u] + 1
                            dq.append(v)
                d[s] = dd
            dists.append(d)
        return comp, groups, dists

    def cands_of(bond, rem):
        comp, groups, dists = comps(bond)
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
        out = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3 or dt[i][j] != 6:
                    continue
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                out.append((key, i, j))
        return out, groups

    def state(bond, rem):
        rows = [(i, j, bond[i][j]) for i in range(n) for j in range(i + 1, n) if bond[i][j]]
        return (tuple(rows), tuple(rem))

    found = {}
    seen = set()

    def dfs(bond, rem):
        st = state(bond, rem)
        if st in seen:
            return
        seen.add(st)
        cands, groups = cands_of(bond, rem)
        if not cands:
            for mem in groups:
                if not any(atoms[v] in TRI for v in mem):
                    continue
                mem = sorted(mem)
                ats = [atoms[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                if classify_block(lib, ats, es) == "BAD":
                    k = block_label(ats, es)
                    found.setdefault(k, {"atoms": ats, "edges": es,
                                         "formula": "".join(sorted(ats)),
                                         "counts": counts})
            return
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        for (i, j) in tied:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            dfs(bond, rem)
            bond[i][j] -= 1
            bond[j][i] -= 1
            rem[i] += 1
            rem[j] += 1

    dfs([[0] * n for _ in range(n)], list(rem0))
    return found


def verify_level6_closure(lib, max_total=10):
    t0 = time.time()
    bad = {}
    per_total = {}
    for total in range(2, max_total + 1):
        n_bad = 0
        for nO in range(0, total + 1):
            for nP in range(0, total - nO + 1):
                nK = total - nO - nP
                if nO == nP == nK == 0:
                    continue
                for k, v in enum_level6((nO, nP, nK), lib).items():
                    n_bad += 1
                    bad.setdefault(k, v)
        per_total[total] = n_bad
        print(f"  level6 三价总数={total}: 库外块={n_bad}", flush=True)
    return {"max_trivalent_total": max_total,
            "bad_per_total": per_total,
            "bad_blocks": list(bad.values()),
            "seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------- 4) T38 复核
def block_kind_counts(lib, atoms, edges):
    return classify_block(lib, atoms, edges), classify_block(lib, atoms, edges, use_wl=True)


def verify_t38_original(lib):
    """复刻 t38_library_check.py：100 物质 × 20 次随机并列。"""
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    rng = random.Random(777)
    pool = [r for r in cat if 2 <= len(r["atoms"]) <= 10]
    sample = rng.sample(pool, 100)
    kinds_mol = Counter()
    kinds_wl = Counter()
    for rec in sample:
        atoms = list(rec["atoms"])
        for i in range(20):
            r = T.run(atoms, policy="random", rng=random.Random(i * 13 + 5))
            if not r or not r.get("block_structs"):
                continue
            for b in r["block_structs"]:
                ats, es = b["atoms"], [tuple(e) for e in b["edges"]]
                km, kw = block_kind_counts(lib, ats, es)
                kinds_mol[km] += 1
                kinds_wl[kw] += 1
    return {"substances": 100, "runs_each": 20,
            "blocks_by_mol_label": dict(kinds_mol),
            "blocks_by_wl_key": dict(kinds_wl),
            "mol_bad_total": kinds_mol.get("BAD", 0),
            "wl_bad_total": kinds_wl.get("BAD", 0)}


def verify_t38b(lib):
    """复刻 t38b_policies.py：200 物质 × (默认 + 15 随机 + 10 块内随机)。"""
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    rng = random.Random(2024)
    pool = [r for r in cat if 2 <= len(r["atoms"]) <= 10]
    sample = rng.sample(pool, 200)
    stats = Counter()
    wl_bad_substances = []
    mol_bad_substances = []
    ten = {}
    for rec in sample:
        atoms = list(rec["atoms"])
        wl_bad = mol_bad = False
        runs = [("first", None)] + [("random", i) for i in range(15)] + \
               [("intra_random", i) for i in range(10)]
        for policy, seed in runs:
            r = T.run(atoms, policy=policy, rng=random.Random(seed) if seed is not None else None)
            if not r or not r.get("block_structs"):
                continue
            for b in r["block_structs"]:
                km, kw = block_kind_counts(lib, b["atoms"], [tuple(e) for e in b["edges"]])
                if km == "BAD":
                    mol_bad = True
                if kw == "BAD":
                    wl_bad = True
        stats["n_substances"] += 1
        if wl_bad:
            stats["wl_bad_substances"] += 1
            wl_bad_substances.append(rec["formula"])
        if mol_bad:
            stats["mol_bad_substances"] += 1
            mol_bad_substances.append(rec["formula"])
    for f in ["O5X3KA", "O5X3PA", "OCP7W2KA2"]:
        atoms = P.vec_to_atoms(P.parse_formula(f), ORDER)
        nb = wl_bad = mol_bad = 0
        for policy, seed in [("first", None)] + [("random", i) for i in range(15)] + \
                            [("intra_random", i) for i in range(10)]:
            r = T.run(atoms, policy=policy, rng=random.Random(seed) if seed is not None else None)
            for b in (r or {}).get("block_structs") or []:
                nb += 1
                km, kw = block_kind_counts(lib, b["atoms"], [tuple(e) for e in b["edges"]])
                wl_bad += kw == "BAD"
                mol_bad += km == "BAD"
        ten[f] = {"blocks": nb, "wl_bad": wl_bad, "mol_bad": mol_bad}
    return {"stats": dict(stats), "wl_bad_substances": wl_bad_substances,
            "mol_bad_substances": mol_bad_substances, "ten_atom_examples": ten}


# ---------------------------------------------------------------- 5) T15 复核
def verify_t15(lib):
    forms = json.load(open(BASE + r"\t15_forms.json", encoding="utf-8"))
    lib_keys = set(lib["multi"]) | set(lib["single"])
    genuine, fake = [], []
    for x in forms:
        if block_label(x["atoms"], [tuple(e) for e in x["edges"]]) in lib_keys:
            fake.append(x)
        else:
            genuine.append(x)
    return {"t15_total": len(forms), "genuine_new": len(genuine),
            "false_positive": len(fake),
            "genuine_sizes": dict(sorted(Counter(x["n"] for x in genuine).items())),
            "smallest_examples": [{"n": x["n"], "tset": x["tset"], "example": x["example"],
                                   "atoms": x["atoms"], "edges": x["edges"]}
                                  for x in sorted(genuine, key=lambda y: (y["n"], y["example"]))[:8]]}


# ---------------------------------------------------------------- 5b) T15 全目录重扫
def verify_t15_full_rescan(lib):
    """用 mol_label 直接重扫 84,225 目录的终态三价组件，得到权威的「45 库外」形态数。"""
    from t15_forms_examples import triv_components
    t0 = time.time()
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    libkeys = set(lib["multi"]) | set(lib["single"])
    new = {}
    n_comp = 0
    for rec in cat:
        atoms, mult, comps = triv_components(rec)
        for mem in comps:
            n_comp += 1
            ats = [atoms[a] for a in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    m = mult[mem[a]][mem[b]]
                    if m:
                        es.append((a, b, m))
            k = block_label(ats, es)
            if k not in libkeys and k not in new:
                new[k] = {"atoms": ats, "edges": [list(e) for e in es],
                          "n": len(ats), "example": rec["formula"]}
    forms = json.load(open(BASE + r"\t15_forms.json", encoding="utf-8"))
    labels = [block_label(x["atoms"], [tuple(e) for e in x["edges"]]) for x in forms]
    labels_genuine = [k for k in labels if k not in libkeys]
    out = {"catalog_records": len(cat), "terminal_components": n_comp,
           "distinct_genuine_new_forms": len(new),
           "size_dist": dict(sorted(Counter(v["n"] for v in new.values()).items())),
           "t15_entries": len(forms),
           "t15_entries_distinct_mol_label": len(set(labels)),
           "t15_entries_genuine_distinct": len(set(labels_genuine)),
           "t15_entries_duplicate_isomorphic": len(labels_genuine) - len(set(labels_genuine)),
           "smallest_examples": sorted(new.values(), key=lambda x: (x["n"], x["example"]))[:10],
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open(BASE + r"\t39_t15_rescan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return out


# ---------------------------------------------------------------- 6) T37 多解复核
def verify_t37(lib):
    out = {}
    for f in ["O5X3KA", "O5X3PA", "OP5W3A", "OWK5A3", "OCP7W2KA2"]:
        atoms = P.vec_to_atoms(P.parse_formula(f), ORDER)
        wl_out, mol_out = set(), set()
        for i in range(300):
            r = T.run(atoms, policy="random", rng=random.Random(i * 7 + 3))
            if not r:
                continue
            wl_out.add(tuple(sorted(wl_key(m["atoms"], [tuple(e) for e in m["edges"]])
                                    for m in r["molecules"])))
            mol_out.add(tuple(sorted(P.mol_label(m["atoms"], [tuple(e) for e in m["edges"]])
                                     for m in r["molecules"])))
        out[f] = {"outcomes_wl_key": len(wl_out), "outcomes_mol_label": len(mol_out)}
    return out


# ---------------------------------------------------------------- 7) 真·库外实例
def find_bad_l6_branch(atom_list, lib):
    """在给定原子顺序下，DFS 搜 6 级并列分支，返回第一个产生库外 6 级块的选择路径
    （路径元素 = (该步并列数, 选中下标)），以及该块的 (atoms, edges)。"""
    n = len(atom_list)
    rem0 = [VAL[e] for e in atom_list]
    dt = [[P.ptable_dist(atom_list[i], atom_list[j]) if i != j else 0 for j in range(n)]
          for i in range(n)]
    fam = [[P.family_rank(atom_list[i], atom_list[j]) if i != j else 0 for j in range(n)]
           for i in range(n)]
    seen = set()
    result = {}

    def groups_of(bond):
        comp = [-1] * n
        groups = []
        for s in range(n):
            if comp[s] != -1:
                continue
            cid = len(groups)
            comp[s] = cid
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v in range(n):
                    if comp[v] == -1 and bond[u][v] > 0:
                        comp[v] = cid
                        st.append(v)
                        mem.append(v)
            groups.append(mem)
        dists = []
        for mem in groups:
            d = {}
            for s in mem:
                dd = {s: 0}
                dq = deque([s])
                while dq:
                    u = dq.popleft()
                    for v in range(n):
                        if bond[u][v] > 0 and v not in dd:
                            dd[v] = dd[u] + 1
                            dq.append(v)
                d[s] = dd
            dists.append(d)
        return comp, groups, dists

    def dfs(bond, rem, path):
        if "path" in result:
            return
        st = (tuple((i, j, bond[i][j]) for i in range(n) for j in range(i + 1, n) if bond[i][j]),
              tuple(rem))
        if st in seen:
            return
        seen.add(st)
        comp, groups, dists = groups_of(bond)
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3 or dt[i][j] != 6:
                    continue
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append((key, i, j))
        if not cands:
            for mem in groups:
                if not any(atom_list[v] in TRI for v in mem):
                    continue
                mem = sorted(mem)
                ats = [atom_list[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                if classify_block(lib, ats, es) == "BAD":
                    result["path"] = list(path)
                    result["block"] = (ats, es)
                    return
            return
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        for t, (i, j) in enumerate(tied):
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            dfs(bond, rem, path + [(len(tied), t)])
            bond[i][j] -= 1
            bond[j][i] -= 1
            rem[i] += 1
            rem[j] += 1
            if "path" in result:
                return

    dfs([[0] * n for _ in range(n)], list(rem0), [])
    return result.get("path"), result.get("block")


def simulate_with_path(atom_list, l6_path):
    """完整规则 1~9 贪心；6 级阶段按 l6_path 选并列项（其余取第一个）。
    返回 (mols, block_structs, ok)。"""
    n = len(atom_list)
    if sum(VAL[e] for e in atom_list) % 2:
        return None, None, False
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = P.family_rank(atom_list[i], atom_list[j])

    def comps():
        comp = [-1] * n
        groups = []
        for s in range(n):
            if comp[s] != -1:
                continue
            cid = len(groups)
            comp[s] = cid
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v in adj[u]:
                    if comp[v] == -1:
                        comp[v] = cid
                        st.append(v)
                        mem.append(v)
            groups.append(mem)
        dists = []
        for mem in groups:
            d = {}
            for s in mem:
                dd = {s: 0}
                dq = deque([s])
                while dq:
                    u = dq.popleft()
                    for v in adj[u]:
                        if v not in dd:
                            dd[v] = dd[u] + 1
                            dq.append(v)
                d[s] = dd
            dists.append(d)
        return comp, groups, dists

    blocks = None
    block_structs = None
    l6_step = 0
    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]
        cands = []
        any6 = False
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                if dt[i][j] == 6:
                    any6 = True
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append((key, i, j))
        if not cands:
            break
        if blocks is None and not any6:
            blocks = [-1] * n
            block_structs = []
            for cid, mem in enumerate(groups):
                if any(atom_list[v] in TRI for v in mem):
                    mem2 = sorted(mem)
                    es2 = []
                    for a in range(len(mem2)):
                        for b in range(a + 1, len(mem2)):
                            m = bond[mem2[a]][mem2[b]]
                            if m:
                                es2.append((a, b, m))
                    block_structs.append({"atoms": [atom_list[v] for v in mem2],
                                          "edges": es2, "mem": mem2})
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        if any6 and l6_step < len(l6_path):
            n_tied, chosen = l6_path[l6_step]
            l6_step += 1
            i, j = tied[chosen] if (n_tied == len(tied) and chosen < len(tied)) else tied[0]
        else:
            i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None, block_structs, False
    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        ats = [atom_list[v] for v in mem]
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((a, b, m))
        mols.append({"atoms": ats, "edges": es})
    return mols, block_structs, True


def rems_of(atoms, edges, val=None):
    val = val or VAL
    used = [0] * len(atoms)
    for (a, b, m) in edges:
        used[a] += m
        used[b] += m
    return [val[e] - u for e, u in zip(atoms, used)]


def verify_genuine_example(lib):
    cat = {r["formula"]: r for r in json.load(open(BASE + r"\t4_catalog_all_validated.json",
                                                   encoding="utf-8"))}
    # 1) 主例：O3P5K2（10 原子纯三价）。先在该物质的实际原子顺序下 DFS 找库外分支。
    name = "O3P5K2"
    rec = cat[name]
    atoms = list(rec["atoms"])
    path, expected_block = find_bad_l6_branch(atoms, lib)
    mols_def, blocks_def, ok_def = simulate_with_path(atoms, [])
    mols_alt, blocks_alt, ok_alt = simulate_with_path(atoms, path or [])
    out = {"substance": name, "atoms": atoms, "n_atoms": len(atoms),
           "bad_branch_path": path,
           "expected_block": ({"atoms": expected_block[0],
                               "edges": [list(e) for e in expected_block[1]]}
                              if expected_block else None)}
    if ok_def:
        out["default_product_equals_catalog"] = (
            P.mol_label(mols_def[0]["atoms"], [tuple(e) for e in mols_def[0]["edges"]])
            == P.mol_label(rec["atoms"], [tuple(e) for e in rec["edges"]]))
    out["alt_ok"] = ok_alt
    if ok_alt:
        prod = mols_alt[0]
        out["alt_product"] = {"atoms": prod["atoms"], "edges": [list(e) for e in prod["edges"]],
                              "formula": P.formula_of(prod["atoms"])}
        prod_place = pot_v2.embed_mol2(prod["atoms"], [tuple(e) for e in prod["edges"]])
        out["alt_product_embeddable"] = prod_place is not None
        out["alt_product_place"] = ({str(k): list(v) for k, v in prod_place.items()}
                                    if prod_place else None)
        out["alt_block_structures"] = []
        for b in blocks_alt:
            km = classify_block(lib, b["atoms"], b["edges"])
            cl = block_label(b["atoms"], b["edges"])
            bplace = pot_v2.embed_mol2(b["atoms"], [tuple(e) for e in b["edges"]])
            out["alt_block_structures"].append({
                "atoms": b["atoms"], "edges": [list(e) for e in b["edges"]],
                "rems": rems_of(b["atoms"], b["edges"]),
                "kind": km, "label": cl,
                "place": ({str(k): list(v) for k, v in bplace.items()}
                          if bplace else None),
            })
        out["alt_block_matches_expected"] = bool(
            expected_block and blocks_alt and
            block_label(blocks_alt[0]["atoms"], blocks_alt[0]["edges"]) == block_label(*expected_block))
        out["alt_product_is_default_fixed_point"] = (
            ok_def and P.mol_label(mols_def[0]["atoms"], [tuple(e) for e in mols_def[0]["edges"]])
            == P.mol_label(prod["atoms"], [tuple(e) for e in prod["edges"]]))
        out["default_product_formula"] = P.formula_of(mols_def[0]["atoms"]) if ok_def else None
    # 2) 同族（同三价核心 + 不同装饰原子的目录物质）
    variants = []
    for f in ["O3P5K2A", "O3P5WK2", "O3XP5K2", "O3C2P5K2", "O3CP5K2F"]:
        r = cat.get(f)
        if not r:
            continue
        vpath, vblock = find_bad_l6_branch(list(r["atoms"]), lib)
        mols, blocks, ok = simulate_with_path(list(r["atoms"]), vpath or [])
        if not ok or not vblock:
            variants.append({"formula": f, "alt_ok": False, "found_bad_branch": bool(vpath)})
            continue
        bad = [b for b in blocks if classify_block(lib, b["atoms"], b["edges"]) == "BAD"]
        emb = pot_v2.embed_mol2(mols[0]["atoms"], [tuple(e) for e in mols[0]["edges"]])
        variants.append({"formula": f, "alt_ok": True,
                         "found_bad_branch": True,
                         "out_of_library_blocks": len(bad),
                         "product_embeddable": emb is not None,
                         "product_formula": P.formula_of(mols[0]["atoms"])})
    out["variants"] = variants
    # 3) 终态库外稳定物质示例（T15 机制：0 级同类键融合）
    terminal = []
    for f in ["O3P", "O2CK", "OCK2", "OCP2", "O2CP", "CPK2", "CP2K", "C2P3K", "O3KA2"]:
        r = cat.get(f)
        if not r:
            continue
        atoms2 = r["atoms"]
        edges2 = [tuple(e) for e in r["edges"]]
        n = len(atoms2)
        adj = [[] for _ in range(n)]
        for (a, b, m) in edges2:
            adj[a].append(b)
            adj[b].append(a)
        seen = [False] * n
        comps = []
        for s in range(n):
            if seen[s] or atoms2[s] not in TRI:
                continue
            seen[s] = True
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v in adj[u]:
                    if atoms2[v] in TRI and not seen[v]:
                        seen[v] = True
                        st.append(v)
                        mem.append(v)
            comps.append(sorted(mem))
        detail = []
        for mem in comps:
            ats = [atoms2[i] for i in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    m = 0
                    for (x, y, mm) in edges2:
                        if {x, y} == {mem[a], mem[b]}:
                            m = mm
                            break
                    if m:
                        es.append((a, b, m))
            detail.append({"atoms": ats, "edges": [list(e) for e in es],
                           "rems": rems_of(ats, es),
                           "in_library": classify_block(lib, ats, es) != "BAD",
                           "has_same_element_bond": any(ats[e[0]] == ats[e[1]] for e in es)})
        # F(v)=v 稳定性
        sim = pot_v3.simulate(list(atoms2))
        stable = (sim is not None and len(sim) == 1 and
                  P.mol_label(sim[0]["atoms"], [tuple(e) for e in sim[0]["edges"]])
                  == P.mol_label(atoms2, edges2))
        terminal.append({"formula": f, "n": n, "stable": stable, "components": detail})
    out["terminal_out_of_library"] = terminal
    return out


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    lib = load_library()
    report = {"library": verify_library(lib)}
    print("== 1) 库组成 ==")
    print(json.dumps(report["library"], ensure_ascii=False, indent=1))

    report["wl_key_bug"] = verify_wl_key(lib)
    print("== 2) wl_key 同构不变性 ==")
    print(json.dumps(report["wl_key_bug"], ensure_ascii=False, indent=1))

    print("== 3) 6 级并列全分支枚举 ==")
    report["level6_closure"] = verify_level6_closure(lib, max_total=10)
    print("   真·库外块:", json.dumps(report["level6_closure"]["bad_blocks"],
                                  ensure_ascii=False))

    print("== 4) T38 复核 ==")
    report["t38_original"] = verify_t38_original(lib)
    print("   t38 原版 100 物质:", json.dumps(report["t38_original"], ensure_ascii=False))
    report["t38b"] = verify_t38b(lib)
    print("   t38b 200 物质:", json.dumps({k: v for k, v in report["t38b"].items()
                                           if k != "wl_bad_substances"}, ensure_ascii=False))

    print("== 5) T15 复核 ==")
    report["t15"] = verify_t15(lib)
    print("   T15 候选 695 复核:", json.dumps({k: v for k, v in report["t15"].items()
                                               if k != "smallest_examples"}, ensure_ascii=False))
    report["t15_full_rescan"] = verify_t15_full_rescan(lib)
    print("   T15 全目录重扫:", json.dumps({k: v for k, v in report["t15_full_rescan"].items()
                                              if k != "smallest_examples"}, ensure_ascii=False))

    print("== 6) T37 多解复核 ==")
    report["t37"] = verify_t37(lib)
    print(json.dumps(report["t37"], ensure_ascii=False))

    print("== 7) 真·库外实例 ==")
    report["genuine_example"] = verify_genuine_example(lib)
    print(json.dumps({"substance": report["genuine_example"]["substance"],
                      "alt_ok": report["genuine_example"].get("alt_ok"),
                      "alt_block_structures": [{k: b[k] for k in ("atoms", "edges", "kind", "label")}
                                               for b in report["genuine_example"].get("alt_block_structures", [])],
                      "alt_product_is_default_fixed_point":
                          report["genuine_example"].get("alt_product_is_default_fixed_point"),
                      "variants": report["genuine_example"].get("variants")},
                     ensure_ascii=False, indent=1))

    report["seconds"] = round(time.time() - t0, 1)
    json.dump(report, open(BASE + r"\t39_library_verify.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t39_library_verify.json  (%.1fs)" % report["seconds"])


if __name__ == "__main__":
    main()
