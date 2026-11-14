# -*- coding: utf-8 -*-
"""t34_temp_compare.py：比较两种温度判定
规则旧：T >= max(参与者阈值)
规则新：T >= sum(参与者阈值)
统计 k=2..5 体系的阈值分布、固定温度下可反应比例、温度窗口宽度。
"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from t28_rule_v2 import wake, select_class, VAL

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 4 and r.get("place")]
rng = random.Random(2468)


def metrics(system):
    """system: list of (atoms, edges)"""
    atom_list = []
    edges = []
    for atoms, es in system:
        off = len(atom_list)
        atom_list += atoms
        for e in es:
            edges.append((e[0] + off, e[1] + off, e[2] if len(e) > 2 else 1))
    bond, dt, fam = wake(atom_list, edges)
    cls = select_class(atom_list, bond, dt, use_valence=True)
    if cls is None:
        return None
    d, negm, v = cls
    mclass = -negm
    # 每个分子总键数 c，及不完全断键数 i
    cs = []
    ins = []
    off = 0
    for atoms, es in system:
        n = len(atoms)
        cbond = [[0] * n for _ in range(n)]
        for e in es:
            i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
            cbond[i][j] = cbond[j][i] = m
        c = sum(e[2] if len(e) > 2 else 1 for e in es)
        ii = 0
        for x in range(n):
            for y in range(x + 1, n):
                if cbond[x][y] == mclass:
                    dd = P.ptable_dist(atoms[x], atoms[y])
                    vv = min(VAL[atoms[x]], VAL[atoms[y]])
                    if dd == d and vv == v:
                        ii += 1
        cs.append(c)
        ins.append(ii)
        off += n
    return {"c": cs, "i": ins, "k": len(system), "class": cls}


def main():
    stats = {}
    for k in (2, 3, 4, 5):
        rows = []
        while len(rows) < 500:
            recs = rng.sample(pool, k)
            if sum(len(r["atoms"]) for r in recs) > 4 * k + 2:
                continue
            system = [(list(r["atoms"]), [tuple(e) for e in r["edges"]]) for r in recs]
            m = metrics(system)
            if not m:
                continue
            parts = [i for i in m["i"] if i > 0]
            if not parts:
                continue
            rows.append(m)
        st = Counter()
        for m in rows:
            inc_max = max(m["i"])
            inc_sum = sum(m["i"])
            comp_max = max(m["c"])
            comp_sum = sum(m["c"])
            st["n"] += 1
            st["inc_max_sum"] += inc_max
            st["inc_sum_sum"] += inc_sum
            st["comp_max_sum"] += comp_max
            st["comp_sum_sum"] += comp_sum
            st["inc_window_max_sum"] += comp_max - inc_max
            st["inc_window_sum_sum"] += comp_sum - inc_sum
            for T in (2, 3, 4, 5, 6, 8, 10, 15, 20):
                if T >= inc_max:
                    st[f"old_inc_{T}"] += 1
                if T >= comp_max:
                    st[f"old_comp_{T}"] += 1
                if T >= inc_sum:
                    st[f"new_inc_{T}"] += 1
                if T >= comp_sum:
                    st[f"new_comp_{T}"] += 1
        stats[k] = {
            "n": st["n"],
            "avg_inc_max": st["inc_max_sum"] / st["n"],
            "avg_inc_sum": st["inc_sum_sum"] / st["n"],
            "avg_comp_max": st["comp_max_sum"] / st["n"],
            "avg_comp_sum": st["comp_sum_sum"] / st["n"],
            "avg_inc_window_old": st["inc_window_max_sum"] / st["n"],
            "avg_inc_window_new": st["inc_window_sum_sum"] / st["n"],
            "old_inc": {T: st[f"old_inc_{T}"] / st["n"] for T in (2, 3, 4, 5, 6, 8, 10, 15, 20)},
            "new_inc": {T: st[f"new_inc_{T}"] / st["n"] for T in (2, 3, 4, 5, 6, 8, 10, 15, 20)},
            "old_comp": {T: st[f"old_comp_{T}"] / st["n"] for T in (2, 3, 4, 5, 6, 8, 10, 15, 20)},
            "new_comp": {T: st[f"new_comp_{T}"] / st["n"] for T in (2, 3, 4, 5, 6, 8, 10, 15, 20)},
        }
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    json.dump(stats, open(BASE + r"\t34_temp_compare.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t34_temp_compare.json")


if __name__ == "__main__":
    main()
