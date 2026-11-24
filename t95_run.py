# -*- coding: utf-8 -*-
"""T95 A/B 运行器：v0（当前 T94 规则）/ v1（P1 单格推挤）/ v2（P2 团簇动量）。

6 臂 = {无膜, PK 膜, 双层 OXC+OP} × {G=0, G=0.2}，同一 seed、同一 E4 环境池、
600 拍；输出 t95_ab.json（每臂指标 + 5 个守恒/完整性 assert + series）与
t95_run.log。报告见 docs/T95_COLLISION.md。

环境 E4 定义沿用 t94_env.ENVS[3]（O/X/C 三元素等丰度，目录分子 2~8 原子），
本文件自行实现采样，避免依赖他模块私有全局；目标份额 {O:1/3, X:1/3, C:1/3}。
"""

import argparse
import bisect
import io
import json
import math
import os
import random
import sys
import time

import t83_env_axes as T83
import t94_life as T94
from t95_collision import PushWorld
from t95_config import params

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE, "t95_run.log")
SEED = 20261124
TICKS = 600
MEASURE_EVERY = 10

E4_TARGET = {"O": 1.0 / 3.0, "X": 1.0 / 3.0, "C": 1.0 / 3.0}

ARMS = [
    {"key": "nomem_G00", "note": "无膜 + E4 环境，G=0（重力对照）",
     "membrane": None, "n_mem": 0, "outer": None, "outer_n": 0, "grav": 0.0},
    {"key": "nomem_G02", "note": "无膜 + E4 环境，G=0.2（默认重力）",
     "membrane": None, "n_mem": 0, "outer": None, "outer_n": 0, "grav": 0.2},
    {"key": "PK_G00", "note": "PK 高 D 膜（D=3,A=0）+ E4，G=0",
     "membrane": "PK", "n_mem": 220, "outer": None, "outer_n": 0, "grav": 0.0},
    {"key": "PK_G02", "note": "PK 高 D 膜 + E4，G=0.2",
     "membrane": "PK", "n_mem": 220, "outer": None, "outer_n": 0, "grav": 0.2},
    {"key": "double_G00", "note": "双层 OXC(内)+OP(外) + E4，G=0",
     "membrane": "OXC", "n_mem": 300, "outer": "OP", "outer_n": 90, "grav": 0.0},
    {"key": "double_G02", "note": "双层 OXC(内)+OP(外) + E4，G=0.2",
     "membrane": "OXC", "n_mem": 300, "outer": "OP", "outer_n": 90, "grav": 0.2},
]

VERSIONS = [
    {"id": "v0", "stage": 0, "note": "基线：当前 T94 规则（已删布朗）"},
    {"id": "v1", "stage": 1, "note": "P1：单格链式推挤"},
    {"id": "v2", "stage": 2, "note": "P2：团簇速度场/动量 + 推挤"},
]


# ---------------------------------------------------------------- 基础
def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with io.open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def atomic_json(path, obj):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------------------------------------------------------------- 环境 E4
def build_e4_pool(n_pool=300, seed=SEED, iters=200, damp=0.5):
    """按 t94_env.ENVS[3]（E4: O/X/C 等丰度）从目录采样环境分子池。"""
    cat = T83.catalog_index()
    support = set(E4_TARGET)
    species = []
    for f in cat:
        c = T83.comp_of(f)
        if not c or not set(c) <= support:
            continue
        ni = sum(c.values())
        if ni < 2 or ni > 8:
            continue
        species.append((f, c, ni))
    species.sort(key=lambda x: x[0])
    if not species:
        raise RuntimeError("E4 环境池为空：目录中没有 O/X/C 分子")
    # IPF：使原子份额趋于 1:1:1
    keys = sorted(support)
    want = {e: E4_TARGET[e] for e in keys}
    tot = sum(want.values())
    want = {e: want[e] / tot for e in keys}
    w = [1.0] * len(species)
    for _ in range(iters):
        cur = {e: 0.0 for e in keys}
        for i, (f, c, ni) in enumerate(species):
            wi = w[i]
            if wi:
                for e, k in c.items():
                    if e in cur:
                        cur[e] += wi * k
        fac = {e: (want[e] / cur[e] if cur[e] > 0 else 1.0) for e in keys}
        new = []
        for i, (f, c, ni) in enumerate(species):
            prod = 1.0
            for e, k in c.items():
                if e in fac:
                    prod *= fac[e] ** (k / float(ni))
            new.append(max(w[i] * (prod ** damp), 1e-12))
        s = sum(new)
        w = [x * len(new) / s for x in new]
    cum = []
    acc = 0.0
    for x in w:
        acc += x
        cum.append(acc)
    rng = random.Random(seed)
    pool = []
    for _ in range(n_pool):
        r = rng.random() * acc
        pool.append(species[bisect.bisect_left(cum, r)][0])
    # 统计
    elem = {}
    atoms = 0
    for f in pool:
        c = T83.comp_of(f)
        for e, k in c.items():
            elem[e] = elem.get(e, 0) + k
        atoms += sum(c.values())
    total = float(sum(elem.values())) or 1.0
    share = {e: round(elem.get(e, 0) / total, 4) for e in keys}
    return pool, {"n_pool": len(pool), "n_species": len(set(pool)),
                  "atoms_per_mol": round(atoms / float(len(pool)), 3),
                  "achieved_share": share, "target": want,
                  "candidate_species": len(species), "seed": seed}


