# -*- coding: utf-8 -*-
"""T89 在 T88 群系里找"类似生命、能自主行动"的物质/分子团簇。

输入：t88_env_*.json（含 track 帧：每 25 拍一帧、簇 size>=3）
输出：t89_life.json

判定（只看恒温阶段 t>=cool_ticks）：
  mover（自主移动团）：frames>=4, n_mean>=4, speed>=0.06 格/拍, straight>=0.25
  growth（生长团）   ：frames>=3, n_end >= 1.5*n_start
  division（分裂事件）：track 结束后一帧，在末质心附近出现 2+ 个尺寸合计≈原尺寸的簇
  colony（驻留反应团）：n_mean>=80, frames>=6, speed<0.05

life_score = min(1,frames/8) * min(1,n_mean/10)**0.5
             * min(1, speed/0.12) * straight
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import t87_analyze as A87

BIOMES = ["B3_OFL", "B3_OXC", "B4_OXKF", "B5_OXKAF", "B6_OXCKAF", "B9_all9"]


def load(name):
    p = os.path.join(BASE, "t88_env_%s.json" % name.lower())
    return json.load(io.open(p, encoding="utf-8"))


def frames_by_t(frames):
    return {fr["t"]: fr["clusters"] for fr in frames}


def match(frames, dt):
    return A87.match_tracks(frames, dt)


def stat(tr, cool):
    return A87.track_stats(tr, cool, dt=25)


def find_divisions(tracks, fbt, dt, cool):
    out = []
    for tid, tr in enumerate(tracks):
        pts = [p for p in tr["pts"] if p[0] >= cool]
        if len(pts) < 2:
            continue
        t_end, cr, cc, n = pts[-1][0], pts[-1][1], pts[-1][2], pts[-1][3]
        nxt = fbt.get(t_end + dt)
        if not nxt:
            continue
        kids = [c for c in nxt
                if math.hypot(c["cr"] - cr, c["cc"] - cc) <= 10]
        if len(kids) < 2:
            continue
        tot = sum(c["n"] for c in kids)
        if tot > 1.6 * n or tot < 0.6 * n:
            continue
        big = [c for c in kids if c["n"] >= 0.2 * n]
        if len(big) < 2:
            continue
        out.append({
            "tid": tid, "t": t_end, "n": n, "cr": round(cr, 1), "cc": round(cc, 1),
            "kids": [[round(c["cr"], 1), round(c["cc"], 1), c["n"],
                      c.get("top", [])[:2]] for c in big],
        })
    return out


def main():
    out = {"config": {
        "rule": "mover: frames>=4, n_mean>=4, speed>=0.06, straight>=0.25; "
                "growth: n_end>=1.5*n_start; division: kids within 10 cells, "
                "total 0.6~1.6n; colony: n_mean>=80, frames>=6, speed<0.05",
        "phase": "steady (t>=cool_ticks)"}, "biomes": []}

    for name in BIOMES:
        r = load(name)
        cfg = r["config"]
        cool = cfg["cool_ticks"]
        frames = r["track"]
        fbt = frames_by_t(frames)
        tracks = match(frames, 25)
        stats = []
        for tr in tracks:
            s = stat(tr, cool)
            if s:
                s["tid"] = len(stats)
                s["biome"] = name
                stats.append(s)

        movers = [s for s in stats if s["frames"] >= 4 and 4 <= s["n_mean"] <= 64
                  and s["speed"] >= 0.06 and s["straight"] >= 0.25]
        for s in movers:
            s["life_score"] = round(
                min(1, s["frames"] / 8.0) * min(1, s["n_mean"] / 10.0) ** 0.5
                * min(1, s["speed"] / 0.12) * s["straight"], 3)
        movers.sort(key=lambda s: -s["life_score"])

        growth = [s for s in stats if s["frames"] >= 3 and s["n_max"] <= 64
                  and s["n_max"] >= 1.5 * s["n_min"]]
        growth.sort(key=lambda s: -(s["n_max"] / max(1, s["n_min"])))
        colonies = [s for s in stats if s["n_mean"] >= 80 and s["frames"] >= 6
                    and s["speed"] < 0.05]
        colonies.sort(key=lambda s: -s["n_mean"])
        divs = find_divisions(tracks, fbt, 25, cool)

        # 每群系最佳候选：优先 life_score，其次尺寸
        best = movers[:5]
        out["biomes"].append({
            "biome": name,
            "label": r["config"]["desc"],
            "subset": cfg["subset"],
            "n_final": r["summary"]["n_final"],
            "n_tracks": len(stats),
            "n_multi": sum(1 for s in stats if s["frames"] >= 6),
            "n_movers": len(movers),
            "molecules_in_movers": round(sum(s["n_mean"] for s in movers), 1),
            "frac_in_movers": round(sum(s["n_mean"] for s in movers)
                                    / max(1, r["summary"]["n_final"]), 3),
            "dir": {d: sum(1 for s in movers if s["dir"] == d)
                    for d in ("上浮", "横向", "下沉")},
            "n_growth": len(growth),
            "n_divisions": len(divs),
            "n_colonies": len(colonies),
            "movers": best,
            "growth": growth[:5],
            "divisions": divs[:5],
            "colonies": colonies[:3],
        })
        top = best[0] if best else None
        print("[%s] tracks=%d movers=%d growth=%d div=%d colony=%d%s"
              % (name, len(stats), len(movers), len(growth), len(divs),
                 len(colonies),
                 ("  best: n=%.1f v=%.3f s=%.2f top=%s"
                  % (top["n_mean"], top["speed"], top["straight"], top["top"]))
                 if top else ""))

    io.open(os.path.join(BASE, "t89_life.json"), "w",
            encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    print("saved t89_life.json")


if __name__ == "__main__":
    main()
