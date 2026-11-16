# -*- coding: utf-8 -*-
"""t43_trace_o3p5k2.py：O3P5K2 的逐步演算（规则 1~9 正式口径）

输出每一步的完整 key 对比、并列裁决，以及 6 级结束时的骨架块和最终分子。
同时给出「规则 5 第二比较项方向被改写」时如何得到 O2P3K + OP2K（用于和手算结果对账）。
"""
import json
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2
from pot_v3 import rule9_extra

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = P.VAL

RULE_NAMES = ["1 距离", "2 剩余键和", "3 族序", "4 同/跨组件", "4 分子内距离",
              "5 最小组件", "5 最大组件", "6 并集种类", "7 种类和", "7 min种类",
              "7 max种类", "8 剩余键和", "8 min剩余键", "9 元素序"]


def run(atoms, size_key=None, verbose=True):
    """size_key: None=正式规则5 (min,-max)；否则为函数 (size_i,size_j)->tuple"""
    n = len(atoms)
    rem = [VAL[e] for e in atoms]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]

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

    steps = []
    level6 = None
    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
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
                sz = (min(csize[ci], csize[cj]), -max(csize[ci], csize[cj])) \
                    if size_key is None else size_key(csize[ci], csize[cj])
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       sz[0], sz[1], -ut, ti + tj, min(ti, tj), max(ti, tj),
                       -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append({"key": key, "i": i, "j": j,
                              "comp": (ci, cj), "csize": (csize[ci], csize[cj]),
                              "rem": (rem[i], rem[j]),
                              "union_counts": dict(celem[ci] + celem[cj])})
        if not cands:
            break
        if level6 is None and not any6:
            level6 = []
            for mem in groups:
                if any(atoms[v] in TRI for v in mem):
                    mem2 = sorted(mem)
                    es = []
                    for a in range(len(mem2)):
                        for b in range(a + 1, len(mem2)):
                            m = bond[mem2[a]][mem2[b]]
                            if m:
                                es.append((a, b, m))
                    level6.append({"mem": mem2, "atoms": [atoms[v] for v in mem2], "edges": es})
        best = min(c["key"] for c in cands)
        tied = [c for c in cands if c["key"] == best]
        # 与第二好的候选比较，找第一条不同 key 位置
        others = [c for c in cands if c["key"] != best]
        decisive = None
        if others:
            second = min(c["key"] for c in others)
            for k in range(len(best)):
                if best[k] != second[k]:
                    decisive = (RULE_NAMES[k], best[k], second[k])
                    break
        chosen = tied[0]
        steps.append({"step": len(steps),
                      "chosen": {"i": chosen["i"], "j": chosen["j"],
                                 "atoms": atoms[chosen["i"]] + "-" + atoms[chosen["j"]],
                                 "dt": dt[chosen["i"]][chosen["j"]],
                                 "rem": chosen["rem"],
                                 "comp": chosen["comp"], "csize": chosen["csize"]},
                      "n_tied": len(tied),
                      "tied_pairs": [(c["i"], c["j"]) for c in tied],
                      "decisive": decisive,
                      "second_key": second if others else None})
        i, j = chosen["i"], chosen["j"]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    # 最终分子
    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        ats = [atoms[v] for v in mem]
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((a, b, m))
        mols.append({"mem": mem, "atoms": ats, "edges": es})
    return {"steps": steps, "level6": level6, "mols": mols,
            "rem_final": rem, "ok": not any(r > 0 for r in rem)}


def print_trace(res, title):
    print("=" * 100)
    print(title)
    print("=" * 100)
    print("step | 选择原子对 | dt | rem_i,rem_j | 组件(大小) | 并列数 | 关键区分(规则,最佳值,次佳值)")
    for s in res["steps"]:
        d = s["decisive"]
        dec = f"{d[0]} {d[1]}<{d[2]}" if d else "-"
        c = s["chosen"]
        print(f"{s['step']:>3} | {c['i']}-{c['j']} {c['atoms']:<4} | {c['dt']} | "
              f"{c['rem'][0]},{c['rem'][1]} | {c['comp']}({c['csize']}) | {s['n_tied']:>2} | {dec}")
        if s["n_tied"] > 1:
            print(f"      并列对: {s['tied_pairs']} -> 取第一个 (候选顺序)")
    print()
    print("6 级结束时的中间态骨架（三价诱导子图连通块）:")
    for b in res["level6"]:
        used = [0] * len(b["atoms"])
        for (a, bb, m) in b["edges"]:
            used[a] += m
            used[bb] += m
        rems = [3 - u for u in used]
        print("  atoms:", b["atoms"])
        print("  edges:", b["edges"])
        print("  rem  :", rems, " 键数:", sum(e[2] for e in b["edges"]))
    print()
    print("最终分子:")
    for m in res["mols"]:
        print("  atoms:", m["atoms"])
        print("  edges:", m["edges"])
        print("  键数:", sum(e[2] for e in m["edges"]))
    print("  react ok:", res["ok"], " 剩余 rem:", res["rem_final"])


def main():
    atoms = P.vec_to_atoms(P.parse_formula("O3P5K2"), P.ORDER)
    print("atoms (投料顺序):", atoms, " 原子数:", len(atoms))

    official = run(atoms)
    print_trace(official, "【正式规则 1~9】O3P5K2")

    # 规则 5 第二比较项取反的变体（手算可能的口径）
    variant = run(atoms, size_key=lambda a, b: (min(a, b), max(a, b)))
    print_trace(variant, "【变体：规则 5 = (min, +max)（第二项方向取反）】O3P5K2")

    # 保存
    out = {
        "atoms": atoms,
        "official": {"steps": official["steps"],
                     "level6": official["level6"],
                     "mols": official["mols"]},
        "rule5_variant": {"steps": variant["steps"],
                          "level6": variant["level6"],
                          "mols": variant["mols"]},
    }
    json.dump(out, open(BASE + r"\t43_o3p5k2_trace.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t43_o3p5k2_trace.json")

    # 结构检查
    print()
    print("最终分子可摆性（pot_v2.embed_mol2）:",
          [pot_v2.embed_mol2(m["atoms"], m["edges"]) is not None for m in official["mols"]])
    print("分子式:", [P.formula_of(m["atoms"]) for m in official["mols"]])


if __name__ == "__main__":
    main()