# ---------------------------------------------------------------- 臂参数
def arm_params(arm, quick=False, ticks_override=None):
    p = dict(arm)
    ticks = TICKS if not quick else 120
    if ticks_override:
        ticks = int(ticks_override)
    if quick:
        p["W"], p["H"] = 120, 80
        p["center"] = (40, 60)
        p["body_n"] = 12
        p["n_mem"] = max(20, int(p["n_mem"] * 0.5))
        p["outer_n"] = max(0, int(p["outer_n"] * 0.5))
        p["food_n"] = max(4, int(T94.FOOD_N * 0.4))
        p["env_n"] = 120
        ticks = min(ticks, 120)
    else:
        p["W"], p["H"] = T94.W0, T94.H0
        p["center"] = T94.CORE_CENTER
        p["body_n"] = T94.BODY_N
        p["food_n"] = T94.FOOD_N
        p["env_n"] = 300
    p["ticks"] = ticks
    return p


# ---------------------------------------------------------------- assert
def check_arm(w):
    """5 个复核 assert：元素守恒 / footprint 完整 / 占格唯一 / 主体冻结 / 速度有界。"""
    out = []
    # A1 元素守恒
    ok = w.elements0 == w.elements()
    out.append({"name": "A1_element_conservation", "ok": bool(ok),
                "detail": "elements0 == elements_final" if ok else "元素不守恒"})
    # A2 footprint 完整：每个活分子的 cells 全指向自己
    bad = 0
    total_cells = 0
    for m in w.mols:
        if m["dead"]:
            continue
        total_cells += len(m["cells"])
        for (r, c) in m["cells"]:
            if w.cell.get((r, c)) != m["id"]:
                bad += 1
    ok = bad == 0 and total_cells == w.n_cells_used
    out.append({"name": "A2_footprint_intact", "ok": bool(ok),
                "detail": "bad_cells=%d cells=%d n_cells_used=%d"
                          % (bad, total_cells, w.n_cells_used)})
    # A3 占格唯一 / 完整
    seen = {}
    dup = 0
    for m in w.mols:
        if m["dead"]:
            continue
        for cell in m["cells"]:
            if cell in seen:
                dup += 1
            seen[cell] = m["id"]
    ok = dup == 0 and len(seen) == len(w.cell) == w.n_cells_used
    out.append({"name": "A3_cell_map_unique", "ok": bool(ok),
                "detail": "dup=%d occupied=%d cell_map=%d n_cells_used=%d"
                          % (dup, len(seen), len(w.cell), w.n_cells_used)})
    # A4 主体冻结：仍存活的主体血统分子必须一格未动；死亡是化学反应（T94 主体
    # 可被环境攻击杀死），由 body_killed 单独统计，不算位移违规。
    moved = 0
    dead = 0
    for mid, cells0 in (w.body_cells0 or {}).items():
        m = w.mols[mid]
        if m["dead"]:
            dead += 1
            continue
        if tuple(m["cells"]) != cells0:
            moved += 1
    ok = moved == 0
    out.append({"name": "A4_body_frozen", "ok": bool(ok),
                "detail": "moved=%d dead_by_chem=%d" % (moved, dead)})
    # A5 速度有界 / 有限（v0 无速度场，自动通过）
    vmax = float(w.P["Vmax"]) + 1e-6
    bad_v = 0
    bad_pos = 0
    for m in w.mols:
        if m["dead"]:
            continue
        vx, vy = m.get("vx", 0.0), m.get("vy", 0.0)
        if not (math.isfinite(vx) and math.isfinite(vy)):
            bad_v += 1
        elif math.hypot(vx, vy) > vmax:
            bad_v += 1
        if not (math.isfinite(m["r"]) and math.isfinite(m["c"])):
            bad_pos += 1
    ok = bad_v == 0 and bad_pos == 0
    out.append({"name": "A5_velocity_bounded", "ok": bool(ok),
                "detail": "bad_v=%d bad_pos=%d vmax=%.2f" % (bad_v, bad_pos, vmax)})
    return out


