"""T87 分析：从团簇跟踪帧里找"有自主移动能力的多分子团"，统计运动规律。

输入：t87_env_asym_result.json（含 track 帧，每 25 拍一帧，簇 size>=3）
输出：t87_analysis.json + 控制台摘要

做法：
1. 帧间匹配：把 t 帧的簇与 t-25 帧的簇按质心距离（<=6 格）与尺寸比
   （0.5~2.0）做贪心匹配，得到 track（同一团簇的时间序列）。
2. 每条 track 计算：帧数、平均尺寸、质心位移、路径长、净位移、
   净位移/路径长（直线度）、平均速度（格/拍）。
3. "自主动 mover"判据（实验性，只看恒温阶段 t>=cool_ticks）：
   帧数 >= 6、平均尺寸 >= 5、平均速度 >= 0.06 格/拍、
   直线度 >= 0.25 —— 即持续朝一个方向漂移，而不是原地抖动。
4. 统计：mover 数量、涉及分子数、速度/尺寸/直线度分布、按尺寸分档。
"""

from __future__ import annotations

import argparse
import io
import json
import math


def load(path):
    return json.load(io.open(path, encoding="utf-8"))


def match_tracks(frames, dt):
    """贪心帧间匹配，返回 tracks: list[dict]。"""
    tracks = []          # 每条: {"pts": [(t, cr, cc, n, A, R, top)]}
    active = []          # 上帧的簇（带 track id）
    for fr in frames:
        t = fr["t"]
        cur = fr["clusters"]
        used = set()
        new_active = []
        # 先按顺序贪心匹配
        for c in cur:
            best = None
            bestd = 1e9
            for j, (prev, tid) in enumerate(active):
                if j in used:
                    continue
                d = math.hypot(c["cr"] - prev["cr"], c["cc"] - prev["cc"])
                if d > 6:
                    continue
                ratio = c["n"] / max(1, prev["n"])
                if ratio < 0.5 or ratio > 2.0:
                    continue
                if d < bestd:
                    bestd = d
                    best = (j, tid)
            if best is not None:
                j, tid = best
                used.add(j)
                tracks[tid]["pts"].append((t, c["cr"], c["cc"], c["n"],
                                           c["A"], c["R"], c["top"],
                                           c.get("mass", 0.0)))
                new_active.append((c, tid))
            else:
                tid = len(tracks)
                tracks.append({"pts": [(t, c["cr"], c["cc"], c["n"],
                                       c["A"], c["R"], c["top"],
                                       c.get("mass", 0.0))]})
                new_active.append((c, tid))
        active = new_active
    return tracks


