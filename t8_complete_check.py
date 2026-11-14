# -*- coding: utf-8 -*-
"""t8_complete_check.py
验证「38 种骨架库」在更大规模下是否封闭：
 A) 穷举计数网格 0..16 全覆盖（并行）
 B) 随机大计数（每类 0..36、样本 60 组）
 C) 对 38 个模板做放大 t=2..6 实验（看是否只复制、不出新形态）
"""
import json
import sys
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import t8_level6_forms as T

BASE = r"G:\AI work\deepseek\work1\alchemy"


def key_of(c):
    return (c["label"], tuple(sorted(c["rems"])), tuple(sorted(c["atoms"])))


def scan_grid(nO):
    out = {}
    mx = 0
    ma = 0
    for nP in range(0, 17):
        for nK in range(0, 17):
            if nO + nP + nK == 0:
                continue
            for c in T.level6_components((nO, nP, nK)):
                k = key_of(c)
                if k not in out:
                    out[k] = {"formula": T.formula_of(c["atoms"]), "size": len(c["atoms"]),
                              "active": sum(1 for r in c["rems"] if r > 0)}
                mx = max(mx, len(c["atoms"]))
                ma = max(ma, sum(1 for r in c["rems"] if r > 0))
    return out, mx, ma


def main():
    lib = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
    lib_keys = {(P.mol_label(f["atoms"], [tuple(e) for e in f["edges"]]), tuple(sorted(f["rems"])), tuple(sorted(f["atoms"]))) for f in lib}
    report = {}

    # A) 穷举 0..16
    allnew = {}
    mx = ma = 0
    with ProcessPoolExecutor(max_workers=16) as ex:
        for out, m1, m2 in ex.map(scan_grid, range(17)):
            mx = max(mx, m1)
            ma = max(ma, m2)
            for k, v in out.items():
                if k not in lib_keys:
                    allnew[k] = v
                else:
                    pass
    report["A_grid16"] = {"new_forms": len(allnew), "max_component": mx, "max_active": ma,
                          "examples": list(allnew.values())[:10]}
    print(f"A) 穷举 0..16: 新形态={len(allnew)} 最大组件={mx} 最大活跃={ma}", flush=True)

    # B) 随机大计数
    rng = random.Random(2026)
    newB = {}
    mxB = maB = 0
    samples = []
    for _ in range(60):
        counts = (rng.randint(0, 36), rng.randint(0, 36), rng.randint(0, 36))
        samples.append(counts)
        for c in T.level6_components(counts):
            k = key_of(c)
            mxB = max(mxB, len(c["atoms"]))
            maB = max(maB, sum(1 for r in c["rems"] if r > 0))
            if k not in lib_keys:
                newB[k] = {"formula": T.formula_of(c["atoms"]), "size": len(c["atoms"]),
                           "counts": counts}
    report["B_random36"] = {"samples": len(samples), "new_forms": len(newB),
                            "max_component": mxB, "max_active": maB,
                            "examples": list(newB.values())[:10]}
    print(f"B) 随机 0..36 ×60: 新形态={len(newB)} 最大组件={mxB} 最大活跃={maB}", flush=True)

    # C) 模板放大
    scale_report = []
    for f in lib:
        cnt = [f["atoms"].count(e) for e in ("O", "P", "K")]
        if sum(cnt) == 0:
            continue
        base_keys = None
        for t in (2, 3, 4, 5, 6):
            counts = tuple(v * t for v in cnt)
            comps = T.level6_components(counts)
            keys = Counter(key_of(c) for c in comps)
            if base_keys is None:
                base_keys = keys
            newc = [k for k in keys if k not in lib_keys]
            # 检查是否全部为原形态的副本（允许出现库内其它形态的副本）
            if newc:
                scale_report.append({"formula": f["formula"], "t": t,
                                     "new": [lib_k_formula(k) for k in newc]})
        # 记录 t=2 时是否等于 2 份
        counts2 = tuple(v * 2 for v in cnt)
        comps2 = T.level6_components(counts2)
        got = Counter(key_of(c) for c in comps2)
        scale_report.append({"formula": f["formula"], "t": 2,
                             "components": [T.formula_of(c["atoms"]) for c in comps2]})
    report["C_scale"] = scale_report[:40]
    n_new_scale = sum(1 for r in scale_report if "new" in r)
    print(f"C) 模板放大 t=2..6: 出现库外形态的模板数={n_new_scale}", flush=True)

    json.dump(report, open(BASE + r"\t8_complete_check.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t8_complete_check.json")


def lib_k_formula(k):
    return T.formula_of(list(k[2]))


if __name__ == "__main__":
    main()