# ---------------------------------------------------------------- 单臂
def summarize(w, series, ver, arm, runtime_s, asserts):
    s = series[-1]
    movers = [r.get("mean_abs_v", 0.0) for r in series if "mean_abs_v" in r]
    return {
        "version": ver["id"], "stage": ver["stage"], "arm": arm["key"],
        "note": arm["note"], "grav": arm["grav"],
        "membrane": arm["membrane"], "outer": arm["outer"],
        "n_mem0": w.membrane_n0, "ticks": w.ticks_total,
        "runtime_s": round(runtime_s, 2),
        "n_final": s["n"],
        "body_n0": w.body_n0, "body_n_final": s["body_n"],
        "body_atoms0": w.body_atoms0, "body_atoms_final": s["body_atoms"],
        "body_cy_final": s.get("body_cy"),
        "membrane_n_final": s["membrane_n"],
        "membrane_retention": round(s["membrane_n"] / max(1, w.membrane_n0), 4)
        if w.membrane_n0 else None,
        "coverage_ang_final": s["coverage_ang"],
        "coverage_ang_mean": round(
            sum(r["coverage_ang"] for r in series[1:]) / max(1, len(series) - 1), 4)
        if len(series) > 1 else s["coverage_ang"],
        "env_n_final": s["env_n"],
        "contacts_env_body_total": s["contacts_env_body_cum"],
        "contacts_env_mem_total": s["contacts_env_mem_cum"],
        "core_env_react_total": s["core_env_react_cum"],
        "mem_env_react_total": s["mem_env_react_cum"],
        "internal_react_total": s["internal_react_cum"],
        "env_react_total": s["env_react_cum"],
        "n_react_total": s["n_react_total"],
        "n_moves": s.get("n_moves"), "n_blocked": s.get("n_blocked"),
        "n_push": s.get("n_push_cum", 0),
        "n_push_fail": s.get("n_push_fail_cum", 0),
        "n_grav_push": s.get("n_grav_push_cum", 0),
        "n_cluster_moves": s.get("n_cluster_moves_cum", 0),
        "chain_hist": s.get("chain_hist", {}),
        "mean_abs_v_final": s.get("mean_abs_v", 0.0),
        "mean_abs_v_avg": round(sum(movers) / len(movers), 4) if movers else 0.0,
        "mem_cy_final": s.get("mem_cy"),
        "membrane_inner_final": s.get("membrane_inner_n"),
        "membrane_outer_final": s.get("membrane_outer_n"),
        "conservation_ok": w.elements0 == w.elements(),
        "asserts": asserts,
        "asserts_all_ok": all(a["ok"] for a in asserts),
        "T_react_mean": s.get("T_react_mean"),
        "timeline": [[r["t"], r["body_n"], r["body_atoms"],
                      r["contacts_env_body_cum"], r["coverage_ang"],
                      r.get("mean_abs_v", 0.0)] for r in series],
    }


