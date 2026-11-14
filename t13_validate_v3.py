# -*- coding: utf-8 -*-
"""t13_validate_v3：正式模拟器 pot_v3（规则 1~9）的一致性验证。
  - 与 t12_rule9e 的实现逐投料对比（T=3..9 全量）；
  - 与旧 pot_all（规则 1~8 + tied[0]）对比，统计规则 9 改变了多少投料的产物。
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
from t12_rule9e import simulate_rule9e, gen_compositions

BASE = r"G:\AI work\deepseek\work1\alchemy"


def forms(mols):
    if mols is None:
        return None
    return tuple(sorted(P.formula_of(m["atoms"]) for m in mols))


def work(T):
    ncase = 0
    n_v3_vs_9e = 0
    n_v3_vs_old = 0
    diff_examples = []
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        f3 = forms(pot_v3.simulate(atoms))
        f9 = simulate_rule9e(atoms, None)  # 已返回分子式元组
        fold = forms(P.simulate(atoms))
        if f3 != f9:
            n_v3_vs_9e += 1
            if len(diff_examples) < 4:
                diff_examples.append({"feed": list(counts), "T": T, "v3": f3, "rule9e": f9})
        if f3 != fold:
            n_v3_vs_old += 1
            if len(diff_examples) < 4:
                diff_examples.append({"feed": list(counts), "T": T, "v3": f3, "old": fold})
    return T, ncase, n_v3_vs_9e, n_v3_vs_old, diff_examples


def main():
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    total = [0, 0, 0]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T, ncase, d1, d2, exs in ex.map(work, list(range(3, 10))):
            results[str(T)] = {"ncase": ncase, "v3_vs_rule9e_diff": d1, "v3_vs_old_diff": d2,
                               "examples": exs}
            total[0] += ncase
            total[1] += d1
            total[2] += d2
            print(f"T={T}: 投料 {ncase}, v3与9e不同 {d1}, v3与旧口径不同 {d2}", flush=True)
    print("TOTAL", {"cases": total[0], "v3_vs_9e": total[1], "v3_vs_old": total[2]})
    json.dump({"total": total, "rows": results}, open(BASE + r"\t13_validate_v3.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
