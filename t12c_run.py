# -*- coding: utf-8 -*-
"""t12c_run.py —— T12C 主采样：目录分层随机对 + 反应计算（多进程）+ 结果缓存。

分层（按条目 natoms）：L1=2-8, L2=9-16, L3=17-32, L4=33+。
每层随机抽 npairs 个「不同公式」的无序对 (A,B)，A!=B。
反应只由总向量决定，故按「唯一总向量」去重后并行计算，再回填到各对。

用法:
  python t12c_run.py            # 用默认参数跑
  python t12c_run.py 2000 2500 2000 1500 18   # 各层对数 + 进程数
输出: t12c_sample_pairs.json, t12c_vectors.json, t12c_run_log.txt
"""
import json, sys, os, time, random
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v2
import pot_v3

ORDER = list(P.ORDER)
LAYER_DEF = [("L1_2-8", 2, 8), ("L2_9-16", 9, 16), ("L3_17-32", 17, 32), ("L4_33+", 33, 10**9)]
DEFAULT_NP = [2000, 2500, 2000, 1500]
EMBED_CAP = 3_000_000  # 每个产物分子的 embedding 节点预算（约 20s 上限）


def vec9_of(d):
    return tuple(P.parse_formula(d["formula"]))


def atoms_of(v):
    return [e for e, c in zip(ORDER, v) for _ in range(c)]


def mol_key(mol):
    """分子（原子+键）的规范键：按元素稳定排序后重标号，用于 embedding 缓存。"""
    atoms = mol["atoms"]
    idx = sorted(range(len(atoms)), key=lambda i: (atoms[i], i))
    rank = {old: new for new, old in enumerate(idx)}
    se = []
    for a, b, m in mol["edges"]:
        ra, rb = rank[a], rank[b]
        if ra > rb:
            ra, rb = rb, ra
        se.append((ra, rb, m))
    se.sort()
    return (tuple(atoms[i] for i in idx), tuple(se))


_EMBED_CACHE = {}


def check_mol(mol):
    k = mol_key(mol)
    v = _EMBED_CACHE.get(k)
    if v is None:
        r = pot_v2.embed_mol2(mol["atoms"], mol["edges"], max_nodes=EMBED_CAP)
        v = {"ok": r is not None, "n": len(mol["atoms"])}
        _EMBED_CACHE[k] = v
    return v


def _worker(v):
    """v: tuple(9)。返回该总向量的反应结果。"""
    t0 = time.time()
    atoms = atoms_of(v)
    mols = pot_v3.simulate(atoms)
    sim_s = time.time() - t0
    n = len(atoms)
    if mols is None:
        return {"status": "fail_rem", "n": n, "prods": None, "nmol": 0, "maxmol": 0,
                "sim_s": round(sim_s, 4), "embed_s": 0.0, "embed_fail": []}
    prods = sorted(P.formula_of(m["atoms"]) for m in mols)
    t1 = time.time()
    fails = []
    ok = True
    for m in mols:
        r = check_mol(m)
        if not r["ok"]:
            ok = False
            fails.append(r["n"])
    embed_s = time.time() - t1
    return {"status": "ok" if ok else "fail_embed", "n": n, "prods": prods,
            "nmol": len(mols), "maxmol": max(len(m["atoms"]) for m in mols),
            "sim_s": round(sim_s, 4), "embed_s": round(embed_s, 4), "embed_fail": fails}


def sample_layer(idx_list, npairs, rng):
    """在层内随机抽无序对，返回**全局 entry 下标**对。"""
    n = len(idx_list)
    pairs = set()
    guard = 0
    while len(pairs) < npairs and guard < npairs * 200:
        guard += 1
        i = rng.randrange(n)
        j = rng.randrange(n)
        if i == j:
            continue
        if i > j:
            i, j = j, i
        pairs.add((idx_list[i], idx_list[j]))
    return sorted(pairs)


def vkey(v):
    return ",".join(str(x) for x in v)


