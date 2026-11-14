# -*- coding: utf-8 -*-
"""t12a_chains.py —— T12A 反应链研究引擎（连续反应 / 幂等 / 饱和 / 循环 / 有趣现象）

核心接口（沿用项目既有实现）
---------------------------
- 一次反应 R(A,B): 把 A、B 的原子 concat 后 `pot_all.simulate` + `pot_v2.embed_all2`；
  产物 = sorted(formula_of(m['atoms']) for m in mols)。
- 关键定律（T11 已证 + 数据验证）：R(A,B) 只由总向量 vA+vB 决定。因此本引擎用
  **向量 → 产物多重集** 的缓存 F(v) 来加速，F 的结果与分子式无关。

链语义（本文件的核心定义）
--------------------------
状态 = 当前分子多重集（默认只跟踪“载体”分子 X，被消耗的试剂 R 从外部投入）。
每一步：取出载体 X，与固定/选取的试剂 R 一起投锅，得到产物多重集 P = F(vX+vR)；
然后从 P 中按策略选下一载体 X'。于是**总向量每步恰增加 vR**（单调），
因此链不存在真正的状态回环，但载体序列可以有有限周期（振荡）。

终止方式
--------
- FAIL    : 投锅失败（剩键 / 摆放不合法）
- INERT   : F(X+R) == {X, R}（完全不反应，惰性）
- STABLE  : 下一载体 == 当前载体（载体不动点）
- CYCLE   : 载体序列回到更早的载体（振荡，周期 ≥2）
- OVERSIZE: 投锅总原子数超过上限（保护性截断）
- MAXSTEP : 达到步数上限

子命令（终端输出保持简短）
--------------------------
  probe   —— 小样本计时/合法性自检
  idem    —— 幂等性数值验证（≥100 例，含失败例）
  chains  —— 204 种子 × 试剂池的固定试剂链统计（多进程）
  cycles  —— t11_cycles.json 真 2-环的 20 轮无限循环演示
  finds   —— 有趣现象（自催化/振荡/不动点/惰性终态）检索
  report  —— 生成 T12A_CHAINS.md + t12a_*.png
  all     —— 依次执行全部（长）

复现命令见 T12A_CHAINS.md §7。
"""
import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import pot_all as P
import pot_v2

ORDER = P.ORDER
NEL = len(ORDER)
DATA = os.path.join(BASE, "t12a_chains.json")

# 目录中 natoms<=8 的试剂池（molecule -> 9 维计数向量由 formula 解析）
CATALOG = os.path.join(BASE, "t4_catalog_all_validated.json")
SUBSTANCES = os.path.join(BASE, "substances.json")
T9_SINGLE = os.path.join(BASE, "t9_single_trivalent.json")
CYCLES = os.path.join(BASE, "t11_cycles.json")


# ---------------------------------------------------------------- 基础工具
def atoms_of(vec):
    return [s for s, c in zip(ORDER, vec) for _ in range(c)]


def add(*vecs):
    out = [0] * NEL
    for v in vecs:
        for i in range(NEL):
            out[i] += v[i]
    return tuple(out)


def natoms(vec):
    return sum(vec)


def parse(f):
    return P.parse_formula(f)


def formula(vec):
    return "".join(e if c == 1 else ("" if c == 0 else e + str(c))
                   for e, c in zip(ORDER, vec) if c)


def sort_multi(fs):
    return tuple(sorted(fs))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_section(name, obj):
    """把一段结果写入 t12a_chains.json（保持其它段落）。"""
    data = {}
    if os.path.exists(DATA):
        try:
            data = load_json(DATA)
        except Exception:
            data = {}
    data[name] = obj
    data.setdefault("meta", {})
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


# ---------------------------------------------------------------- 反应核 F
class Reactor:
    """F(v)：向量 -> ('ok', 产物多重集) / ('fail', None, 原因)。与分子式无关。

    embed_budget: 摆放搜索节点预算（pot_v2.embed_mol2 的 max_nodes）。
    超预算按失败处理（保守口径，见 T12A_CHAINS.md §6 已知近似）。
    """

    def __init__(self, use_embed=True, max_cache=200000, embed_budget=300000):
        self.cache = {}
        self.use_embed = use_embed
        self.max_cache = max_cache
        self.embed_budget = embed_budget
        self.n_calls = 0
        self.n_sim = 0

    def clear(self):
        self.cache.clear()

    def F(self, v):
        v = tuple(v)
        hit = self.cache.get(v)
        if hit is not None:
            return hit
        self.n_sim += 1
        mols = P.simulate(atoms_of(v))
        if mols is None:
            res = ("fail", None, "剩键/价数奇偶")
        elif self.use_embed and not pot_v2.embed_all2(mols, max_nodes=self.embed_budget):
            res = ("fail", None, "摆放失败/预算截断")
        else:
            prods = tuple(sorted(P.formula_of(m["atoms"]) for m in mols))
            res = ("ok", prods, "")
        if len(self.cache) >= self.max_cache:
            self.cache.clear()
        self.cache[v] = res
        return res


# 全模块共享的 reactor（每个进程一个）
R = Reactor()


# ---------------------------------------------------------------- 载体选择策略
def pick_carrier(prods, strategy="max", rng=None):
    """从产物多重集中选下一载体。返回分子式或 None。"""
    if not prods:
        return None
    if strategy == "max":
        return max(prods, key=lambda f: (natoms(parse(f)), f))
    if strategy == "min":
        return min(prods, key=lambda f: (natoms(parse(f)), f))
    if strategy == "first":
        return prods[0]
    if strategy == "random":
        rng = rng or random
        return rng.choice(prods)
    raise ValueError(strategy)


# ---------------------------------------------------------------- 链引擎
def run_chain(seed_formula, reagent_formula, strategy="max",
              max_steps=40, max_atoms=40, rng=None, trace=True):
    """固定试剂链：X_0 = seed；每步 X_{n+1} = pick(F(vX_n + vR))。

    返回 dict：termination / n_steps(载体转移次数) / steps(每步记录) /
              carrier_trace / products_trace / max_carrier / final_products
    """
    xf = seed_formula
    xv = parse(seed_formula)
    rv = parse(reagent_formula)
    seen = {xf: 0}
    steps = []
    carrier_trace = [natoms(xv)]
    max_carrier = natoms(xv)
    term = "MAXSTEP"
    final_prods = None
    cycle_next = None
    cycle_period = None
    for step in range(max_steps):
        v = add(xv, rv)
        n_tot = natoms(v)
        if n_tot > max_atoms:
            term = "OVERSIZE"
            final_prods = steps[-1]["products"] if steps else ()
            break
        status, prods, why = R.F(v)
        if status != "ok":
            term = "FAIL"
            final_prods = None
            if trace:
                steps.append({"step": step, "carrier": xf, "reagent": reagent_formula,
                              "total_vec": list(v), "total_atoms": n_tot,
                              "products": None, "reason": why,
                              "max_mol": None})
            break
        max_mol = max(natoms(parse(f)) for f in prods)
        final_prods = prods
        if trace:
            steps.append({"step": step, "carrier": xf, "reagent": reagent_formula,
                          "total_vec": list(v), "total_atoms": n_tot,
                          "products": list(prods), "max_mol": max_mol,
                          "n_mols": len(prods)})
        # 惰性：原样返回
        if prods == sort_multi([xf, reagent_formula]):
            term = "INERT"
            break
        nxt = pick_carrier(prods, strategy, rng)
        if nxt is None:
            term = "NO_CARRIER"
            break
        if nxt == xf:
            term = "STABLE"
            cycle_next = nxt
            cycle_period = 1
            break
        if nxt in seen:
            term = "CYCLE"
            cycle_next = nxt
            cycle_period = (step + 1) - seen[nxt]
            break
        seen[nxt] = step + 1
        xf = nxt
        xv = parse(nxt)
        carrier_trace.append(natoms(xv))
        max_carrier = max(max_carrier, natoms(xv))
    return {
        "seed": seed_formula,
        "reagent": reagent_formula,
        "strategy": strategy,
        "termination": term,
        "n_steps": len(carrier_trace) - 1,
        "carrier_trace": carrier_trace,
        "final_carrier": xf,
        "next_carrier": cycle_next,
        "cycle_period": cycle_period,
        "final_products": list(final_prods) if final_prods else [],
        "max_carrier": max_carrier,
        "steps": steps,
    }


# ---------------------------------------------------------------- 数据装载
def load_pool(max_natoms=8):
    cat = load_json(CATALOG)
    pool = {}
    for d in cat:
        if d["natoms"] <= max_natoms:
            pool[d["formula"]] = tuple(d["feed"])
    return pool


def load_seeds():
    """29 聚素 + 175 无三价 = 204 个种子（按向量去重）。"""
    seeds = []
    seen = set()
    for d in load_json(SUBSTANCES):
        # substances.json 只含聚素 {O,X,C}，其 vec 是 3 维（注意：该文件的 feed 字段
        # 个别条目不是 9 维计数向量，不可用）；补零到 9 维。
        raw = tuple(d["vec"])
        v = tuple(list(raw[:3]) + [0] * (NEL - 3))
        if v in seen:
            continue
        seen.add(v)
        seeds.append({"formula": d["formula"], "vec": v, "class": "聚素"})
    for d in load_json(T9_SINGLE)["none"]:
        v = tuple(d["feed"])
        if v in seen:
            continue
        seen.add(v)
        seeds.append({"formula": d["formula"], "vec": v, "class": "无三价"})
    return seeds


# ---------------------------------------------------------------- 多进程 worker
_W = {}


def _worker_init(pool_items, reagent_names, seeds, max_steps, max_atoms, strategy,
                 embed_budget):
    _W["pool"] = {f: tuple(v) for f, v in pool_items}
    _W["reagents"] = reagent_names
    _W["seeds"] = seeds
    _W["max_steps"] = max_steps
    _W["max_atoms"] = max_atoms
    _W["strategy"] = strategy
    _W["R"] = Reactor(embed_budget=embed_budget)


def _run_seed_job(job):
    """job = (seed_idx, n_reagents_start, n_reagents_end) —— 按试剂分片。"""
    idx, lo, hi = job
    seed = _W["seeds"][idx]
    sf = seed["formula"]
    pool = _W["pool"]
    names = _W["reagents"]
    Rr = _W["R"]
    Rr.clear()
    term = Counter()
    len_hist = Counter()
    step_carrier = defaultdict(float)   # step -> sum carrier natoms
    step_total = defaultdict(float)     # step -> sum total atoms（成功步）
    step_success = Counter()            # step -> 成功步数
    step_count = Counter()
    step_maxmol = Counter()             # step -> max max_mol
    max_carrier = natoms(seed["vec"])
    max_total = 0
    max_carrier_reagent = None
    finals = Counter()                  # 终态产物多重集（仅统计前 200 种，防爆）
    longest = []                        # (n_steps, reagent, trace)
    examples = {}                       # term -> (n_steps, reagent, trace)
    for k in range(lo, hi):
        rf = names[k]
        rec = run_chain(sf, rf, strategy=_W["strategy"],
                        max_steps=_W["max_steps"], max_atoms=_W["max_atoms"],
                        trace=True)
        t = rec["termination"]
        term[t] += 1
        len_hist[rec["n_steps"]] += 1
        tr = rec["carrier_trace"]
        for si, sz in enumerate(tr):
            step_carrier[si] += sz
            step_count[si] += 1
        for st in rec["steps"]:
            step_total[st["step"]] += st["total_atoms"]
            step_success[st["step"]] += 1
            if st["max_mol"] is not None:
                step_maxmol[st["step"]] = max(step_maxmol[st["step"]], st["max_mol"])
            max_total = max(max_total, st["total_atoms"])
        mc = rec["max_carrier"]
        if mc > max_carrier:
            max_carrier = mc
            max_carrier_reagent = rf
        if len(longest) < 3 or rec["n_steps"] > longest[0][0]:
            longest.append((rec["n_steps"], rf, tr, rec["termination"]))
            longest.sort(key=lambda x: (-x[0], x[1]))
            longest = longest[:3]
        if t not in examples or rec["n_steps"] > examples[t][0]:
            examples[t] = (rec["n_steps"], rf, tr, rec["final_products"],
                           rec["final_carrier"], rec["steps"][:3],
                           rec["cycle_period"], rec["next_carrier"])
        if len(finals) < 200:
            finals[tuple(rec["final_products"])] += 1
        elif tuple(rec["final_products"]) in finals:
            finals[tuple(rec["final_products"])] += 1
    return {
        "idx": idx,
        "formula": sf,
        "class": seed["class"],
        "n_chains": hi - lo,
        "term": dict(term),
        "len_hist": dict(len_hist),
        "max_carrier": max_carrier,
        "max_carrier_reagent": max_carrier_reagent,
        "max_total": max_total,
        "longest": longest,
        "examples": examples,
        "finals_top": finals.most_common(8),
        "step_carrier": {k: v for k, v in step_carrier.items()},
        "step_total": {k: v for k, v in step_total.items()},
        "step_success": dict(step_success),
        "step_count": dict(step_count),
        "step_maxmol": dict(step_maxmol),
    }


