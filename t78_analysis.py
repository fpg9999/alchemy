# -*- coding: utf-8 -*-
"""t78_analysis.py —— T78 三轴介质箱实验结果汇总/交叉核对

读 t78_{main,nogate,nochem}_result.json，输出：
  1) 三臂总表（N/原子/反应漏斗/恒素场/新物质）
  2) 分层表（三档 y 均值随时间；终态三带组成）
  3) 恒素场演化 + 终态 10x20 ASCII 图（main / nochem）
  4) 反应地理（ρ 分桶：attempts / reactions / 反应率）
  5) 27 格分布（终态，按分子数与原子数）
  6) 新物质统计（数量、原子数分布、27 格归属、是否在 84,225 目录）
  7) 快照交叉验证：局部 ρ 与局部平均温度的相关（热→富集方向）
  8) 一致性核对：band/直方图/计数器求和
所有数字来自结果 JSON，算完写 t78_analysis.json 供 docs 引用。
用法：python t78_analysis.py
"""
import json
import os
import sys

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
from alchemy import attrs as A
from alchemy.core.elements import ORDER as ELEM_ORDER

ARMS = ("main", "nogate", "nochem")
W, H = 2000.0, 4000.0
EX, EY = 10, 20


def load(arm):
    with open(os.path.join(BASE, "t78_%s_result.json" % arm), encoding="utf-8") as fh:
        return json.load(fh)


def pct(a, q):
    a = sorted(a)
    return a[min(len(a) - 1, int(q * len(a)))]


_TCACHE = {}


def tier_temp(formula):
    """公式 -> (mass,state,temp,mass档,state档,temp档)；温度轴只按层平均（不需要边信息）。"""
    hit = _TCACHE.get(formula)
    if hit is not None:
        return hit
    vec = P.parse_formula(formula)
    atoms = []
    for i, k in enumerate(ELEM_ORDER):
        atoms += [k] * vec[i]
    d = A.molecule_attrs(atoms)
    m, s, t = d["mass"], d["state"], d["temperature"]
    hit = (m, s, t,
           A.tier_name(m, "mass"), A.tier_name(s, "state"), A.tier_name(t, "temperature"))
    _TCACHE[formula] = hit
    return hit


def cell_of(formula):
    m, s, t, mt, st, tt = tier_temp(formula)
    return "·".join((mt, st, tt))