def main():
    args = sys.argv[1:]
    nps = [int(x) for x in args[:4]] if len(args) >= 4 else DEFAULT_NP
    nproc = int(args[4]) if len(args) >= 5 else 18
    t_start = time.time()

    cat = json.load(open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))
    entries = []
    for d in cat:
        v = vec9_of(d)
        n = sum(v)
        entries.append({"formula": d["formula"], "vec": v, "natoms": n, "source": d.get("source")})
    entries.sort(key=lambda e: (e["natoms"], e["formula"]))
    # 每个 natoms 层内的下标
    layer_idx = {}
    for li, (name, lo, hi) in enumerate(LAYER_DEF):
        layer_idx[li] = [i for i, e in enumerate(entries) if lo <= e["natoms"] <= hi]
    print("层大小:", {LAYER_DEF[li][0]: len(layer_idx[li]) for li in range(4)}, flush=True)

    pairs_rec = []           # (layer, i, j)
    for li, (name, lo, hi) in enumerate(LAYER_DEF):
        rng = random.Random(20261113 + li * 7919)
        idx = layer_idx[li]
        ps = sample_layer(idx, nps[li], rng)
        for i, j in ps:
            pairs_rec.append({"layer": name, "i": i, "j": j})
        print(f"{name}: 采样 {len(ps)} 对", flush=True)

    # 唯一总向量
    totals = {}
    for pr in pairs_rec:
        va = entries[pr["i"]]["vec"]
        vb = entries[pr["j"]]["vec"]
        v = tuple(a + b for a, b in zip(va, vb))
        pr["vk"] = vkey(v)
        totals[pr["vk"]] = v
    uniq = sorted(totals.items(), key=lambda kv2: -sum(kv2[1]))
    print(f"配对 {len(pairs_rec)}；唯一总向量 {len(uniq)}", flush=True)

    json.dump({"params": {"npairs": nps, "nproc": nproc, "embed_cap": EMBED_CAP,
                          "seed": "20261113 + layer*7919", "layers": LAYER_DEF},
               "entries": entries,
               "pairs": pairs_rec},
              open(os.path.join(BASE, "t12c_sample_pairs.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print("配对已落盘 t12c_sample_pairs.json", flush=True)

    from multiprocessing import Pool
    results = {}
    log = open(os.path.join(BASE, "t12c_run_log.txt"), "w", encoding="utf-8")
    done = 0
    t0 = time.time()
    # 大向量优先，改善尾部负载均衡
    tasks = [v for _, v in uniq]
    with Pool(nproc) as pool:
        for v, res in zip(tasks, pool.imap(_worker, tasks, chunksize=1)):
            results[vkey(v)] = res
            done += 1
            if done % 100 == 0 or done == len(tasks):
                el = time.time() - t0
                avg = el / done
                msg = (f"{done}/{len(tasks)} elapsed={el:.0f}s avg={avg:.2f}s "
                       f"eta={avg*(len(tasks)-done)/60:.1f}min "
                       f"last_n={res['n']} last={res['status']} last_s={res['sim_s']+res['embed_s']:.2f}")
                print(msg, flush=True)
                log.write(msg + "\n")
                log.flush()
                if done % 500 == 0:
                    json.dump(results, open(os.path.join(BASE, "t12c_vectors.json"), "w",
                                            encoding="utf-8"), ensure_ascii=False)
    log.close()
    json.dump(results, open(os.path.join(BASE, "t12c_vectors.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"完成，用时 {(time.time()-t_start)/60:.1f} min；结果 t12c_vectors.json", flush=True)

    # 简短统计
    st = Counter(r["status"] for r in results.values())
    print("状态:", dict(st), flush=True)
    big = [r for r in results.values() if r["status"] == "ok"]
    print("成功 maxmol 分布:", Counter(b["maxmol"] for b in big).most_common(12), flush=True)
    print("最慢 10:", sorted(((r["sim_s"] + r["embed_s"], k) for k, r in results.items()),
                           reverse=True)[:10], flush=True)


if __name__ == "__main__":
    main()
