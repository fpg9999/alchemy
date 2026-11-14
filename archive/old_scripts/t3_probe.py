# -*- coding: utf-8 -*-
"""t3_probe：对可疑子集做大规模随机大投料探针，验证"最大单分子"是否随投料上限增长。"""
import json
import random
import sys
import time
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
INF = []  # 满足 a>=2, b>=1
THREE = set("OPK")
TWO = set("XWA")


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def probe(elems, Ts, samples, seed=1, budget=200000):
    rng = random.Random(seed)
    out = {}
    for T in Ts:
        best = (0, None, None)
        tries = 0
        for _ in range(samples):
            v = rand_vec(T, len(elems), rng)
            atoms = P.vec_to_atoms(tuple(v), elems)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            tries += 1
            mols = P.simulate(atoms)
            if not mols:
                continue
            mx = max(len(m["atoms"]) for m in mols)
            if mx <= best[0]:
                continue
            m = [x for x in mols if len(x["atoms"]) == mx][0]
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=budget) is None:
                continue
            if not P.embed_all(mols):
                continue
            best = (mx, P.formula_of(m["atoms"]), list(v))
        out[T] = {"max": best[0], "formula": best[1], "feed": best[2], "tries": tries}
    return out


def ai(elems):
    a = len(set(elems) & THREE)
    b = len(set(elems) & TWO)
    return a, b, (a >= 2 and b >= 1)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "susp"
    if which == "susp":
        sets = [
            "X C K A", "X K A F", "X C K", "K A F", "O X A", "O K W", "P K X",
            "O C K A F", "X C K A F", "O X C K A F",
        ]
        Ts = [24, 32, 40]
        samples = 400
    elif which == "triples":
        import itertools
        sets = [" ".join(t) for t in itertools.combinations(P.ORDER, 3)]
        Ts = [24, 32]
        samples = 300
    else:
        sets = which.split("|")
        Ts = [24, 32, 40, 48]
        samples = 400
    res = {}
    for s in sets:
        elems = s.split()
        t0 = time.time()
        r = probe(elems, Ts, samples, seed=hash(s) & 0xffff)
        a, b, pred = ai(elems)
        res[s] = {"a": a, "b": b, "pred_inf": pred, "probe": r}
        print(f"{s:16s} a={a} b={b} pred={'∞' if pred else '有限'} "
              + " ".join(f"T{T}={r[T]['max']:2d}({r[T]['formula']})" for T in Ts)
              + f"  [{time.time()-t0:.1f}s]", flush=True)
    name = which.replace(" ", "_")
    json.dump(res, open(BASE + rf"\t3_probe_{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
