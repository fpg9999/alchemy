# -*- coding: utf-8 -*-
"""scan_all.py —— 按范围枚举可产出物质（通用版，pot_all）"""
import json
import random
import sys
import time
from collections import deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
IDX = {s: i for i, s in enumerate(ORDER)}

SCOPES = {
    1: ("动素", ["P", "W", "L"]),
    2: ("散素", ["K", "A", "F"]),
    3: ("聚素+散素", ["O", "X", "C", "K", "A", "F"]),
    4: ("聚素+动素", ["O", "X", "C", "P", "W", "L"]),
    5: ("动素+散素", ["P", "W", "L", "K", "A", "F"]),
    6: ("聚素+动素+散素", ["O", "X", "C", "P", "W", "L", "K", "A", "F"]),
}


def vec_from_counts(counts):
    return tuple(counts.get(s, 0) for s in ORDER)


def atoms_of_vec(v):
    out = []
    for s, c in zip(ORDER, v):
        out.extend([s] * c)
    return out


def vec_of_formula(f):
    v = [0] * 9
    i = 0
    while i < len(f):
        s = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        v[IDX[s]] += int(num) if num else 1
    return tuple(v)


def semigroup(vectors, N):
    """所有非负组合、总原子<=N 的计数向量"""
    reach = set()
    zero = tuple([0] * 9)
    stack = [zero]
    seen = {zero}
    while stack:
        v = stack.pop()
        reach.add(v)
        for g in vectors:
            nv = tuple(v[i] + g[i] for i in range(9))
            if sum(nv) <= N and nv not in seen:
                seen.add(nv)
                stack.append(nv)
    return reach


def base_generators(elems):
    gens = []
    for s in elems:
        v = [0] * 9
        v[IDX[s]] = 2          # 单质均为二聚体（三键/双键/单键）
        gens.append(tuple(v))
    return gens


def run_scope(scope_id, N=18, verbose=True):
    name, elems = SCOPES[scope_id]
    gens = base_generators(elems)
    known = {}      # formula -> vec
    example = {}    # formula -> 投料 vec
    reasons = {"剩键": 0, "摆不出来": 0, "ok": 0}
    rng = random.Random(1234)
    it = 0
    t0 = time.time()
    while True:
        vecs = semigroup(gens, N)
        vecs = sorted(vecs, key=lambda v: (sum(v), v))
        new = 0
        for v in vecs:
            atoms = atoms_of_vec(v)
            if not atoms:
                continue
            mols = P.simulate(atoms)
            if mols is None:
                reasons["剩键"] += 1
                continue
            if not P.embed_all(mols):
                reasons["摆不出来"] += 1
                continue
            reasons["ok"] += 1
            for m in mols:
                f = P.formula_of(m["atoms"])
                if f not in known:
                    known[f] = vec_of_formula(f)
                    example[f] = v
                    new += 1
        it += 1
        if verbose:
            print(f"  iter {it}: 可达向量={len(vecs)} 已知={len(known)} 新增={new} "
                  f"({time.time()-t0:.1f}s) 失败统计={reasons}", flush=True)
        if new == 0:
            break
        gens = list(known.values()) + base_generators(elems)
        # 去重
        gens = list(dict.fromkeys(gens))
        if it >= 10:
            break
    out = []
    for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))):
        v = known[f]
        mols = P.simulate(atoms_of_vec(example[f]))
        natoms = sum(v)
        out.append({
            "scope": name,
            "formula": f,
            "zh": P.zh_of([s for s in ORDER for _ in range(v[IDX[s]])]),
            "vec": list(v),
            "natoms": natoms,
            "feed": list(example[f]),
        })
    return {"scope": name, "elems": elems, "N": N, "formulas": out,
            "known": known, "example": example, "reasons": reasons}


def load_prev():
    """读取已有结果（若有）"""
    try:
        return json.load(open(r"G:\AI work\deepseek\work1\alchemy\substances_all.json",
                              encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    sid = int(sys.argv[1])
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 18
    res = run_scope(sid, N)
    print(f"\n=== 范围 {sid} {res['scope']} ===  N={N}  公式数={len(res['formulas'])}")
    for x in res["formulas"]:
        print(f"  {x['formula']:10s} {x['zh']:10s} 原子={x['natoms']:2d} 例投料={tuple(x['feed'])}")