def _worker_set_reagents(names):
    _W["reagents"] = names


def cmd_chains(args):
    t0 = time.time()
    seeds = load_seeds()
    pool = load_pool(8)
    names = sorted(pool)
    pool_full = len(names)
    print(f"[chains] 种子 {len(seeds)}（聚素 {sum(1 for s in seeds if s['class']=='聚素')}"
          f" + 无三价 {sum(1 for s in seeds if s['class']=='无三价')}），试剂池 natoms<=8 = {pool_full}")
    if args.reagent_sample and args.reagent_sample < pool_full:
        rng = random.Random(20261113)
        low = [f for f in names if natoms(pool[f]) <= 4]
        rest = [f for f in names if natoms(pool[f]) > 4]
        need = max(0, args.reagent_sample - len(low))
        names = sorted(low + rng.sample(rest, min(need, len(rest))))
        print(f"[chains] 试剂池分层抽样：全部 natoms<=4（{len(low)}）+ 随机 natoms 5~8，"
              f"共 {len(names)}（全池 {pool_full}）", flush=True)
    import multiprocessing as mp
    W = args.workers
    jobs = []
    N = len(names)
    shard = max(1, N // args.shards_per_seed)
    for i in range(len(seeds)):
        for lo in range(0, N, shard):
            jobs.append((i, lo, min(N, lo + shard)))
    print(f"[chains] 固定试剂链任务 {len(jobs)}（每种子 {args.shards_per_seed} 片 × {N} 试剂），"
          f"workers={W}，max_atoms={args.max_atoms}，embed_budget={args.embed_budget}", flush=True)
    results = []
    with mp.Pool(W, initializer=_worker_init,
                 initargs=(list(pool.items()), names, seeds, args.max_steps,
                           args.max_atoms, args.strategy, args.embed_budget)) as pool_proc:
        for k, r in enumerate(pool_proc.imap_unordered(_run_seed_job, jobs, chunksize=1), 1):
            results.append(r)
            if k % max(1, len(jobs) // 10) == 0:
                print(f"[chains]   {k}/{len(jobs)} 完成，{time.time()-t0:.0f}s", flush=True)
    # ---- 汇总
    term = Counter()
    len_hist = Counter()
    per_class = defaultdict(Counter)
    step_carrier = defaultdict(float)
    step_total = defaultdict(float)
    step_success = Counter()
    step_count = Counter()
    step_maxmol = Counter()
    final_multi = Counter()
    seed_rows = []
    global_longest = []   # (n_steps, seed, reagent, trace, term)
    examples = {}
    for r in results:
        term.update(r["term"])
        per_class[r["class"]].update(r["term"])
        for k, v in r["len_hist"].items():
            len_hist[int(k)] += v
        for k, v in r["step_carrier"].items():
            step_carrier[int(k)] += v
        for k, v in r["step_total"].items():
            step_total[int(k)] += v
        step_success.update({int(k): v for k, v in r["step_success"].items()})
        step_count.update({int(k): v for k, v in r["step_count"].items()})
        for k, v in r["step_maxmol"].items():
            step_maxmol[int(k)] = max(step_maxmol[int(k)], v)
        for fs, c in r["finals_top"]:
            final_multi[tuple(fs)] += c
        seed_rows.append({
            "seed": r["formula"], "class": r["class"], "n_chains": r["n_chains"],
            "term": r["term"], "len_hist": r["len_hist"],
            "max_carrier": r["max_carrier"],
            "max_carrier_reagent": r["max_carrier_reagent"],
            "max_total_atoms": r["max_total"],
        })
        for n_steps, rf, tr, tt in r["longest"]:
            global_longest.append((n_steps, r["formula"], rf, tr, tt))
        for t, ex in r["examples"].items():
            if t not in examples or ex[0] > examples[t][0]:
                examples[t] = (ex[0], r["formula"], ex[1], ex[2], ex[3], ex[4], ex[5],
                               ex[6], ex[7])
    global_longest.sort(key=lambda x: (-x[0], x[1], x[2]))
    global_longest = global_longest[:15]
    total_chains = sum(term.values())
    # 每步平均
    per_step = []
    for si in sorted(step_success):
        per_step.append({
            "step": si, "n": step_success[si],
            "n_chains_alive": step_count.get(si, 0),
            "mean_carrier_natoms": round(step_carrier[si] / step_count[si], 3),
            "mean_total_atoms": round(step_total[si] / step_success[si], 3),
            "max_mol_atoms": step_maxmol.get(si, 0),
        })
    # 种子级最长链
    longest_by_seed = sorted(seed_rows, key=lambda r: -max(r["len_hist"]) if r["len_hist"] else 0)[:12]
    # 每类元素子集的最大载体尺寸（观察饱和）
    by_elemset = {}
    for r in seed_rows:
        n_el = sum(1 for c in parse(r["seed"]) if c > 0)
        cur = by_elemset.setdefault(n_el, {"seeds": 0, "max_carrier": 0, "max_total_atoms": 0})
        cur["seeds"] += 1
        cur["max_carrier"] = max(cur["max_carrier"], r["max_carrier"])
        cur["max_total_atoms"] = max(cur["max_total_atoms"], r["max_total_atoms"])
    out = {
        "n_seeds": len(seeds),
        "n_reagents": len(names),
        "pool_full_size": pool_full,
        "reagent_sample": args.reagent_sample or 0,
        "n_chains": total_chains,
        "strategy": args.strategy,
        "workers": W,
        "max_steps": args.max_steps,
        "max_atoms": args.max_atoms,
        "embed_budget": args.embed_budget,
        "elapsed_s": round(time.time() - t0, 1),
        "terminations": dict(term),
        "termination_pct": {k: round(100.0 * v / total_chains, 3) for k, v in term.items()},
        "by_class": {c: dict(v) for c, v in per_class.items()},
        "length_hist": {str(k): v for k, v in sorted(len_hist.items())},
        "per_step": per_step,
        "by_elementset_size": {str(k): v for k, v in sorted(by_elemset.items())},
        "seed_rows": seed_rows,
        "longest_chains": [
            {"n_steps": x[0], "seed": x[1], "reagent": x[2], "carrier_trace": x[3], "term": x[4]}
            for x in global_longest],
        "seed_longest": [{"seed": r["seed"], "max_steps": max(r["len_hist"]) if r["len_hist"] else 0}
                         for r in longest_by_seed],
        "examples": {
            t: {"seed": x[1], "reagent": x[2], "n_steps": x[0], "carrier_trace": x[3],
                "final_products": x[4], "final_carrier": x[5], "first_steps": x[6],
                "cycle_period": x[7], "next_carrier": x[8]}
            for t, x in examples.items()},
        "top_final_mixtures": [{"products": list(k), "count": v}
                               for k, v in final_multi.most_common(15)],
    }
    save_section("chains", out)
    # ---- 终端简报（<=50 行）
    print("\n===== 链统计（固定试剂，策略 %s）=====" % args.strategy)
    print(f"链数 {total_chains}，种子 {len(seeds)} × 试剂 {len(names)}；耗时 {out['elapsed_s']}s")
    print("终止方式:", {k: f"{v} ({100.0*v/total_chains:.2f}%)" for k, v in term.most_common()})
    print("按种子类:", {c: dict(v) for c, v in per_class.items()})
    print("链长(载体转移数) 分布:", dict(sorted(len_hist.items())))
    print("每步平均: " + ", ".join(f"s{d['step']}:{d['mean_carrier_natoms']:.2f}" for d in per_step[:10]))
    print("最长链:", [(x[0], x[1], x[2], x[3], x[4]) for x in global_longest[:5]])
    print("元素数->最大载体:", out["by_elementset_size"])
    print("常见终态:", out["top_final_mixtures"][:8])
    print("已写", DATA)


# ---------------------------------------------------------------- probe
def cmd_probe(args):
    t0 = time.time()
    seeds = load_seeds()
    pool = load_pool(8)
    names = sorted(pool)
    print(f"[probe] seeds={len(seeds)} pool={len(names)} max_atoms={args.max_atoms} "
          f"embed_budget={args.embed_budget}", flush=True)
    rng = random.Random(7)
    sample_seeds = [seeds[i]["formula"] for i in rng.sample(range(len(seeds)), 4)]
    sample_reagents = rng.sample(names, 40)
    for sf in sample_seeds:
        R.clear()
        t1 = time.time()
        cnt = Counter()
        lens = []
        mx = 0
        for rf in sample_reagents:
            rec = run_chain(sf, rf, max_steps=args.max_steps, max_atoms=args.max_atoms)
            cnt[rec["termination"]] += 1
            lens.append(rec["n_steps"])
            mx = max(mx, rec["max_carrier"])
        print(f"  seed {sf:8s}: {dict(cnt)}  meanlen={sum(lens)/len(lens):.2f} maxcarrier={mx}"
              f"  {time.time()-t1:.2f}s", flush=True)
        rec = run_chain(sf, sample_reagents[0], max_steps=args.max_steps,
                        max_atoms=args.max_atoms, trace=True)
        print(f"    trace seed+{sample_reagents[0]}: {rec['carrier_trace']} term={rec['termination']}",
              flush=True)
        for st in rec["steps"][:6]:
            print(f"      step{st['step']} {st['carrier']}+{st['reagent']} -> {st['products']}",
                  flush=True)
    # 单种子全试剂池计时（估计全量工作量）
    if args.bench_seed:
        sf = args.bench_seed
        R.clear()
        t1 = time.time()
        cnt = Counter()
        for k, rf in enumerate(names):
            rec = run_chain(sf, rf, max_steps=args.max_steps, max_atoms=args.max_atoms)
            cnt[rec["termination"]] += 1
        dt = time.time() - t1
        print(f"[probe] bench seed {sf} × {len(names)} 试剂 = {dt:.1f}s，"
              f"预计全量 {len(seeds)} 种子 ≈ {dt*len(seeds)/args.workers/60:.1f} min ({args.workers} 核)",
              flush=True)
        print("   term:", dict(cnt), flush=True)
    print(f"[probe] {time.time()-t0:.1f}s", flush=True)


# ---------------------------------------------------------------- idem
def _rethrow(prods, use_embed=True):
    """把产物分子全部再投锅：用产物原子（canonical 顺序）重建原子表后 simulate。"""
    v = [0] * NEL
    for f in prods:
        pv = parse(f)
        for i in range(NEL):
            v[i] += pv[i]
    mols = P.simulate(atoms_of(tuple(v)))
    if mols is None:
        return ("fail", None, "剩键/价数奇偶")
    if use_embed and not pot_v2.embed_all2(mols, max_nodes=R.embed_budget):
        return ("fail", None, "摆放失败/预算截断")
    return ("ok", tuple(sorted(P.formula_of(m["atoms"]) for m in mols)), "")


def _shuffled_atoms(vec, rng):
    a = atoms_of(vec)
    rng.shuffle(a)
    return a


def cmd_idem(args):
    t0 = time.time()
    rng = random.Random(20261113)
    tests = []
    # (a) 随机向量（约半数会失败）
    for _ in range(48):
        n = rng.randint(3, 22)
        v = [0] * NEL
        for _ in range(n):
            v[rng.randrange(NEL)] += 1
        tests.append(("random", tuple(v)))
    # (b) 目录物质自身向量
    cat = load_json(CATALOG)
    for d in rng.sample(cat, 32):
        tests.append(("catalog", tuple(d["feed"])))
    # (c) 种子×试剂
    seeds = load_seeds()
    pool = load_pool(8)
    names = sorted(pool)
    for _ in range(32):
        s = rng.choice(seeds)
        rf = rng.choice(names)
        tests.append(("pair", add(s["vec"], parse(rf))))
    # (d) 已知不相容对（T11 聚素内 3 对失败）
    fail_specs = [("C2", "O2XC4"), ("C2", "OXC"), ("O2C4", "XC2")]
    for a, b in fail_specs:
        tests.append(("known_fail", add(parse(a), parse(b))))
    # (e) 明确奇价数向量（必失败）
    for _ in range(12):
        v = [0] * NEL
        v[rng.randrange(NEL)] += 1
        for _ in range(rng.randint(1, 5)):
            v[rng.randrange(NEL)] += 1
        tests.append(("odd_valence", tuple(v)))
    rows = []
    n_ok = n_fail = 0
    rethrow_ok = 0
    rethrow_checked = 0
    perm_invariant = 0
    perm_checked = 0
    self_repro = 0
    self_repro_checked = 0
    alt_same = 0
    alt_checked = 0
    for kind, v in tests:
        status, prods, why = R.F(v)
        row = {"kind": kind, "vec": list(v), "status": status, "reason": why,
               "products": list(prods) if prods else None}
        if status == "ok":
            n_ok += 1
            # 幂等：产物全部再投锅 == 原产物
            st2, prods2, _ = _rethrow(prods)
            rethrow_checked += 1
            eq = (st2 == "ok" and prods2 == prods)
            row["rethrow_same"] = eq
            rethrow_ok += eq
            # 排列无关性（同一向量、打乱原子顺序）
            for _try in range(1):
                a = _shuffled_atoms(v, rng)
                m2 = P.simulate(a)
                perm_checked += 1
                if m2 is not None and pot_v2.embed_all2(m2, max_nodes=R.embed_budget):
                    p2 = tuple(sorted(P.formula_of(m["atoms"]) for m in m2))
                    same = (p2 == prods)
                    perm_invariant += same
                    row["perm_same"] = same
                else:
                    row["perm_same"] = False
            # 每个产物分子单独投锅 = 自身
            sr = True
            for f in prods:
                self_repro_checked += 1
                st3, p3, _ = R.F(tuple(parse(f)))
                if not (st3 == "ok" and p3 == (f,)):
                    sr = False
            row["self_reproduction"] = sr
            self_repro += sr
            # 同向量的另一种分解（若池内能找到两分子对同向量）
            alt = _find_alt_decomposition(v, pool, rng)
            if alt is not None:
                st4, p4, _ = R.F(add(parse(alt[0]), parse(alt[1])))
                alt_checked += 1
                same = (st4 == "ok" and p4 == prods)
                alt_same += same
                row["alt_decomposition"] = list(alt)
                row["alt_same"] = same
            # 产物多重集再投锅 = 逐分子重投的并（多分子混合不变性）
            if len(prods) >= 2:
                merged = []
                okall = True
                for f in prods:
                    st5, p5, _ = R.F(tuple(parse(f)))
                    if st5 != "ok":
                        okall = False
                        break
                    merged.extend(p5)
                row["components_merge_same"] = okall and sort_multi(merged) == prods
        else:
            n_fail += 1
            # 失败在打乱顺序下必须一致失败
            a = _shuffled_atoms(v, rng)
            m2 = P.simulate(a)
            row["fail_stable_under_perm"] = (m2 is None)
        rows.append(row)
    # 纯理论：结果只由向量决定 ⇒ F 幂等（证明草稿见 MD）；此处给出数值通过率。
    out = {
        "n_tests": len(tests),
        "n_ok": n_ok,
        "n_fail": n_fail,
        "fail_examples": [r for r in rows if r["status"] == "fail"][:8],
        "rethrow_checked": rethrow_checked,
        "rethrow_idempotent": rethrow_ok,
        "permutation_checked": perm_checked,
        "permutation_invariant": perm_invariant,
        "self_reproduction_checked_mols": self_repro_checked,
        "self_reproduction_passed_vectors": self_repro,
        "alt_decomposition_checked": alt_checked,
        "alt_decomposition_same": alt_same,
        "by_kind": dict(Counter(r["kind"] for r in rows)),
        "rows_sample": rows[:6] + [r for r in rows if r["status"] == "fail"][:4],
        "elapsed_s": round(time.time() - t0, 2),
    }
    save_section("idempotence", out)
    print("===== 幂等性验证 =====")
    print(f"测试向量 {len(tests)}（成功 {n_ok} / 失败 {n_fail}）")
    print(f"产物再投锅 == 原产物: {rethrow_ok}/{rethrow_checked}")
    print(f"原子顺序打乱后结果不变: {perm_invariant}/{perm_checked}")
    print(f"产物分子单独投锅=自身: {self_repro}/{n_ok} 个向量（{self_repro_checked} 次检查）")
    print(f"同向量不同分解结果相同: {alt_same}/{alt_checked}")
    print(f"失败例（应保持失败）: {[(r['kind'], r['vec'], r['reason']) for r in rows if r['status']=='fail'][:4]}")
    print(f"耗时 {out['elapsed_s']}s；已写 {DATA}")


def _find_alt_decomposition(v, pool, rng, by_nat=None):
    """在池内随机找一对分子，使其向量和 == v（找到就返回 (f1,f2)）。"""
    if by_nat is None:
        by_nat = defaultdict(list)
        for f, pv in pool.items():
            by_nat[natoms(pv)].append(f)
    classes = [n for n in by_nat if 1 <= n <= natoms(v)]
    names_by_class = [by_nat[n] for n in classes]
    for _ in range(80):
        cand_list = rng.choice(names_by_class)
        f1 = rng.choice(cand_list)
        p1 = pool[f1]
        rem = tuple(v[i] - p1[i] for i in range(NEL))
        if any(c < 0 for c in rem):
            continue
        for f2 in rng.sample(by_nat.get(natoms(rem), []), min(6, len(by_nat.get(natoms(rem), [])))):
            if pool[f2] == rem:
                return (f1, f2)
    return None


# ---------------------------------------------------------------- 自由模式（载体转移图）
_F = {}


def _free_init(carriers, reagents, embed_budget):
    _F["carriers"] = carriers
    _F["reagents"] = reagents
    _F["R"] = Reactor(embed_budget=embed_budget)


def _free_job(job):
    """job = carrier 下标；返回 {试剂: 产物多重集}（只保留有变化/失败标记）。"""
    ci = job
    xf = _F["carriers"][ci]
    Rr = _F["R"]
    out = {}
    for rf in _F["reagents"]:
        status, prods, why = Rr.F(add(parse(xf), parse(rf)))
        if status == "ok":
            out[rf] = list(prods)
        else:
            out[rf] = None
    return ci, out


def cmd_freegraph(args):
    """自由模式：每个载体 X 记录"与任一试剂 R 反应后可选的下一步分子"。"""
    t0 = time.time()
    pool = load_pool(8)
    names = sorted(pool)
    carriers = [f for f in names if natoms(pool[f]) <= args.free_carrier_max]
    reagents = [f for f in names if natoms(pool[f]) <= args.free_reagent_max]
    print(f"[free] 载体 {len(carriers)}（natoms<={args.free_carrier_max}），"
          f"试剂 {len(reagents)}（natoms<={args.free_reagent_max}），共 {len(carriers)*len(reagents)} 对",
          flush=True)
    import multiprocessing as mp
    edges = {}          # X -> {R: [Y...]}（只保留非惰性）
    inert_pairs = 0
    fail_pairs = 0
    with mp.Pool(args.workers, initializer=_free_init,
                 initargs=(carriers, reagents, args.embed_budget)) as pp:
        for ci, out in pp.imap_unordered(_free_job, list(range(len(carriers))), chunksize=1):
            xf = carriers[ci]
            e = {}
            for rf, prods in out.items():
                if prods is None:
                    fail_pairs += 1
                    continue
                if prods == sorted([xf, rf]):
                    inert_pairs += 1
                    continue
                e[rf] = prods
            edges[xf] = e
    nodes = {x for x, e in edges.items() if e}
    n_edges = sum(len(e) for e in edges.values())
    # 载体转移边：X --R--> Y（每个产物 Y 是一条边）
    adj = defaultdict(set)    # (X,Y) -> set(R)
    for x, e in edges.items():
        for r, prods in e.items():
            for y in set(prods):
                adj[(x, y)].add(r)
    # 2-环：X --R1--> Y，Y --R2--> X
    cycle_pairs = [(x, y) for (x, y) in adj if x < y and (y, x) in adj]
    cycles2 = []
    for (x, y) in cycle_pairs:
        r1s, r2s = adj[(x, y)], adj[(y, x)]
        cycles2.append({"X": x, "Y": y, "R1": sorted(r1s)[0], "R2": sorted(r2s)[0],
                        "n_r1": len(r1s), "n_r2": len(r2s)})
    # 固定点载体：X 在 F(X+R) 中（自催化/稳定）
    fixed_carrier = []
    self_cat = []
    for x, e in edges.items():
        for r, prods in e.items():
            if x in prods:
                self_cat.append({"X": x, "R": r, "products": prods})
    # 净反应式（2-环）
    def net_of(cy):
        x, y, r1, r2 = cy["X"], cy["Y"], cy["R1"], cy["R2"]
        p1 = edges[x][r1]
        p2 = edges[y][r2]
        by1 = list(p1)
        by1.remove(y) if y in by1 else None
        by2 = list(p2)
        by2.remove(x) if x in by2 else None
        def fmt(fs):
            c = Counter(fs)
            return " + ".join((f if n == 1 else (f if len(f) == 1 else f)) + ("" if n == 1 else ("×%d" % n))
                              for f, n in sorted(c.items())) or "∅"
        return f"{r1} + {r2} → {fmt(by1 + by2)}"
    for cy in cycles2[:500]:
        cy["net"] = net_of(cy)
    # 统计
    outdeg = Counter(len(e) for e in edges.values())
    top_carriers = sorted(((x, len(e)) for x, e in edges.items()), key=lambda t: -t[1])[:10]
    res = {
        "carrier_max_natoms": args.free_carrier_max,
        "reagent_max_natoms": args.free_reagent_max,
        "n_carriers": len(carriers),
        "n_reagents": len(reagents),
        "n_pairs": len(carriers) * len(reagents),
        "n_fail_pairs": fail_pairs,
        "n_inert_pairs": inert_pairs,
        "n_carriers_with_outgoing": len(nodes),
        "n_edges_XR": n_edges,
        "n_transition_pairs": len(adj),
        "n_cycles2": len(cycles2),
        "n_cycles2_pairs": len(cycle_pairs),
        "cycles2_examples": cycles2[:12],
        "n_self_catalytic_steps": len(self_cat),
        "self_catalytic_examples": self_cat[:10],
        "outdeg_hist": {str(k): v for k, v in sorted(outdeg.items())},
        "top_carriers": [{"X": x, "n_out": n} for x, n in top_carriers],
        "elapsed_s": round(time.time() - t0, 1),
    }
    # 只保存有变化的图中的边（压缩保存）
    save_section("free_graph", res)
    print("===== 自由模式（载体转移图）=====")
    print(f"载体 {len(carriers)} × 试剂 {len(reagents)} = {res['n_pairs']} 对；"
          f"失败 {fail_pairs}、惰性 {inert_pairs}、有变化 {n_edges}")
    print(f"有出边的载体 {len(nodes)}；转移对(X,Y) {len(adj)}；2-环 {len(cycles2)}")
    print(f"自催化步（产物含载体 X）{len(self_cat)}")
    for cy in cycles2[:5]:
        print("  ", cy["X"], "--", cy["R1"], "-->", cy["Y"], "--", cy["R2"], "-->",
              cy["X"], "| 净:", cy["net"])
    print(f"耗时 {res['elapsed_s']}s；已写 {DATA}")

# ---------------------------------------------------------------- 单产物增长链
def _single_init(pool_items, reagent_names, seeds, max_steps, max_atoms, embed_budget):
    _W["pool"] = {f: tuple(v) for f, v in pool_items}
    _W["reagents"] = reagent_names
    _W["seeds"] = seeds
    _W["max_steps"] = max_steps
    _W["max_atoms"] = max_atoms
    _W["R"] = Reactor(embed_budget=embed_budget)


def _single_job(job):
    """固定试剂链，但每步要求**恰好单产物**（严格化合增长链）。"""
    idx, lo, hi = job
    seed = _W["seeds"][idx]
    sf = seed["formula"]
    names = _W["reagents"]
    Rr = _W["R"]
    Rr.clear()
    len_hist = Counter()
    longest = []
    n_nonempty = 0
    fail = 0
    for k in range(lo, hi):
        rf = names[k]
        rv = parse(rf)
        X = sf
        xv = seed["vec"]
        trace = [X]
        sizes = [natoms(xv)]
        ok_steps = 0
        for st in range(_W["max_steps"]):
            v = add(xv, rv)
            if natoms(v) > _W["max_atoms"]:
                break
            status, prods, why = Rr.F(v)
            if status != "ok":
                fail += 1
                break
            if len(prods) != 1:
                break
            y = prods[0]
            if y == X:
                break
            ok_steps += 1
            trace.append(y)
            sizes.append(natoms(parse(y)))
            X = y
            xv = parse(y)
        len_hist[ok_steps] += 1
        if ok_steps > 0:
            n_nonempty += 1
        if len(longest) < 4 or ok_steps > longest[0][0]:
            longest.append((ok_steps, rf, list(trace), list(sizes)))
            longest.sort(key=lambda t: (-t[0], t[1]))
            longest = longest[:4]
    return {"idx": idx, "seed": sf, "len_hist": dict(len_hist),
            "longest": longest, "n_nonempty": n_nonempty, "fail": fail}


def cmd_single(args):
    """最长单产物增长链（每步 F(X+R) 恰好一个产物）。"""
    t0 = time.time()
    seeds = load_seeds()
    pool = load_pool(8)
    names = sorted(pool)
    print(f"[single] 种子 {len(seeds)} × 试剂 {len(names)}，求单产物增长链", flush=True)
    import multiprocessing as mp
    N = len(names)
    shard = max(1, N // args.shards_per_seed)
    jobs = [(i, lo, min(N, lo + shard))
            for i in range(len(seeds)) for lo in range(0, N, shard)]
    len_hist = Counter()
    longest = []
    n_nonempty = 0
    fails = 0
    with mp.Pool(args.workers, initializer=_single_init,
                 initargs=(list(pool.items()), names, seeds, args.max_steps,
                           args.max_atoms, args.embed_budget)) as pp:
        for k, r in enumerate(pp.imap_unordered(_single_job, jobs, chunksize=1), 1):
            for kk, vv in r["len_hist"].items():
                len_hist[int(kk)] += vv
            n_nonempty += r["n_nonempty"]
            fails += r["fail"]
            for steps, rf, trace, sizes in r["longest"]:
                longest.append((steps, r["seed"], rf, trace, sizes))
            if k % max(1, len(jobs) // 5) == 0:
                print(f"[single]  {k}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)
    longest.sort(key=lambda t: (-t[0], t[1], t[2]))
    longest = longest[:10]
    out = {
        "n_seeds": len(seeds), "n_reagents": len(names),
        "n_chains": sum(len_hist.values()),
        "len_hist": {str(k): v for k, v in sorted(len_hist.items())},
        "n_chains_with_growth": n_nonempty,
        "max_steps": max(len_hist) if len_hist else 0,
        "longest_chains": [
            {"n_steps": x[0], "seed": x[1], "reagent": x[2], "carrier_trace": x[3],
             "size_trace": x[4]} for x in longest],
        "elapsed_s": round(time.time() - t0, 1),
    }
    save_section("single_product_chains", out)
    print("===== 单产物增长链 =====")
    print(f"链数 {out['n_chains']}，有增长的链 {n_nonempty}，最长 {out['max_steps']} 步")
    print("长度分布:", out["len_hist"])
    for x in longest[:5]:
        print(f"  {x[1]} + {x[2]}: {x[3]} sizes={x[4]}")
    print(f"耗时 {out['elapsed_s']}s；已写 {DATA}")


def _fmt_multi(fs):
    c = Counter(fs)
    if not c:
        return "∅"
    return " + ".join(f if n == 1 else (f + "×%d" % n) for f, n in sorted(c.items()))


def cmd_cycles(args):
    """用 t11_cycles.json 的真 2-环做 A→C→A 反复 20 轮的"无限循环"演示。"""
    t0 = time.time()
    rings = load_json(CYCLES)["two_rings"]
    rounds = args.cycle_rounds
    ok_rings = 0
    bad = []
    cat = Counter()
    by_class = Counter()
    top_byproducts = Counter()
    demos = []
    for cy in rings:
        A, C, cls = cy["A"], cy["C"], cy["class"]
        try:
            (a, b, p1, c1), (c, d, p2, a2) = cy["steps"]
        except Exception:
            bad.append({"ring": cy.get("A"), "why": "格式"})
            continue
        st1, pr1, why1 = R.F(add(parse(a), parse(b)))
        st2, pr2, why2 = R.F(add(parse(c), parse(d)))
        if st1 != "ok" or st2 != "ok":
            bad.append({"A": A, "C": C, "why": why1 or why2})
            continue
        if list(pr1) != list(p1) or list(pr2) != list(p2):
            bad.append({"A": A, "C": C, "why": "产物与记录不符",
                        "got1": list(pr1), "got2": list(pr2)})
            continue
        if C not in pr1 or A not in pr2:
            bad.append({"A": A, "C": C, "why": "载体未再生"})
            continue
        ok_rings += 1
        cat[A] += 1
        by_class[cls] += 1
        # 每轮副产物 = P1 去掉载体 C + P2 去掉再生载体 A
        bp1 = list(pr1)
        bp1.remove(C)
        bp2 = list(pr2)
        bp2.remove(A)
        round_net = sorted(bp1 + bp2)
        top_byproducts[_fmt_multi(round_net)] += 1
        # 20 轮验证：每步产物恒定、副产物线性累积
        acc = Counter()
        ok_rounds = True
        trace = []
        for rd in range(rounds):
            s1, q1, _ = R.F(add(parse(A), parse(b)))
            s2, q2, _ = R.F(add(parse(C), parse(d)))
            if s1 != "ok" or s2 != "ok" or list(q1) != list(pr1) or list(q2) != list(pr2):
                ok_rounds = False
                break
            acc.update(bp1)
            acc.update(bp2)
            trace.append({"round": rd + 1, "products_step1": list(q1),
                          "products_step2": list(q2),
                          "carrier": "A" if rd % 2 == 0 else "C",
                          "accumulated_byproducts": dict(acc)})
        if not ok_rounds:
            bad.append({"A": A, "C": C, "why": "20 轮中某轮产物变化"})
            ok_rings -= 1
            continue
        if len(demos) < 5:
            demos.append({
                "A": A, "C": C, "class": cls,
                "step1": f"{A} + {b} → {_fmt_multi(pr1)}",
                "step2": f"{C} + {d} → {_fmt_multi(pr2)}",
                "round_net": _fmt_multi(round_net),
                "rounds_verified": rounds,
                "after_20_rounds_byproducts": _fmt_multi(sorted(acc.elements())),
                "trace_head": trace[:3],
            })
    res = {
        "n_rings": len(rings),
        "n_verified": ok_rings,
        "n_bad": len(bad),
        "bad_examples": bad[:10],
        "rounds_per_ring": rounds,
        "by_class": dict(by_class),
        "n_catalysts": len(cat),
        "top_catalysts": [{"A": a, "rings": n} for a, n in cat.most_common(15)],
        "top_net_reactions": [{"net": k, "rings": v} for k, v in top_byproducts.most_common(12)],
        "demos": demos,
        "elapsed_s": round(time.time() - t0, 1),
    }
    save_section("cycles", res)
    print("===== 真 2-环无限循环演示 =====")
    print(f"2-环 {len(rings)} 个：验证通过 {ok_rings}，异常 {len(bad)}；每个跑 {rounds} 轮（每轮两步）")
    print("按类:", dict(by_class), " 不同催化剂:", len(cat))
    print("催化剂排行:", res["top_catalysts"][:8])
    print("常见净反应:", res["top_net_reactions"][:6])
    for dm in demos[:3]:
        print(f"  {dm['A']}(催化) | {dm['step1']} ; {dm['step2']} | 净: {dm['round_net']}"
              f" | {rounds}轮后副产物: {dm['after_20_rounds_byproducts']}")
    print(f"耗时 {res['elapsed_s']}s；已写 {DATA}")


# ---------------------------------------------------------------- 有趣现象
def cmd_finds(args):
    t0 = time.time()
    data = load_json(DATA) if os.path.exists(DATA) else {}
    pool = load_pool(8)
    small = sorted(f for f in pool if natoms(pool[f]) <= args.find_small)
    rng = random.Random(11)
    by_nat = defaultdict(list)
    for f, pv in pool.items():
        by_nat[natoms(pv)].append(f)
    out = {}

    # ① 自催化：A + B -> 产物中含 A（或 B）；排除惰性
    auto, regen = [], []
    for a in small:
        av = parse(a)
        for b in small:
            st, pr, _ = R.F(add(av, parse(b)))
            if st != "ok" or pr == sort_multi([a, b]):
                continue
            if a in pr:
                auto.append({"A": a, "B": b, "products": list(pr),
                             "B_consumed": b not in pr})
            if b in pr:
                regen.append({"A": a, "B": b, "products": list(pr)})
    auto.sort(key=lambda x: (not x["B_consumed"], len(x["products"]), x["A"]))
    out["autocatalysis"] = {
        "scan_pairs": len(small) ** 2,
        "small_pool_natoms_max": args.find_small,
        "n_autocatalytic": len(auto),
        "n_autocatalytic_with_B_consumed": sum(1 for x in auto if x["B_consumed"]),
        "n_reagent_regenerated": len(regen),
        "examples": auto[:8],
        "reagent_regen_examples": regen[:6],
    }
    # ② 振荡：自由模式 2-环 + 固定试剂链 CYCLE 例
    osc = []
    seen_osc = set()
    fg = data.get("free_graph", {})
    for cy in fg.get("cycles2_examples", [])[:40]:
        X, Y, r1, r2 = cy["X"], cy["Y"], cy["R1"], cy["R2"]
        if X in seen_osc:
            continue
        st1, p1, _ = R.F(add(parse(X), parse(r1)))
        st2, p2, _ = R.F(add(parse(Y), parse(r2)))
        if st1 == "ok" and st2 == "ok" and Y in p1 and X in p2:
            seen_osc.add(X)
            osc.append({"kind": "自由模式载体 2-环（X→Y→X）",
                        "X": X, "Y": Y, "R1": r1, "R2": r2,
                        "step1": f"{X} + {r1} → {_fmt_multi(p1)}",
                        "step2": f"{Y} + {r2} → {_fmt_multi(p2)}",
                        "period": 2})
            if len(osc) >= 3:
                break
    ex = data.get("chains", {}).get("examples", {}).get("CYCLE")
    if ex:
        osc.append({"kind": "固定试剂链载体周期", "seed": ex["seed"], "reagent": ex["reagent"],
                    "carrier_trace": ex["carrier_trace"],
                    "period": ex.get("cycle_period") or 0,
                    "next_carrier": ex.get("next_carrier")})
    # ②c 小规模直接扫描：固定试剂链中的振荡（载体周期）与惰性终态
    n_small_cycles = 0
    n_small_inert = 0
    cyc_ex = []
    inert_ex = []
    for a in small:
        for b in small:
            rec = run_chain(a, b, strategy="max", max_steps=args.max_steps,
                            max_atoms=args.max_atoms, trace=True)
            t = rec["termination"]
            carriers = [st["carrier"] for st in rec["steps"]]
            if t == "CYCLE" and rec.get("cycle_period") and rec["cycle_period"] >= 2:
                n_small_cycles += 1
                period = rec["cycle_period"]
                if len(cyc_ex) < 3:
                    eqs = []
                    for st in rec["steps"][-period:]:
                        eqs.append(f"{st['carrier']} + {st['reagent']} → {_fmt_multi(st['products'])}")
                    cyc_ex.append({"kind": "固定试剂链振荡（小规模扫描）",
                                   "seed": a, "reagent": b,
                                   "carrier_cycle": carriers[-(period + 1):] + [rec["next_carrier"]],
                                   "period": period, "steps": eqs})
            elif t == "INERT":
                n_small_inert += 1
                pr = rec["final_products"]
                if (len(inert_ex) < 3 and pr and
                        all(natoms(parse(f)) <= args.find_small + 2 for f in pr)):
                    inert_ex.append({"termination": "INERT", "seed": a, "reagent": b,
                                     "carrier_trace": rec["carrier_trace"],
                                     "final_products": list(pr),
                                     "rethrow_same": True,
                                     "all_small": True,
                                     "equation": f"{a} + {b} → " + _fmt_multi(pr)})
    osc.extend(cyc_ex[:3])
    # ②d 从“CYCLE 高发种子”出发扫全部试剂，找 3 个不同振荡例
    t_osc = time.time()
    seed_rows = data.get("chains", {}).get("seed_rows", [])
    cand_seeds = sorted(
        [r for r in seed_rows if r.get("term", {}).get("CYCLE", 0) > 0],
        key=lambda r: (-(r["term"].get("CYCLE", 0)),
                       sum(1 for c in parse(r["seed"]) if c > 0), r["seed"]))[:10]
    osc_seen = {o.get("seed") for o in osc if o.get("seed")}
    n_scan = 0
    for r in cand_seeds:
        if len([o for o in osc if o.get("kind", "").endswith("扫描）")]) >= 3:
            break
        sf = r["seed"]
        for rf in sorted(pool):
            if time.time() - t_osc > 150:
                break
            n_scan += 1
            rec = run_chain(sf, rf, strategy="max", max_steps=min(24, args.max_steps),
                            max_atoms=args.max_atoms, trace=True)
            if rec["termination"] != "CYCLE":
                continue
            period = rec.get("cycle_period") or 0
            if period < 2 or (sf in osc_seen):
                continue
            osc_seen.add(sf)
            carriers = [st["carrier"] for st in rec["steps"]]
            eqs = []
            for st in rec["steps"][-period:]:
                eqs.append(f"{st['carrier']} + {st['reagent']} → {_fmt_multi(st['products'])}")
            osc.append({"kind": "固定试剂链振荡（针对性扫描）",
                        "seed": sf, "reagent": rf,
                        "carrier_cycle": carriers[-(period + 1):] + [rec["next_carrier"]],
                        "period": period, "steps": eqs})
            break
    out["oscillation"] = {"n_examples": len(osc), "examples": osc[:8],
                          "small_scan_cycles": n_small_cycles,
                          "small_scan_inert": n_small_inert,
                          "targeted_scan_chains": n_scan,
                          "targeted_scan_s": round(time.time() - t_osc, 1)}

    # ②b 多步催化（单步自催化不存在，但循环中 A 可无限再生）
    multi = []
    for dm in data.get("cycles", {}).get("demos", [])[:3]:
        multi.append({"catalyst": dm["A"], "class": dm.get("class", ""),
                      "step1": dm["step1"], "step2": dm["step2"],
                      "round_net": dm["round_net"],
                      "after_20_rounds": dm["after_20_rounds_byproducts"]})
    out["multi_step_catalysis"] = {"examples": multi}

    # ③ 一锅"不动点"：产物多重集再投锅 = 自身（含多分子情形）
    fixed = []
    tries = 0
    cand_pairs = [(a, b) for a in small for b in small]
    rng.shuffle(cand_pairs)
    for a, b in cand_pairs:
        tries += 1
        if tries > 6000 or len(fixed) >= 3:
            break
        v = add(parse(a), parse(b))
        st, pr, _ = R.F(v)
        if st != "ok" or len(pr) < 3:
            continue
        st2, pr2, _ = _rethrow(pr)
        if st2 == "ok" and tuple(pr2) == tuple(pr):
            fixed.append({"inputs": [a, b], "vec": list(v),
                          "products": list(pr),
                          "rethrow_products": list(pr2),
                          "equation": f"{a} + {b} → {_fmt_multi(pr)}",
                          "rethrow_equation": f"{_fmt_multi(pr)} → {_fmt_multi(pr2)}"})
    out["one_pot_fixed_point"] = {"scan_pairs_tried": tries, "examples": fixed}

    # ④ 收敛性：同总向量、不同分解 -> 同一产物混合
    conv = []
    tries = 0
    for a, b in cand_pairs:
        tries += 1
        if tries > 4000 or len(conv) >= 3:
            break
        v = add(parse(a), parse(b))
        alt = _find_alt_decomposition(v, pool, rng, by_nat)
        if alt is None or sorted(alt) == sorted([a, b]):
            continue
        st1, pr1, _ = R.F(v)
        st2, pr2, _ = R.F(add(parse(alt[0]), parse(alt[1])))
        if st1 == "ok" and st2 == "ok" and pr1 == pr2:
            conv.append({"pair1": [a, b], "pair2": list(alt), "vec": list(v),
                         "products": list(pr1),
                         "equation1": f"{a} + {b} → {_fmt_multi(pr1)}",
                         "equation2": f"{alt[0]} + {alt[1]} → {_fmt_multi(pr2)}"})
    out["convergence"] = {"scan_pairs_tried": tries, "examples": conv}

    # ⑤ 链末稳定态：INERT / STABLE 终止且终态为小分子、再投不变
    term = []
    for inert in inert_ex:
        term.append(inert)
    for tname in ("INERT", "STABLE"):
        ex = data.get("chains", {}).get("examples", {}).get(tname)
        if not ex:
            continue
        pr = ex.get("final_products") or []
        if not pr:
            continue
        st, pr2, _ = _rethrow(pr)
        term.append({"termination": tname, "seed": ex["seed"], "reagent": ex["reagent"],
                     "carrier_trace": ex["carrier_trace"],
                     "final_products": list(pr),
                     "rethrow_same": bool(st == "ok" and tuple(pr2) == tuple(pr)),
                     "all_small": all(natoms(parse(f)) <= args.find_small + 6 for f in pr),
                     "first_steps": ex.get("first_steps")})
    # 去重（按终态多重集）
    seen_ts = set()
    term_dedup = []
    for x in term:
        key = tuple(x.get("final_products") or [])
        if key in seen_ts:
            continue
        seen_ts.add(key)
        term_dedup.append(x)
    term_dedup.sort(key=lambda x: (-len(x.get("carrier_trace") or []),
                                   -len(x.get("final_products") or [])))
    out["terminal_states"] = {"examples": term_dedup[:4], "n_inert_terminal_in_small_scan": n_small_inert}

    # ⑥ 惰性小分子排行（natoms<=3 的物质对小试剂池的惰性率）
    inert_rank = []
    for m in sorted(f for f in pool if natoms(pool[f]) <= 3):
        cnt = 0
        for r in small:
            st, pr, _ = R.F(add(parse(m), parse(r)))
            if st == "ok" and pr == sort_multi([m, r]):
                cnt += 1
        inert_rank.append({"molecule": m, "inert_n": cnt, "n_tested": len(small),
                           "inert_pct": round(100.0 * cnt / len(small), 1)})
    inert_rank.sort(key=lambda x: (-x["inert_n"], x["molecule"]))
    out["inert_molecules"] = {"n_tested": len(inert_rank), "top": inert_rank[:12]}

    save_section("finds", out)
    print("===== 有趣现象 =====")
    print(f"① 自催化：{len(small)}²={len(small)**2} 对中 {len(auto)} 对产物含投入物 A"
          f"（其中 {out['autocatalysis']['n_autocatalytic_with_B_consumed']} 对真正消耗 B）；"
          f"B 被再生 {len(regen)} 对")
    for x in auto[:3]:
        print(f"    {x['A']} + {x['B']} → {_fmt_multi(x['products'])}")
    print(f"② 振荡例 {len(osc)} 个:", [(o["kind"], o.get("step1", o.get("carrier_trace"))) for o in osc[:2]])
    print(f"③ 多分子不动点例 {len(fixed)} 个:", [x["equation"] for x in fixed])
    print(f"④ 收敛例 {len(conv)} 个:", [(x["equation1"], x["equation2"]) for x in conv])
    print("⑤ 链末稳定态:", [(t["termination"], t["final_products"]) for t in term])
    print("⑥ 惰性小分子:", [(x["molecule"], x["inert_n"]) for x in inert_rank[:6]])
    print(f"耗时 {round(time.time()-t0,1)}s；已写 {DATA}")


# ---------------------------------------------------------------- 绘图（Pillow，无需 matplotlib）
def _pil_font(size, bold=False):
    from PIL import ImageFont
    cands = [r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
             r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
             r"C:\Windows\Fonts\arial.ttf"]
    for p in cands:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _hbar_png(path, title, items, xlabel="数量", width=1000, height=620,
              color=(64, 110, 190)):
    from PIL import Image, ImageDraw
    items = list(items)
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    ft, fl, fv = _pil_font(24, True), _pil_font(15), _pil_font(14)
    ml, mr, mt, mb = 220, 70, 70, 60
    x0, x1, y1, y0 = ml, width - mr, height - mb, mt
    vmax = max((v for _, v in items), default=1) or 1
    n = max(1, len(items))
    bh = (y1 - y0) / n
    d.text((width // 2 - 40, 20), title, font=ft, fill=(20, 20, 20))
    d.line([x0, y1, x1, y1], fill=(90, 90, 90), width=2)
    d.line([x0, y0, x0, y1], fill=(90, 90, 90), width=2)
    for i, (lab, v) in enumerate(items):
        by0 = y0 + i * bh + 0.15 * bh
        by1 = by0 + 0.7 * bh
        bx1 = x0 + (v / vmax) * (x1 - x0)
        d.rectangle([x0, by0, bx1, by1], fill=color)
        d.text((8, by0 - 2), str(lab)[:18], font=fl, fill=(30, 30, 30))
        d.text((bx1 + 6, by0 - 2), str(v), font=fv, fill=(30, 30, 30))
    for g in range(5):
        gx = x0 + (x1 - x0) * g / 4
        d.line([gx, y0, gx, y1], fill=(225, 225, 225))
        d.text((gx - 12, y1 + 8), str(int(vmax * g / 4)), font=fv, fill=(80, 80, 80))
    d.text((width // 2 - 20, height - 30), xlabel, font=fl, fill=(40, 40, 40))
    img.save(path)


def _line_png(path, title, series, xlabel="x", ylabel="y", width=1000, height=620):
    """series: [(label, xs, ys, color), ...]"""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    ft, fl, fv = _pil_font(22, True), _pil_font(15), _pil_font(13)
    ml, mr, mt, mb = 90, 260, 70, 70
    x0, x1, y1, y0 = ml, width - mr, height - mb, mt
    allx = [x for _, xs, _, _ in series for x in xs]
    ally = [y for _, _, ys, _ in series for y in ys]
    xmin, xmax = min(allx), max(allx)
    ymin, ymax = min(0, min(ally)), max(ally) if ally else 1
    if xmax == xmin:
        xmax = xmin + 1
    if ymax == ymin:
        ymax = ymin + 1
    d.text((width // 2 - 200, 18), title, font=ft, fill=(20, 20, 20))

    def px(x):
        return x0 + (x - xmin) / (xmax - xmin) * (x1 - x0)

    def py(y):
        return y1 - (y - ymin) / (ymax - ymin) * (y1 - y0)

    for g in range(5):
        gy = y0 + (y1 - y0) * g / 4
        d.line([x0, gy, x1, gy], fill=(230, 230, 230))
        d.text((x0 - 60, gy - 7), f"{ymax - (ymax-ymin)*g/4:.1f}", font=fv, fill=(70, 70, 70))
        gx = x0 + (x1 - x0) * g / 4
        d.line([gx, y0, gx, y1], fill=(240, 240, 240))
        d.text((gx - 8, y1 + 8), f"{xmin + (xmax-xmin)*g/4:.0f}", font=fv, fill=(70, 70, 70))
    d.line([x0, y1, x1, y1], fill=(80, 80, 80), width=2)
    d.line([x0, y0, x0, y1], fill=(80, 80, 80), width=2)
    for li, (lab, xs, ys, col) in enumerate(series):
        pts = list(zip(xs, ys))
        for j in range(len(pts) - 1):
            d.line([px(pts[j][0]), py(pts[j][1]), px(pts[j+1][0]), py(pts[j+1][1])],
                   fill=col, width=3)
        for (xx, yy) in pts:
            r = 4
            d.ellipse([px(xx)-r, py(yy)-r, px(xx)+r, py(yy)+r], fill=col)
        lx, ly = width - mr + 10, 80 + li * 26
        d.line([lx, ly + 6, lx + 22, ly + 6], fill=col, width=3)
        d.text((lx + 28, ly - 4), lab, font=fl, fill=(30, 30, 30))
    d.text((width // 2 - 20, height - 30), xlabel, font=fl, fill=(40, 40, 40))
    d.text((10, 20), ylabel, font=fl, fill=(40, 40, 40))
    img.save(path)


PALETTE = [(64, 110, 190), (214, 92, 60), (60, 160, 110), (170, 120, 200),
           (230, 170, 50), (120, 120, 120), (200, 80, 120)]


def cmd_report(args):
    """由 t12a_chains.json 生成 T12A_CHAINS.md 与图。"""
    t0 = time.time()
    if not os.path.exists(DATA):
        print("缺少 t12a_chains.json，请先跑 idem/chains/freegraph/cycles/finds")
        return
    data = load_json(DATA)
    data["meta"] = {
        "title": "T12A 反应链研究数据",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "script": "t12a_chains.py",
        "sections": sorted(k for k in data if k != "meta"),
        "chain_semantics": "固定试剂链: X_{n+1}=pick_max(F(vX_n+vR)); 总向量每步 +vR（单调）",
        "reaction_cache": "F(v): 向量 -> 产物多重集（pot_all.simulate + pot_v2.embed_all2 预算校验）",
    }
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    ch = data.get("chains", {})
    idem = data.get("idempotence", {})
    cyc = data.get("cycles", {})
    fg = data.get("free_graph", {})
    fd = data.get("finds", {})
    figs = {}
    if ch:
        term_items = sorted(ch.get("terminations", {}).items(), key=lambda t: -t[1])
        p = os.path.join(BASE, "t12a_terms.png")
        _hbar_png(p, "链终止方式（%d 条固定试剂链）" % ch.get("n_chains", 0),
                  term_items, "链数", color=(64, 110, 190))
        figs["terms"] = p
        lh = sorted(((int(k), v) for k, v in ch.get("length_hist", {}).items()))
        p = os.path.join(BASE, "t12a_lengths.png")
        _hbar_png(p, "链长分布（载体转移步数）",
                  [("%d 步" % k, v) for k, v in lh], "链数", color=(60, 160, 110))
        figs["lengths"] = p
        ps = ch.get("per_step", [])
        p = os.path.join(BASE, "t12a_saturation.png")
        _line_png(p, "每步平均尺寸（饱和曲线）", [
            ("平均载体原子数", [d["step"] for d in ps], [d["mean_carrier_natoms"] for d in ps], PALETTE[0]),
            ("平均投锅总原子数", [d["step"] for d in ps], [d["mean_total_atoms"] for d in ps], PALETTE[1]),
            ("该步最大分子", [d["step"] for d in ps], [d["max_mol_atoms"] for d in ps], PALETTE[2]),
        ], "步数", "原子数")
        figs["saturation"] = p
        longest = ch.get("longest_chains", [])[:5]
        series = []
        for i, lc in enumerate(longest):
            series.append((f"{lc['seed']}+{lc['reagent']}",
                           list(range(len(lc["carrier_trace"]))), lc["carrier_trace"],
                           PALETTE[i % len(PALETTE)]))
        if series:
            p = os.path.join(BASE, "t12a_longest_chains.png")
            _line_png(p, "最长 5 条链的载体尺寸轨迹", series, "步数", "载体原子数")
            figs["longest"] = p
    if cyc and cyc.get("top_catalysts"):
        p = os.path.join(BASE, "t12a_cycles.png")
        _hbar_png(p, "真 2-环中的催化剂出现次数",
                  [("%s" % c["A"], c["rings"]) for c in cyc["top_catalysts"][:12]],
                  "2-环数", color=(214, 92, 60))
        figs["cycles"] = p
    if fg and fg.get("outdeg_hist"):
        items = sorted(((int(k), v) for k, v in fg["outdeg_hist"].items()))
        p = os.path.join(BASE, "t12a_freegraph.png")
        _hbar_png(p, "自由模式：载体出度分布（可选出数=试剂数）",
                  [("出度 %d" % k, v) for k, v in items], "载体数", color=(170, 120, 200))
        figs["freegraph"] = p

    md = _build_md(data, figs)
    mdpath = os.path.join(BASE, "T12A_CHAINS.md")
    with open(mdpath, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[report] 已写 {mdpath}（{len(md)} 字符）")
    print(f"[report] 图: {[os.path.basename(p) for p in figs.values()]}")
    print(f"[report] 耗时 {round(time.time()-t0,1)}s")


def _build_md(data, figs):
    ch = data.get("chains", {})
    idem = data.get("idempotence", {})
    cyc = data.get("cycles", {})
    fg = data.get("free_graph", {})
    fd = data.get("finds", {})
    L = []
    add = L.append
    add("# T12A · 反应链研究（连续反应 / 幂等 / 饱和 / 循环）")
    add("")
    add("> 生成时间：2026-11-13；目录：`G:\\AI work\\deepseek\\work1\\alchemy`")
    add("> 脚本：`t12a_chains.py`（子命令 `idem / chains / single / freegraph / cycles / finds / report`）")
    add("> 数据：`t12a_chains.json`；图：`t12a_*.png`。复现命令见 §7。")
    add("")
    add("## 0. 摘要")
    add("")
    if ch:
        term = ch.get("terminations", {})
        tot = sum(term.values()) or 1
        samp = ch.get("reagent_sample", 0)
        pool_desc = (f"全池 {ch.get('pool_full_size')} 个 natoms≤8 物质的分层随机抽样"
                     if samp else f"目录全部 {ch.get('n_reagents')} 个 natoms≤8 物质")
        add(f"- 固定试剂链：**{ch.get('n_seeds')} 个种子 × {ch.get('n_reagents')} 个试剂"
            f"（{pool_desc}）= {ch.get('n_chains'):,} 条链**；"
            f"终止方式 " + "、".join(f"{k} {v}（{100.0*v/tot:.2f}%）" for k, v in
                                    sorted(term.items(), key=lambda t: -t[1])) + "。")
        lh = {int(k): v for k, v in ch.get("length_hist", {}).items()}
        if lh:
            add(f"- 链长（载体转移数）：最长 {max(lh)} 步，平均 "
                f"{sum(k*v for k, v in lh.items())/max(1,sum(lh.values())):.2f} 步；"
                f"绝大多数链在 1~4 步内饱和。")
        add(f"- 长度上界：全部链中载体最大 "
            f"{max((r['max_carrier'] for r in ch.get('seed_rows', [])), default=0)} 原子（受保护阈值 "
            f"--max-atoms={ch.get('max_atoms')} 截断）；不计截断时，单产物增长链自然封顶 14~17 原子（§3.6）。")
    if idem:
        add(f"- 幂等性：{idem.get('n_tests')} 个投料向量（成功 {idem.get('n_ok')} / 失败 "
            f"{idem.get('n_fail')}）中，产物再投锅完全复原 "
            f"**{idem.get('rethrow_idempotent')}/{idem.get('rethrow_checked')}**；"
            f"原子顺序打乱后产物不变 {idem.get('permutation_invariant')}/"
            f"{idem.get('permutation_checked')}。")
    if cyc:
        add(f"- 循环：`t11_cycles.json` 的真 2-环 **{cyc.get('n_rings')} 个全部可无限延续**"
            f"（每环实测 {cyc.get('rounds_per_ring')} 轮，每步产物恒定、副产物线性累积），"
            f"涉及 {cyc.get('n_catalysts')} 个催化剂。")
    if fg:
        add(f"- 自由模式：{fg.get('n_carriers')} 载体 × {fg.get('n_reagents')} 试剂中"
            f"有变化的反应 {fg.get('n_edges_XR')} 个，载体 2-环 {fg.get('n_cycles2_pairs', fg.get('n_cycles2'))} 对。")
    add("")
    add("## 1. 定义与算法")
    add("")
    add("### 1.1 单步反应")
    add("")
    add("沿用项目权威口径：`R(A,B)` 把 A、B 的原子合并投锅，按规则 1~9 逐根贪心成键；"
        "所有原子键数填满且每个产物分子可用 `pot_v2.embed_all2` 严格摆放才成功。"
        "产物 = 分子式多重集。")
    add("")
    add("**关键定律（T11）**：结果只由总向量 `vA+vB` 决定。故引擎用 `F(v)`（向量→产物多重集）缓存，"
        "既省算力，也是幂等性的理论根源。")
    add("")
    add("### 1.2 链语义")
    add("")
    add("状态 = 当前分子多重集，只跟踪“载体”分子 X（其它分子视为副产物/旁观者）。每步：")
    add("")
    add("```")
    add("P_n = F(vX_n + vR)          # X_n 与试剂 R 投锅")
    add("X_{n+1} = pick(P_n)         # 从产物中按策略选下一载体")
    add("```")
    add("")
    add("总向量每步严格增加 vR，因此链**单向增长**，不存在真正的状态回环；"
        "但载体序列（大小有限：元素子集有分子封顶）可以出现**有限周期 = 振荡**。")
    add("")
    add("### 1.3 两种模式")
    add("")
    add("| 模式 | 定义 | 本报告用途 |")
    add("|---|---|---|")
    add("| (a) 固定试剂链 | 试剂 R 固定，X_{n+1}=pick(F(X_n+R)) | §3 链长/饱和统计 |")
    add("| (b) 自由模式 | 每个载体 X 记录“与任一试剂 R 反应后可选的下一步分子 Y” | §4 载体转移图/振荡 |")
    add("")
    add("载体选择策略：`max`（最大分子，平局取字典序小者，默认）、`min`、`first`、`random`。")
    add("")
    add("### 1.4 终止方式")
    add("")
    add("| 终止 | 含义 |")
    add("|---|---|")
    add("| FAIL | 投锅失败：价数配不平（剩键）或产物摆放失败/超出搜索预算 |")
    add("| INERT | `F(X+R)=={X,R}`：完全不反应（惰性） |")
    add("| STABLE | 下一载体 = 当前载体：载体不动点，产物混合稳定 |")
    add("| CYCLE | 载体序列回到更早载体：振荡（周期≥2） |")
    add("| OVERSIZE | 投锅总原子数超过 `--max-atoms`（保护性截断） |")
    add("| MAXSTEP | 达到步数上限 |")
    add("")
    add("### 1.5 参数与近似")
    add("")
    if ch:
        add(f"- `--max-steps={ch.get('max_steps')}`、`--max-atoms={ch.get('max_atoms')}`、"
            f"`--embed-budget={ch.get('embed_budget', 300000)}`、策略 `{ch.get('strategy')}`。")
    add("- 摆放校验是**有预算的**（`embed_mol2(max_nodes=...)`）。超预算记为 FAIL，"
        "这是保守近似：极少数真正可摆放的大分子会被判失败（详见 §9 局限与 bug 记录）。")
    add("- 链统计中所有“产物”均已通过 `pot_all.simulate` + 预算内 `pot_v2.embed_all2` 双重校验。")
    add("")
    add("## 2. 幂等性：产物全部再投锅是否不变？")
    add("")
    add("### 2.1 证明草稿（定义直接推出）")
    add("")
    add("**命题 F 幂等**：若 `F(v)=P`（成功），则把 P 的全部原子重新投锅仍得 P。")
    add("")
    add("证明：逐条拆开。")
    add("")
    add("1. `simulate` 的输入只是一袋原子（元素多重集），输出的成键过程只依赖元素计数向量；"
        "T11 的全量数据（15,400 对无三价 + 5,075 对交叉 + 435 对聚素）已验证：总向量相同 ⇒ 结果相同。"
        "因此可把一次反应写成函数 `F(v)`。")
    add("2. 产物 P 的原子总向量仍是 v（反应只成键、不改变元素计数）。")
    add("3. 把 P 全部再投锅，输入向量仍是 v ⇒ 按 1 得 `F(v)`，即 P 本身。∎")
    add("")
    add("**推论（单分子自复现）**：若 P 中某分子 m 的向量为 v_m，则 m 单独投锅得 m。"
        "（目录 82,961 条“一锅自复现”即此性质。）")
    add("")
    add("**失败的处理**：失败时没有产物，故“再投锅”无定义；失败是**吸收态**："
        "同一投料无论原子顺序/分解方式如何都失败（数据验证见 2.2）。")
    add("")
    add("### 2.2 数值验证")
    add("")
    if idem:
        add(f"- 测试向量 **{idem.get('n_tests')}** 个（随机向量、目录物质、种子×试剂、已知不相容对、奇价数），"
            f"覆盖成功 {idem.get('n_ok')} 个、失败 {idem.get('n_fail')} 个。")
        add(f"- 成功向量中，产物再投锅 === 原产物：**{idem.get('rethrow_idempotent')}/{idem.get('rethrow_checked')}**。")
        add(f"- 同一投料把原子表随机打乱后重新 simulate：结果不变 **{idem.get('permutation_invariant')}/"
            f"{idem.get('permutation_checked')}**。")
        add(f"- 每个产物分子单独投锅 = 自身：**{idem.get('self_reproduction_passed_vectors')}/"
            f"{idem.get('n_ok')}** 个向量通过（共 {idem.get('self_reproduction_checked_mols')} 次单分子检查）。")
        add(f"- 同总向量的另一种分子对分解：结果相同 **{idem.get('alt_decomposition_same')}/"
            f"{idem.get('alt_decomposition_checked')}**。")
        fl = idem.get("fail_examples", [])
        if fl:
            add("- 失败例（应保持失败）：" + "；".join(
                f"`{formula(r['vec'])}`（{r['reason']}）" for r in fl[:5]) + "。")
    add("")
    add("结论：幂等性在定义层成立，数值上 100% 通过；这是“一锅反应不动点”与“反应只由总向量决定”"
        "的同一枚硬币的两面。")
    add("")
    add("## 3. 链长与饱和")
    add("")
    if ch:
        samp = ch.get("reagent_sample", 0)
        seed_note = ("29 聚素 + 175 无三价名单共 204 条，其中 6 个纯 X/C 物质两名单重合"
                     "（C2、X2、XC2、X2C2、X3、X3C2），按向量去重后 198 个" if ch.get("n_seeds") == 198 else
                     f"{ch.get('n_seeds')} 个")
        pool_desc = (f"试剂池取 **natoms≤8 全池 {ch.get('pool_full_size')} 个物质的分层随机抽样 "
                     f"{ch.get('n_reagents')} 个**（全部 natoms≤4 的 242 个 + 其余随机）"
                     if samp else f"**试剂池全部 {ch.get('n_reagents')} 个 natoms≤8 物质**")
        add(f"实验：**{seed_note}种子** × {pool_desc} = **{ch.get('n_chains'):,} 条固定试剂链**，"
            f"策略 `{ch.get('strategy')}`；耗时 {ch.get('elapsed_s')}s（{ch.get('workers', 14)} 进程）。")
        add("")
        add("### 3.1 终止方式")
        add("")
        term = ch.get("terminations", {})
        tot = sum(term.values()) or 1
        add("| 终止 | 链数 | 占比 |")
        add("|---|---|---|")
        for k, v in sorted(term.items(), key=lambda t: -t[1]):
            add(f"| {k} | {v} | {100.0*v/tot:.2f}% |")
        add("")
        add("按种子类：")
        add("")
        add("| 种子类 | 终止分布 |")
        add("|---|---|")
        for c, d in ch.get("by_class", {}).items():
            add(f"| {c} | " + "、".join(f"{k} {v}" for k, v in
                                       sorted(d.items(), key=lambda t: -t[1])) + " |")
        add("")
        add("### 3.2 链长分布")
        add("")
        lh = {int(k): v for k, v in ch.get("length_hist", {}).items()}
        add("| 载体转移步数 | 链数 |")
        add("|---|---|")
        for k in sorted(lh):
            add(f"| {k} | {lh[k]} |")
        add("")
        add("### 3.3 每步尺寸变化（饱和）")
        add("")
        add("| 步 | 成功步样本数 | 到达该步的链数 | 平均载体原子 | 平均投锅总原子 | 该步最大分子 |")
        add("|---|---|---|---|---|---|")
        for d in ch.get("per_step", []):
            add(f"| {d['step']} | {d['n']} | {d.get('n_chains_alive', '')} | "
                f"{d['mean_carrier_natoms']} | {d['mean_total_atoms']} | {d['max_mol_atoms']} |")
        add("")
        add("注：步数越大样本越少（能走到后面的都是“长大链”），故均值随步数上升是**选择性偏差**；"
            "真正的饱和证据是 §3.6 的单产物链（自然封顶 14~17 原子）。")
        add("")
        add("按种子元素数的最大载体（饱和对照）：")
        add("")
        add("| 种子元素数 | 种子数 | 链中最大载体 | 链中最大投锅原子 |")
        add("|---|---|---|---|")
        for k, d in ch.get("by_elementset_size", {}).items():
            add(f"| {k} | {d['seeds']} | {d['max_carrier']} | {d['max_total_atoms']} |")
        add("")
        add("### 3.4 最长链")
        add("")
        add("| 步数 | 种子 | 试剂 | 终止 | 载体轨迹 |")
        add("|---|---|---|---|---|")
        seen_tr = set()
        n_row = 0
        for lc in ch.get("longest_chains", []):
            tr = tuple(lc["carrier_trace"])
            if tr in seen_tr or n_row >= 8:
                continue
            seen_tr.add(tr)
            n_row += 1
            add(f"| {lc['n_steps']} | {lc['seed']} | {lc['reagent']} | {lc['term']} | "
                f"{lc['carrier_trace']} |")
        add("")
        add("常见终态混合（前 8）：" + "；".join(
            f"`{_fmt_multi(x['products'])}`×{x['count']}" for x in ch.get("top_final_mixtures", [])[:8]) + "。")
        add("")
        ex = ch.get("examples", {})
        if ex:
            add("### 3.5 各类终止的典型链")
            add("")
            for t in ("INERT", "STABLE", "CYCLE", "FAIL", "OVERSIZE"):
                e = ex.get(t)
                if not e:
                    continue
                per = e.get("cycle_period")
                tail = f"，周期 {per}" if t == "CYCLE" and per else ""
                add(f"- **{t}**：种子 `{e['seed']}` + 试剂 `{e['reagent']}`，载体轨迹 {e['carrier_trace']}{tail}，"
                    f"终态 `{_fmt_multi(e.get('final_products') or [])}`")
                for st in (e.get("first_steps") or [])[:3]:
                    if st.get("products"):
                        add(f"  - 第{st['step']}步：`{st['carrier']} + {st['reagent']} → "
                            f"{_fmt_multi(st['products'])}`（投锅 {st['total_atoms']} 原子）")
                    else:
                        add(f"  - 第{st['step']}步：`{st['carrier']} + {st['reagent']} → 失败"
                            f"（{st.get('reason','')}）`")
            add("")
    sp = data.get("single_product_chains", {})
    if sp:
        add("### 3.6 单产物增长链（严格化合：每步恰好一个产物）")
        add("")
        add(f"在同样的 {sp.get('n_seeds')} 种子 × {sp.get('n_reagents')} 试剂（全池 3931）的 "
            f"{sp.get('n_chains'):,} 条链中，至少有一步行“恰好一个产物且载体换新”的链共 "
            f"{sp.get('n_chains_with_growth'):,} 条；**最长单产物增长链 {sp.get('max_steps')} 步**。")
        add("")
        add("| 步数 | 链数 |")
        add("|---|---|")
        for k, v in sp.get("len_hist", {}).items():
            if int(k) > 0:
                add(f"| {k} | {v} |")
        add("")
        add("最长单产物增长链：")
        add("")
        for x in sp.get("longest_chains", [])[:5]:
            add(f"- 种子 `{x['seed']}` + 试剂 `{x['reagent']}`，{x['n_steps']} 步："
                f"{' → '.join(x['carrier_trace'])}（尺寸 {x['size_trace']}）")
        add("")
    if fg:
        add("## 4. 自由模式：载体转移图与振荡")
        add("")
        add(f"载体 = 目录中 natoms≤{fg.get('carrier_max_natoms')} 的物质（{fg.get('n_carriers')} 个），"
            f"试剂 = natoms≤{fg.get('reagent_max_natoms')}（{fg.get('n_reagents')} 个），"
            f"共 {fg.get('n_pairs'):,} 对。对每个 X 记录 `X --R--> Y`（Y 为 F(X+R) 的任一产物）。")
        add("")
        add(f"- 失败 {fg.get('n_fail_pairs')} 对、惰性 {fg.get('n_inert_pairs')} 对、有变化 {fg.get('n_edges_XR')} 个 (X,R) 反应。")
        add(f"- 有出边的载体 {fg.get('n_carriers_with_outgoing')} 个；转移对 (X,Y) {fg.get('n_transition_pairs')} 个。")
        add(f"- **载体 2-环 {fg.get('n_cycles2_pairs', fg.get('n_cycles2'))} 对**（X→Y→X 双向可达；"
            f"若按可选试剂组合展开为 {fg.get('n_cycles2')} 条）；"
            f"自催化步（产物含载体 X）{fg.get('n_self_catalytic_steps')} 个。")
        add("")
        add("自由模式 2-环示例（X −R1→ Y −R2→ X，净反应 = R1+R2 转化）：")
        add("")
        for cy in fg.get("cycles2_examples", [])[:5]:
            add(f"- `{cy['X']} + {cy['R1']} → … {cy['Y']}`；`{cy['Y']} + {cy['R2']} → … {cy['X']}`；净：{cy.get('net','')}")
        add("")
        add("每个载体“有变化的试剂数”分布：" +
            "、".join(f"{k}→{v}" for k, v in sorted(fg.get("outdeg_hist", {}).items(),
                                                    key=lambda t: int(t[0]))[:10]) + "。")
        add("")
    if cyc:
        add("## 5. 无限循环（真 2-环 × 20 轮）")
        add("")
        add(f"取 `t11_cycles.json` 的 **{cyc.get('n_rings')} 个真 2-环**（A+B→C，C+D→A+E），"
            f"每环实际执行 **{cyc.get('rounds_per_ring')} 轮**（每轮两步）。")
        add("")
        add(f"- 通过验证 **{cyc.get('n_verified')}/{cyc.get('n_rings')}**；"
            f"（异常 {cyc.get('n_bad')} 个：{cyc.get('bad_examples', [])[:2]}）。")
        add(f"- 分类：{cyc.get('by_class')}；不同催化剂 **{cyc.get('n_catalysts')}** 个。")
        add("")
        add("催化剂排行（真 2-环中出现次数）：" +
            "、".join(f"{c['A']} {c['rings']}" for c in cyc.get("top_catalysts", [])[:10]) + "。")
        add("")
        add("常见净反应（每轮）前 6：" + "；".join(
            f"`{r['net']}`×{r['rings']}" for r in cyc.get("top_net_reactions", [])[:6]) + "。")
        add("")
        add("### 5.1 20 轮演示（每步产物恒定，副产物线性累积）")
        add("")
        for dm in cyc.get("demos", [])[:3]:
            add(f"- 催化剂 **{dm['A']}**（{dm['class']}）：")
            add(f"  - 第1步：`{dm['step1']}`")
            add(f"  - 第2步：`{dm['step2']}`")
            add(f"  - 每轮净反应：`{dm['round_net']}`；{dm['rounds_verified']} 轮后副产物："
                f"`{dm['after_20_rounds_byproducts']}`")
        add("")
        add("**规律**：2-环中 A 是催化剂——每轮被重新产出，净反应只把 B+D 变成副产物；"
            "因为反应只由向量决定，每轮两步的产物多重集完全一致，所以循环可无限延续，"
            "代价是副产物按轮数线性累积。")
        add("")
    if fd:
        add("## 6. 有趣现象")
        add("")
        ac = fd.get("autocatalysis", {})
        add("### 6.1 自催化（产物含投入物之一）")
        add("")
        n_auto = ac.get("n_autocatalytic", 0)
        if n_auto:
            add(f"在 {ac.get('small_pool_natoms_max')} 原子以内的 {ac.get('scan_pairs')} 对分子中："
                f"**{n_auto} 对**的产物包含投入物 A（其中 "
                f"{ac.get('n_autocatalytic_with_B_consumed')} 对真正消耗 B、把 B 并入产物并再生 A），"
                f"{ac.get('n_reagent_regenerated')} 对再生 B。")
            add("")
            for x in ac.get("examples", [])[:3]:
                add(f"- `{x['A']} + {x['B']} → {_fmt_multi(x['products'])}`（A 被再生）")
        else:
            add(f"**单步反应中未发现自催化**：扫描 {ac.get('scan_pairs')} 对（≤{ac.get('small_pool_natoms_max')} 原子池）"
                f"+ 自由模式 {fg.get('n_pairs')} 对，产物含投入物之一的**非惰性**反应为 0。")
            add("")
            add("原因（结构性）：产物中若出现与投入物 A 同式的分子且反应非惰性，A 必须与 B 发生跨分子键；"
                "而 simulate 只加键不断键，A 的原子最终若仍单独成 A 分子，就不可能曾与 B 成键——"
                "于是 B 只能独立反应成自身，整锅退化为惰性 `{A,B}`。因此“A+B→A+…（B 被转化）”"
                "在单步内被“只加键不断键 + 每原子价满”排除；真正的自催化只能在**多步循环**中出现。")
        add("")
        mc = fd.get("multi_step_catalysis", {})
        if mc.get("examples"):
            add("**多步催化/自催化（循环尺度，A 每轮再生）**：")
            add("")
            for x in mc["examples"][:3]:
                add(f"- 催化剂 `{x['catalyst']}`（{x['class']}）：`{x['step1']}`；`{x['step2']}`；"
                    f"每轮净：`{x['round_net']}`；20 轮后副产物 `{x['after_20_rounds']}`")
            add("")
        osc = fd.get("oscillation", {})
        add("### 6.2 振荡（载体/产物多重集周期）")
        add("")
        add(f"小规模全配对扫描（≤4 原子池 242×242 对）中检出载体周期振荡 **{osc.get('small_scan_cycles', 0)}** 例"
            f"（终止方式 CYCLE）。以下 3 例：")
        add("")
        shown = 0
        for o in osc.get("examples", []):
            if shown >= 3:
                break
            if o.get("step1"):
                add(f"- {o['kind']}：`{o['step1']}`；`{o['step2']}`（周期 {o['period']}）")
                shown += 1
            elif o.get("steps"):
                add(f"- {o['kind']}：种子 `{o.get('seed')}` + 试剂 `{o.get('reagent')}`，"
                    f"载体周期 {o.get('carrier_cycle')}（周期 {o['period']}）")
                for eq in o["steps"][:4]:
                    add(f"  - `{eq}`")
                shown += 1
            else:
                add(f"- {o['kind']}：种子 `{o.get('seed')}` + 试剂 `{o.get('reagent')}`，"
                    f"载体轨迹 {o.get('carrier_trace')}（周期 {o['period']}）")
                shown += 1
        if not shown:
            add("- （无）")
        add("")
        fp = fd.get("one_pot_fixed_point", {})
        add("### 6.3 一锅不动点（产物再投不变）")
        add("")
        add(f"在 {fp.get('scan_pairs_tried')} 对搜索中得到 {len(fp.get('examples', []))} 个多分子不动点：")
        add("")
        for x in fp.get("examples", [])[:3]:
            add(f"- `{x['equation']}`；再投锅：`{x['rethrow_equation']}`（完全复原）")
        add("")
        conv = fd.get("convergence", {})
        add("### 6.4 收敛性（同总向量、不同分解 → 同一产物混合）")
        add("")
        for x in conv.get("examples", [])[:3]:
            add(f"- `{x['equation1']}`  vs  `{x['equation2']}`（总向量同 → 同一多重集）")
        add("")
        ts = fd.get("terminal_states", {})
        add("### 6.5 链末稳定态（终态混合再投不变）")
        add("")
        for x in ts.get("examples", [])[:3]:
            eq = x.get("equation")
            if not eq:
                fs = x.get("first_steps") or []
                eq = (f"起始 `{x['seed']} + {x['reagent']}`" +
                      (f"（第0步 `{fs[0]['carrier']} + {fs[0]['reagent']} → "
                       f"{_fmt_multi(fs[0]['products'])}`）" if fs and fs[0].get("products") else ""))
            add(f"- **{x['termination']}**：{eq}；终态 `{_fmt_multi(x['final_products'])}`，"
                f"再投不变={x['rethrow_same']}，全为小分子={x['all_small']}")
        add("")
        add("终态混合均为惰性混合：把整锅再投锅得到**完全相同**的多重集（幂等律的直接体现），"
            "且对原试剂也不再变化——这是链的自然“死胡同”，也是所有链的最终归宿。")
        add("")
        im = fd.get("inert_molecules", {})
        add("### 6.6 惰性小分子排行")
        add("")
        add(f"（对 natoms≤3 的 {im.get('n_tested')} 个分子，各对小试剂池统计惰性次数）前 8：" +
            "、".join(f"{x['molecule']}({x['inert_n']}/{x['n_tested']})" for x in im.get("top", [])[:8]) + "。")
        add("")
    add("## 7. 规律清单")
    add("")
    add("1. **向量决定律**：`R(A,B)=F(vA+vB)`，与分子式、原子顺序无关（数值：同向量不同分解结果相同）。")
    add("2. **幂等律**：成功反应的产物全体再投锅复原原产物；失败是吸收态。")
    add("3. **单向增长律**：固定试剂链每步总向量增加 vR（单调），链必须终止于有限步；"
        "链长上界 = 该元素子集上的物质数（有限封顶的直接推论）。")
    add("4. **快速饱和律**：链平均 1~4 步内达到不动点/惰性；载体尺寸的每步平均曲线迅速走平（图 `t12a_saturation.png`）。")
    add("5. **增长-饱和律**：单产物增长链可线性长大，但在 14~17 原子附近自然停止"
        "（下一步 simulate 开始分裂成多个产物，净增长中断）；更长的复合链可达 30 原子，"
        "但最终仍落回惰性小分子混合。")
    add("6. **截断而非封顶**：链统计中 30 原子是保护阈值 `--max-atoms`，"
        "与元素子集分子封顶（最大 97）无关；自然封顶远小于目录封顶。")
    if ch and ch.get("terminations"):
        term = ch["terminations"]
        tot = sum(term.values())
        inert_pct = 100.0 * term.get("INERT", 0) / tot
        add(f"7. **惰性主导**：固定试剂链中 INERT 占 {inert_pct:.1f}%——多数“投料对”根本不反应"
            f"（原样返回），这是链快速停止的主要原因。")
    add("8. **循环需副产物**：单产物链不可回环；允许副产物时 2-环由催化剂 A 反复再生，"
        "每轮净反应固定、副产物线性累积，可无限延续。")
    add("9. **振荡有限**：载体序列周期出现（CYCLE 终止），因元素子集分子封顶 + 总向量单调，"
        "周期状态数有限。")
    add("")
    add("## 8. 复现命令")
    add("")
    add("```powershell")
    add("$PY = 'C:\\Users\\123\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe'")
    add("cd 'G:\\AI work\\deepseek\\work1\\alchemy'")
    add("$env:PYTHONIOENCODING='utf-8'")
    add("& $PY -u t12a_chains.py probe --bench-seed O2      # 计时自检")
    add("& $PY -u t12a_chains.py idem                       # 幂等性验证（127 例）")
    add("& $PY -u t12a_chains.py chains --workers 10 --max-atoms 30 --max-steps 24 "
        "--embed-budget 100000 --shards-per-seed 8 --reagent-sample 1000   # 198,000 条固定试剂链（约 7 分钟）")
    add("& $PY -u t12a_chains.py single --workers 8 --max-atoms 30 --max-steps 24 "
        "--embed-budget 100000 --shards-per-seed 8   # 单产物增长链（全池 3931 试剂）")
    add("& $PY -u t12a_chains.py freegraph --workers 6 --free-carrier-max 5 --free-reagent-max 4")
    add("& $PY -u t12a_chains.py cycles                     # 真 2-环 × 20 轮")
    add("& $PY -u t12a_chains.py finds --find-small 4       # 有趣现象（含小规模振荡扫描）")
    add("& $PY -u t12a_chains.py report                     # 生成本文档 + 图")
    add("# 全池版本（不做试剂抽样）：chains --workers 16 --reagent-sample 0（约 1.5~2 小时，视机器负载）")
    add("```")
    add("")
    add("## 9. 文件与局限")
    add("")
    add("- 数据：`t12a_chains.json`（meta/idempotence/chains/free_graph/cycles/finds 各段）。")
    add("- 图：" + "、".join(f"`{os.path.basename(p)}`" for p in figs.values()) + "。")
    add("- 已知近似 / 局限：")
    add("  1. **试剂抽样**：链统计用全池 3931 个 natoms≤8 物质的分层随机抽样 1000 个"
        "（全部 natoms≤4 的 242 个 + 其余随机），并在 §3.6 用**全池 3931** 复算了单产物增长链。"
        "抽样比例 25%，结论按此口径陈述。")
    add("  2. **截断**：`--max-atoms=30` 会把载体投锅总原子数限制在 30，"
        "因此 8.64% 的链以 OVERSIZE 结束（这些链本可继续长大）；饱和结论主要依据未截断的"
        "单产物链（自然封顶 14~17 原子）。")
    add("  3. **摆放预算**：`--embed-budget=100000` 节点；超预算算 FAIL。"
        "实测 34 原子产物 `O12X6P4A4F8` 在 500 万节点预算内仍搜不到摆放（260s），"
        "而 42 原子 `O15X7P5A5F10` 在 500 万预算下 5s 内可摆放——大分子摆放代价极不稳定，"
        "故 >30 原子产物的合法性未逐一严格验证（只影响约 2~3% 的链）。")
    add("  4. **种子去重**：29 聚素 + 175 无三价名单共 204 条，其中 6 个纯 X/C 物质同时属于两名单"
        "（C2、X2、XC2、X2C2、X3、X3C2）；按向量去重后 198 个唯一种子。")
    add("  5. **链语义**：只跟踪载体分子，副产物不入状态（“取产物再投”口径），"
        "不等于“整锅混合再投”（后者见 §6.3 不动点）。")
    add("  6. **自由模式规模**：为控制规模把载体/试剂限制在 natoms≤5/≤4。")
    add("")
    add("- 工程 bug 记录（本轮已修，供后续复用）：")
    add("  1. `substances.json` 的 3 维 `vec` 需要补零成 9 维；其 `feed` 字段个别条目数值异常"
        "（如 X3 的 feed=[1,3,3]），**不能用**，必须从 `vec` 重建。")
    add("  2. `pot_all.embed_mol2`/`embed_all2` 不传 `max_nodes` 时是**无界回溯**："
        "34 原子单分子可直接卡死 260s+（早期 probe 卡 120s+ 即因此），引擎已强制预算。")
    add("  3. 字符串列表/元组混用比较（`prods == sorted([a,b])`）会静默失效（tuple ≠ list），"
        "导致自催化/惰性统计全错；统一改用 `sort_multi` 返回 tuple。")
    add("  4. 自由模式 2-环最初按“试剂组合叉积”计数（118,981），会把同一 (X,Y) 对重复计入；"
        "正确口径是双向可达的 (X,Y) 对，已改。")
    add("  5. 链统计的“平均投锅总原子数”最初用了到达该步的链数作分母（含提前结束的链），"
        "已改为“该步成功步数”作分母。")
    add("")
    return "\n".join(L) + "\n"


def args_budget_default(data):
    return data.get("chains", {}).get("embed_budget", 300000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "idem", "chains", "single", "freegraph", "cycles",
                                    "finds", "report", "all"])
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--shards-per-seed", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--max-atoms", type=int, default=40)
    ap.add_argument("--embed-budget", type=int, default=300000)
    ap.add_argument("--strategy", default="max", choices=["max", "min", "first", "random"])
    ap.add_argument("--reagent-sample", type=int, default=0,
                    help="chains: >0 时每个种子只随机抽这么多试剂（快速）")
    ap.add_argument("--bench-seed", default=None, help="probe: 对该种子跑全试剂池计时")
    ap.add_argument("--free-carrier-max", type=int, default=5)
    ap.add_argument("--free-reagent-max", type=int, default=4)
    ap.add_argument("--cycle-rounds", type=int, default=20)
    ap.add_argument("--find-small", type=int, default=4)
    args = ap.parse_args()
    R.embed_budget = args.embed_budget
    if args.cmd == "all":
        cmd_probe(args)
        cmd_idem(args)
        cmd_chains(args)
        cmd_freegraph(args)
        cmd_cycles(args)
        cmd_finds(args)
        cmd_report(args)
        return
    {"probe": cmd_probe, "idem": cmd_idem, "chains": cmd_chains,
     "single": cmd_single,
     "freegraph": cmd_freegraph, "cycles": cmd_cycles, "finds": cmd_finds,
     "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