def track_stats(tr, cool_ticks, dt):
    pts = [p for p in tr["pts"] if p[0] >= cool_ticks]
    if len(pts) < 3:
        return None
    ds = []
    for a, b in zip(pts, pts[1:]):
        ds.append(math.hypot(b[1] - a[1], b[2] - a[2]))
    path = sum(ds)
    net = math.hypot(pts[-1][1] - pts[0][1], pts[-1][2] - pts[0][2])
    span_t = (pts[-1][0] - pts[0][0])   # 单位：拍（t 已是拍数）
    speed = path / span_t if span_t else 0.0
    straight = net / path if path > 1e-9 else 0.0
    sizes = [p[3] for p in pts]
    return {
        "frames": len(pts),
        "t0": pts[0][0], "t1": pts[-1][0],
        "n_mean": round(sum(sizes) / len(sizes), 1),
        "n_min": min(sizes),
        "n_max": max(sizes),
        "path": round(path, 1),
        "net": round(net, 1),
        "speed": round(speed, 4),        # 格/拍
        "straight": round(straight, 3),
        "dx": round(pts[-1][2] - pts[0][2], 1),      # cc：水平
        "dy": round(pts[-1][1] - pts[0][1], 1),      # cr：垂直，正=向下
        "start": [round(pts[0][1], 1), round(pts[0][2], 1)],
        "end": [round(pts[-1][1], 1), round(pts[-1][2], 1)],
        "A_mean": round(sum(p[4] for p in pts) / len(pts), 2),
        "R_mean": round(sum(p[5] for p in pts) / len(pts), 2),
        "mass_mean": round(sum(p[7] for p in pts) / len(pts), 2),
        "top": pts[-1][6],
        "stable": bool((max(sizes) - min(sizes)) <= 0.5 * (sum(sizes) / len(sizes))),
        "dir": ("下沉" if (pts[-1][1] - pts[0][1]) > 0.5 * net else
                "上浮" if (pts[0][1] - pts[-1][1]) > 0.5 * net else "横向"),
        "pts": [[p[0], p[1], p[2], p[3]] for p in pts],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="t87_env_asym_result.json")
    ap.add_argument("--out", default="t87_analysis.json")
    a = ap.parse_args(argv)
    res = load(a.inp)
    cfg = res["config"]
    dt = cfg["track_every"]
    cool = cfg["cool_ticks"]
    frames = res["track"]
    tracks = match_tracks(frames, dt)
    stats = []
    for tr in tracks:
        s = track_stats(tr, cool, dt)
        if s:
            stats.append(s)
    stats.sort(key=lambda s: (-s["n_mean"], -s["speed"]))

    multi = [s for s in stats if s["frames"] >= 6]
    movers = [s for s in multi
              if s["n_mean"] >= 5
              and s["speed"] >= 0.06 and s["straight"] >= 0.25]
    movers.sort(key=lambda s: (-(s["speed"] * s["n_mean"]), -s["straight"]))
    stable_movers = [s for s in movers if s["stable"]]
    stable_movers.sort(key=lambda s: (-s["net"], -s["speed"]))
    dirs = {}
    for s in movers:
        dirs[s["dir"]] = dirs.get(s["dir"], 0) + 1

    n_live = res["summary"]["n0"]
    frac_movers = (sum(s["n_mean"] for s in movers) / n_live) if n_live else 0.0
    # 尺寸分档速度
    buckets = {"3-4": [], "5-9": [], "10-19": [], "20-49": [], "50+": []}
    for s in stats:
        n = s["n_mean"]
        key = ("3-4" if n < 5 else "5-9" if n < 10 else "10-19" if n < 20
               else "20-49" if n < 50 else "50+")
        buckets[key].append(s["speed"])
    bucket_stat = {k: {"n": len(v),
                       "mean": round(sum(v) / len(v), 4) if v else None,
                       "p90": (round(sorted(v)[int(0.9 * (len(v) - 1))], 4)
                               if v else None)}
                   for k, v in buckets.items()}
    out = {
        "config": {"track_every": dt, "cool_ticks": cool,
                   "n_frames": len(frames), "n_tracks": len(tracks),
                   "mover_rule": "frames>=6, n_mean>=5, speed>=0.06, straight>=0.25"},
        "summary": {
            "n_tracks": len(stats),
            "n_multi": len(multi),
            "n_movers": len(movers),
            "n_stable_movers": len(stable_movers),
            "dir_counts": dirs,
            "molecules_in_movers": round(sum(s["n_mean"] for s in movers), 1),
            "frac_molecules_in_movers": round(frac_movers, 3),
            "speed_mean_all": round(sum(s["speed"] for s in stats) / len(stats), 4)
            if stats else None,
        },
        "buckets": bucket_stat,
        "movers": movers[:80],
        "stable_movers": stable_movers[:40],
        "all": stats[:2000],
    }
    with io.open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print("frames=%d tracks=%d movers=%d (%.1f%% molecules)"
          % (len(frames), len(stats), len(movers), 100 * frac_movers))
    print("speed by size:", json.dumps(bucket_stat, ensure_ascii=False))
    for s in movers[:8]:
        print("mover: n=%.1f t=%d..%d speed=%.3f straight=%.2f net=%.1f "
              "dx=%.1f dy=%.1f top=%s"
              % (s["n_mean"], s["t0"], s["t1"], s["speed"], s["straight"],
                 s["net"], s["dx"], s["dy"], s["top"]))
    top = movers[0] if movers else None
    if top:
        print("TOP mover path:", [[p[0], round(p[1], 0), round(p[2], 0)]
                                  for p in top["pts"]])
    print("saved", a.out)


if __name__ == "__main__":
    main()