def main():
    data = {a: load(a) for a in ARMS}
    out = {}

    # ---------------------------------------------------------- 1) 总表
    print("=" * 100)
    print("1) 三臂总表")
    rows = []
    for a in ARMS:
        d = data[a]
        s = d["summary"]
        c = s["counts"]
        attempts = c["attempts"]
        rows.append({
            "arm": a,
            "initial_N": s["initial_N"], "final_N": s["final_N"],
            "initial_atoms": s["initial_atoms"], "final_atoms": s["final_atoms"],
            "complete": c["complete"], "incomplete": c["incomplete"],
            "none": c["none"], "inert": c["inert"], "capped": c["capped"],
            "self_skip": c.get("self_skip", 0), "chem_off": c.get("chem_off", 0),
            "attempts": attempts,
            "inert_share": round(c["inert"] / attempts, 4) if attempts else None,
            "complete_share": round((c["complete"] + c["incomplete"]) / attempts, 4) if attempts else None,
            "distinct": s["distinct_formulas"], "new": s["new_substances"],
            "rho_mean": s["rho_final"]["mean"], "rho_std": s["rho_final"]["std"],
            "band": s["band_reaction"],
            "conservation_ok": s["conservation_ok"],
            "runtime_s": s["runtime_s"],
        })
    out["table_summary"] = rows
    for r in rows:
        print("%-7s N %4d->%4d atoms %5d->%5d | react %5d+%-3d none %6d inert %7d(%.0f%%) capped %5d "
              "| distinct %3d new %3d | rho %.3f±%.3f | band %s | %ss" % (
                  r["arm"], r["initial_N"], r["final_N"], r["initial_atoms"], r["final_atoms"],
                  r["complete"], r["incomplete"], r["none"], r["inert"], 100 * (r["inert_share"] or 0),
                  r["capped"], r["distinct"], r["new"], r["rho_mean"], r["rho_std"],
                  r["band"], r["runtime_s"]))

    # ---------------------------------------------------------- 2) 分层
    print("=" * 100)
    print("2) 质量分层：三档 y 均值随时间（0/20/60/120/180/239 分钟）")
    strat = {}
    for a in ARMS:
        ts = data[a]["time_series"]
        idx = [t for t in (0, 20, 60, 120, 180, 239) if t < len(ts)]
        rows = []
        for i in idx:
            r = ts[i]
            ym = r["y_mean"]
            rows.append({"t": r["t"], "N": r["N"],
                         "light": ym["轻"], "mid": ym["中"], "heavy": ym["重"],
                         "rho": r["rho_mean"]})
        strat[a] = rows
        print(" ", a)
        for r in rows:
            print("    t=%3d N=%4d  y 轻=%7.1f 中=%7.1f 重=%7.1f  rho=%.3f" % (
                r["t"], r["N"], r["light"], r["mid"], r["heavy"], r["rho"]))
    out["stratification"] = strat

    # 终态三带组成
    bands = {}
    print("  终态三带（分子数；质量/物态/温度档）：")
    for a in ARMS:
        b = data[a]["bands"]
        band = {}
        for k in ("bottom", "mid", "top"):
            band[k] = {"n": b[k]["n"], "mass": b[k]["mass"],
                       "state": b[k]["state"], "temp": b[k]["temp"]}
            print("   %-6s %-6s n=%4d mass=%s state=%s temp=%s" % (
                a, k, b[k]["n"], b[k]["mass"], b[k]["state"], b[k]["temp"]))
        bands[a] = band
    out["bands"] = bands

    # ---------------------------------------------------------- 3) 恒素场
    print("=" * 100)
    print("3) 恒素场 rho 演化（均值/std/p10/p90）")
    rho_evo = {}
    for a in ARMS:
        ts = data[a]["time_series"]
        idx = [t for t in (0, 20, 60, 120, 180, 239) if t < len(ts)]
        rows = [{"t": ts[i]["t"], "mean": ts[i]["rho_mean"], "std": ts[i]["rho_std"],
                 "p10": ts[i]["rho_p10"], "p90": ts[i]["rho_p90"]} for i in idx]
        rho_evo[a] = rows
        print(" ", a)
        for r in rows:
            print("    t=%3d mean=%.3f std=%.3f p10=%.3f p90=%.3f" % (
                r["t"], r["mean"], r["std"], r["p10"], r["p90"]))
    out["rho_evolution"] = rho_evo

    # 终态 rho 网格 ASCII（从最后一个 snapshot）
    ascii_maps = {}
    for a in ARMS:
        snaps = data[a]["snapshots"]
        rho = snaps[-1]["rho"] if snaps else None
        if not rho:
            continue
        grid = [[rho[ey * EX + ex] for ex in range(EX)] for ey in range(EY)]
        lines = []
        ramp = " .:-=+*#%@"
        for ey in range(EY - 1, -1, -1):   # 上=ey 大
            line = "".join(ramp[min(9, int(grid[ey][ex] * 10))] for ex in range(EX))
            lines.append(line)
        ascii_maps[a] = {"t": snaps[-1]["t"], "lines": lines,
                         "grid": [[round(v, 3) for v in row] for row in grid]}
        print("  终态 rho 图 (%s, t=%d, 上=顶 y=H)：" % (a, snaps[-1]["t"]))
        for ln in lines:
            print("   ", ln)
    out["rho_ascii"] = ascii_maps

    # ---------------------------------------------------------- 4) 反应地理
    print("=" * 100)
    print("4) 反应地理：按 rho 0.1 分桶的 attempts / reactions / 反应率")
    geo = {}
    for a in ARMS:
        g = data[a]["reaction_geography"]
        rows = []
        for b in g:
            att, rea = b["attempts"], b["reactions"]
            rows.append({"rho_bin": b["rho_bin"], "attempts": att, "reactions": rea,
                         "rate": round(rea / att, 4) if att else None})
        geo[a] = rows
        print(" ", a)
        for r in rows:
            print("    rho~%.1f attempts=%7d reactions=%5d rate=%s" % (
                r["rho_bin"], r["attempts"], r["reactions"],
                ("%.3f" % r["rate"]) if r["rate"] is not None else "-"))
    out["reaction_geography"] = geo

    # 反应 y 分布（40 桶 -> 20 桶便于阅读）
    ry = {}
    for a in ARMS:
        h = data[a]["reaction_y_hist"]
        h20 = [sum(h[2 * i:2 * i + 2]) for i in range(20)]
        ry[a] = h20
        print("  %-6s reaction y 直方图(20 桶, 下->上): %s" % (a, h20))
    out["reaction_y_20"] = ry

    # ---------------------------------------------------------- 5) 27 格
    print("=" * 100)
    print("5) 终态 27 格分布（按分子数）")
    cells = {}
    for a in ARMS:
        c27 = data[a]["cells27"]
        tot = sum(c27.values())
        rows = sorted(c27.items(), key=lambda kv: -kv[1])
        cells[a] = {"n_cells": len(c27), "total": tot,
                    "top": [{"cell": k, "n": v, "share": round(v / tot, 4)} for k, v in rows[:10]]}
        print("  %-6s 覆盖 %d/27 格，top10：" % (a, len(c27)))
        for r in cells[a]["top"]:
            print("     %-8s %4d (%.1f%%)" % (r["cell"], r["n"], 100 * r["share"]))
    out["cells27"] = cells

    # ---------------------------------------------------------- 6) 新物质
    print("=" * 100)
    print("6) 新物质（不在 84,225 目录中的产物）")
    catalog = set()
    p = os.path.join(BASE, "t4_catalog_index.json")
    if os.path.exists(p):
        catalog = {r["formula"] for r in json.load(open(p, encoding="utf-8"))}
    newinfo = {}
    for a in ARMS:
        ns = data[a]["new_substances"]
        bad = [f for f in ns if f in catalog]
        atoms_dist = {}
        cell_dist = {}
        for f, v in ns.items():
            atoms_dist[len(v["atoms"])] = atoms_dist.get(len(v["atoms"]), 0) + 1
            cell_dist[cell_of(f)] = cell_dist.get(cell_of(f), 0) + 1
        top = sorted(ns.items(), key=lambda kv: kv[1]["first_t"])[:12]
        newinfo[a] = {
            "count": len(ns),
            "in_catalog": len(bad),
            "atoms_dist": dict(sorted(atoms_dist.items())),
            "cell_dist_top": dict(sorted(cell_dist.items(), key=lambda kv: -kv[1])[:8]),
            "earliest": [{"formula": f, "first_t": v["first_t"], "natoms": len(v["atoms"]),
                          "cell": cell_of(f)} for f, v in top],
        }
        print("  %-6s 新物质 %3d 个，其中在目录内 %d 个 | 原子数分布 %s" % (
            a, len(ns), len(bad), newinfo[a]["atoms_dist"]))
        print("     落格 top: %s" % newinfo[a]["cell_dist_top"])
        print("     最早出现: %s" % [(x["formula"], x["first_t"]) for x in newinfo[a]["earliest"][:6]])
    out["new_substances"] = newinfo

    # ---------------------------------------------------------- 7) 快照交叉验证
    print("=" * 100)
    print("7) 快照检验：局部 rho vs 局部平均温度（热->富集方向）")
    cross = {}
    for a in ARMS:
        snaps = data[a]["snapshots"]
        if not snaps:
            continue
        res = []
        for sn in (snaps[0], snaps[-1]):
            acc = [[0.0, 0] for _ in range(EX * EY)]
            for x, y, f in sn["points"]:
                i = min(EY - 1, int(y / (H / EY))) * EX + min(EX - 1, int(x / (W / EX)))
                t = tier_temp(f)[2]
                acc[i][0] += t
                acc[i][1] += 1
            rho = sn["rho"]
            xs, ys = [], []
            for i in range(EX * EY):
                if acc[i][1]:
                    xs.append(rho[i])
                    ys.append(acc[i][0] / acc[i][1])
            if len(xs) > 2:
                mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
                cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                vx = sum((x - mx) ** 2 for x in xs)
                vy = sum((y - my) ** 2 for y in ys)
                r = cov / (vx * vy) ** 0.5 if vx > 0 and vy > 0 else None
                res.append({"t": sn["t"], "n_cells": len(xs), "r_temp_rho": round(r, 4) if r else None})
        cross[a] = res
        print("  %-6s %s" % (a, res))
    out["snapshot_temp_rho_corr"] = cross

    # ---------------------------------------------------------- 8) 一致性核对
    print("=" * 100)
    print("8) 一致性核对")
    checks = []
    for a in ARMS:
        d = data[a]
        s = d["summary"]
        c = s["counts"]
        ts = d["time_series"]
        # 计数器求和
        for key in ("attempts", "complete", "incomplete", "none", "inert", "capped"):
            v = sum(r[key] for r in ts)
            checks.append({"arm": a, "check": "sum(time_series.%s)" % key,
                           "pass": v == c[key], "detail": "%d vs %d" % (v, c[key])})
        # band 计数和 = N
        nb = sum(d["bands"][k]["n"] for k in ("bottom", "mid", "top"))
        checks.append({"arm": a, "check": "band_sum=N", "pass": nb == s["final_N"],
                       "detail": "%d vs %d" % (nb, s["final_N"])})
        # vertical_hist 和 = N
        vh = sum(d["vertical_hist"]["all"])
        checks.append({"arm": a, "check": "vertical_hist_sum=N", "pass": vh == s["final_N"],
                       "detail": "%d vs %d" % (vh, s["final_N"])})
        # 反应 y 直方图和 = complete+incomplete
        rh = sum(d["reaction_y_hist"])
        checks.append({"arm": a, "check": "reaction_y_sum=react", "pass": rh == c["complete"] + c["incomplete"],
                       "detail": "%d vs %d" % (rh, c["complete"] + c["incomplete"])})
        checks.append({"arm": a, "check": "conservation_ok", "pass": bool(s["conservation_ok"]),
                       "detail": json.dumps(s["conservation"], ensure_ascii=False)})
    out["consistency"] = checks
    for ck in checks:
        print("  %-6s %-26s %s  %s" % (ck["arm"], ck["check"], "PASS" if ck["pass"] else "FAIL", ck["detail"]))

    # ---------------------------------------------------------- 9) 元素/组成概览
    print("=" * 100)
    print("9) 终态组成 top（按分子数）")
    comp = {}
    for a in ARMS:
        fc = data[a]["final_composition"]
        rows = sorted(fc.items(), key=lambda kv: -kv[1]["count"])[:15]
        comp[a] = [{"formula": f, "count": v["count"], "natoms": v["atoms"],
                    "cell": v["cell"]} for f, v in rows]
        print("  %-6s %s" % (a, [(x["formula"], x["count"]) for x in comp[a][:8]]))
    out["final_composition_top"] = comp

    # 元素守恒明细
    out["conservation"] = {a: data[a]["summary"]["conservation"] for a in ARMS}

    path = os.path.join(BASE, "t78_analysis.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("=" * 100)
    print("saved", path)
    return out


if __name__ == "__main__":
    main()