def run_one(ver, arm, pool, pool_meta, quick=False, ticks=None,
            seed=SEED, measure_every=MEASURE_EVERY):
    p = arm_params(arm, quick=quick, ticks_override=ticks)
    t0 = time.time()
    w = PushWorld(
        W=p["W"], H=p["H"], seed=seed, env_feed=pool, env_name="E4",
        membrane=p["membrane"], n_mem=p["n_mem"],
        body_n=p["body_n"], food_formula=T94.FOOD_FORMULA,
        food_n=p["food_n"], grav=p["grav"], ticks_total=p["ticks"],
        center=p["center"], body_formula=T94.BODY_FORMULA,
        stage=ver["stage"], outer_membrane=p["outer"],
        outer_n=p["outer_n"], push_params=params())
    w.t = 0
    w.Tamb = w.ambient_T(0)
    series = [w.measure(0)]
    log("[%s/%s] 放置 body=%d mem=%d outer=%d food=%d env=%d | stage=%d G=%.2f ticks=%d"
        % (ver["id"], arm["key"], w.body_n0, w.membrane_n0,
           w.outer_n if w.outer_membrane else 0, w.food_n0, w.env_n0,
           ver["stage"], p["grav"], p["ticks"]))
    for t in range(1, p["ticks"] + 1):
        w.t = t
        w.step()
        if t % measure_every == 0 or t == p["ticks"]:
            series.append(w.measure(t))
    asserts = check_arm(w)
    summary = summarize(w, series, ver, arm, time.time() - t0, asserts)
    summary["env_meta"] = pool_meta
    summary["config"] = {
        "engine": "T95 PushWorld（T94 试验场 + 碰撞/推挤）",
        "stage": ver["stage"], "version": ver["id"],
        "params": w.P, "world": {"W": w.W, "H": w.H, "center": list(w.center)},
        "body_formula": T94.BODY_FORMULA, "body_n": p["body_n"],
        "food_formula": T94.FOOD_FORMULA, "food_n": p["food_n"],
        "membrane": p["membrane"], "n_mem": p["n_mem"],
        "outer": p["outer"], "outer_n": p["outer_n"],
        "env": "E4（O/X/C 等丰度）", "env_n": p["env_n"],
        "grav": p["grav"], "seed": seed, "ticks": p["ticks"],
        "quick": quick,
        "t94_params": dict(T94.CFG.DEFAULT_PARAMS),
        "t95_params": params(),
        "F2V": 0.02, "M_EPS": 0.05,
    }
    return summary, series


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--versions", default="v0,v1,v2")
    ap.add_argument("--arms", default="")
    ap.add_argument("--ticks", type=int, default=0)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--outdir", default=BASE)
    ap.add_argument("--measure-every", type=int, default=MEASURE_EVERY)
    a = ap.parse_args(argv)
    log("=" * 78)
    log("T95 碰撞/推挤 A/B | quick=%s | seed=%d | params=%s"
        % (a.quick, a.seed, params()))
    pool, pool_meta = build_e4_pool(n_pool=120 if a.quick else 300, seed=a.seed)
    log("E4 环境池: %d 分子 / %d 种 / %s 原子每分子 / 实现份额 %s"
        % (pool_meta["n_pool"], pool_meta["n_species"],
           pool_meta["atoms_per_mol"], pool_meta["achieved_share"]))
    vids = [x.strip() for x in a.versions.split(",") if x.strip()]
    versions = [v for v in VERSIONS if v["id"] in vids]
    arm_keys = [x.strip() for x in a.arms.split(",") if x.strip()]
    arms = [x for x in ARMS if (not arm_keys or x["key"] in arm_keys)]
    outdir = a.outdir
    os.makedirs(outdir, exist_ok=True)
    all_sum = []
    all_series = {}
    t0 = time.time()
    for ver in versions:
        for arm in arms:
            try:
                summary, series = run_one(
                    ver, arm, pool, pool_meta, quick=a.quick,
                    ticks=a.ticks or None, seed=a.seed,
                    measure_every=a.measure_every)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                log("[%s/%s] 失败: %s" % (ver["id"], arm["key"], ex))
                continue
            s = summary
            log("[%s/%s] 完成 %.1fs | body %d/%d 原子 | envC %d | coreER %d | "
                "cov %.2f | mem %.0f%% | push %d/fail %d | mean|v| %.3f | asserts %s"
                % (ver["id"], arm["key"], s["runtime_s"],
                   s["body_n_final"], s["body_atoms_final"],
                   s["contacts_env_body_total"], s["core_env_react_total"],
                   s["coverage_ang_final"],
                   100.0 * (s["membrane_retention"] or 0),
                   s["n_push"], s["n_push_fail"], s["mean_abs_v_avg"],
                   "OK" if s["asserts_all_ok"] else "FAIL"))
            all_sum.append(s)
            all_series["%s|%s" % (ver["id"], arm["key"])] = series
            atomic_json(os.path.join(outdir, "t95_ab.json"), {
                "config": {
                    "task": "T95 碰撞/推挤引擎 A/B",
                    "versions": versions, "arms": ARMS,
                    "t95_params": params(), "t94_params": dict(T94.CFG.DEFAULT_PARAMS),
                    "F2V": 0.02, "M_EPS": 0.05, "seed": a.seed,
                    "quick": a.quick, "env": "E4", "env_meta": pool_meta,
                },
                "arms": all_sum,
                "series": all_series,
                "runtime_s": round(time.time() - t0, 2),
            })
    log("全部完成: %d 组, %.1fs -> %s"
        % (len(all_sum), time.time() - t0,
           os.path.join(outdir, "t95_ab.json")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
