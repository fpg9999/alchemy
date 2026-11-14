# -*- coding: utf-8 -*-
"""T13 汇总分析：候选统计 / 投料原子数 vs 最大产物尺寸 / 命中率 / 记录 / 图。

输出：
  t13_big_search.json   全部候选与结果 + 统计 + embed 结果 + 记录
  t13_scatter.png       投料总原子 vs 最大产物分子尺寸（散点）
  t13_bins.png          按投料区间的最佳/中位最大产物尺寸
"""
import sys, os, json, math
from collections import defaultdict

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)

FILES = ["t13_results.jsonl", "t13_results_grow.jsonl", "t13_results_target.jsonl", "t13_results_grow2.jsonl"]
OUT_JSON = os.path.join(HERE, "t13_big_search.json")

# lead 提供的超大投料结果（V140×3 / ×4），结构在 t13_scale3/4.json
LEAD_GIANT = [
    {"n": 420, "scale": 3, "max": 258, "sizes": [258, 66, 42, 27, 27],
     "formula": "O55X46P92K19A46", "source": "lead: V140×3, t13_scale3.json"},
    {"n": 560, "scale": 4, "max": 346, "sizes": [346, 75, 72, 40, 27],
     "formula": "O72X64P120W4K26A58F2", "source": "lead: V140×4, t13_scale4.json"},
]


def load_results():
    recs = []
    for fn in FILES:
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            r["phase"] = r.get("phase", "?")
            recs.append(r)
    return recs


def load_json(fn, default):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def stats_block(rows):
    ok = [r for r in rows if r.get("ok")]
    n = len(rows)
    small = [r for r in ok if r["max"] <= 16]
    single = [r for r in ok if r.get("nmols") == 1]
    rec140 = [r for r in ok if r["max"] > 140]
    rec143 = [r for r in ok if r["max"] > 143]
    return {
        "candidates": n,
        "ok": len(ok),
        "fail_rem_or_parity": n - len(ok),
        "ok_rate": round(len(ok) / n, 4) if n else None,
        "single_molecule": len(single),
        "single_molecule_rate": round(len(single) / n, 4) if n else None,
        "max_product_size": max((r["max"] for r in ok), default=0),
        "median_max_product_size": sorted(r["max"] for r in ok)[len(ok) // 2] if ok else 0,
        "hits_gt140": len(rec140),
        "hits_gt143": len(rec143),
        "hit_rate_gt140": round(len(rec140) / n, 5) if n else None,
        "sum_sim_s": round(sum(r.get("t", 0) for r in rows), 1),
    }


def bins_block(rows):
    edges = [(120, 140), (140, 160), (160, 200), (200, 250), (250, 300),
             (300, 350), (350, 420), (420, 500), (500, 10000)]
    out = []
    for lo, hi in edges:
        sub = [r for r in rows if lo <= r["n"] < hi]
        ok = [r for r in sub if r.get("ok")]
        if not sub:
            continue
        mxs = sorted(r["max"] for r in ok)
        out.append({
            "n_range": f"{lo}-{hi-1}" if hi < 10000 else f"{lo}+",
            "candidates": len(sub),
            "ok": len(ok),
            "ok_rate": round(len(ok) / len(sub), 4),
            "best_max": max(mxs) if mxs else 0,
            "median_max": mxs[len(mxs) // 2] if mxs else 0,
            "p90_max": mxs[int(0.9 * (len(mxs) - 1))] if mxs else 0,
            "single_molecule": sum(1 for r in ok if r.get("nmols") == 1),
            "gt140": sum(1 for r in sub if r["max"] > 140),
            "avg_sim_s": round(sum(r.get("t", 0) for r in sub) / len(sub), 2),
        })
    return out


def spearman(xs, ys):
    import numpy as np
    rx = np.argsort(np.argsort(xs))
    ry = np.argsort(np.argsort(ys))
    return float(np.corrcoef(rx, ry)[0, 1])


def make_scatter(rows, giant, path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1500, 950
    L, R, T, B = 110, 60, 70, 90
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    try:
        import glob
        cands = []
        for pat in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
                    "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc",
                    "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"):
            if os.path.exists(pat):
                cands.append(pat)
        cjk = [p for p in cands if any(k in p for k in ("msyh", "simhei", "simsun"))]
        fpath = (cjk + cands)[0] if cands else "arial.ttf"
        bold = "C:/Windows/Fonts/msyhbd.ttc"
        fbpath = bold if os.path.exists(bold) else fpath
        f = ImageFont.truetype(fpath, 20)
        fb = ImageFont.truetype(fbpath, 26)
        fs = ImageFont.truetype(fpath, 17)
    except Exception:
        f = fb = fs = ImageFont.load_default()
    xs = [r["n"] for r in rows] + [g["n"] for g in giant]
    ys = [r["max"] for r in rows] + [g["max"] for g in giant]
    xmin, xmax = 100, max(320, max(xs) + 20)
    ymin, ymax = 0, max(300, max(ys) + 20)
    px = lambda x: L + (x - xmin) / (xmax - xmin) * (W - L - R)
    py = lambda y: H - B - (y - ymin) / (ymax - ymin) * (H - T - B)
    # 网格
    for gy in range(0, ymax + 1, 50):
        d.line([(L, py(gy)), (W - R, py(gy))], fill=(230, 230, 230))
        d.text((L - 55, py(gy) - 9), str(gy), font=fs, fill=(60, 60, 60))
    for gx in range(100, xmax + 1, 50):
        d.line([(px(gx), T), (px(gx), H - B)], fill=(238, 238, 238))
        d.text((px(gx) - 15, H - B + 8), str(gx), font=fs, fill=(60, 60, 60))
    # 参考线
    for y, col, lab in ((140, (220, 120, 0), "140 原纪录"), (155, (200, 0, 0), "155 本次验证纪录")):
        d.line([(L, py(y)), (W - R, py(y))], fill=col, width=2)
        d.text((W - R - 210, py(y) - 22), lab, font=fs, fill=col)
    colors = {"seed": (60, 90, 200), "rand": (40, 160, 90), "target": (230, 130, 20), "grow2": (120, 80, 200),
              "adapt": (150, 60, 180), "grow": (0, 150, 150)}
    for r in rows:
        c = colors.get(r["phase"], (100, 100, 100))
        x, y = px(r["n"]), py(r["max"])
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=c)
    for g in giant:
        x, y = px(g["n"]), py(g["max"])
        d.polygon([(x, y - 9), (x + 9, y), (x, y + 9), (x - 9, y)], fill=(200, 0, 0))
        d.text((x + 12, y - 20), f"{g['max']}", font=fs, fill=(180, 0, 0))
    d.text((L, 20), "T13 投料总原子数 vs 最大产物分子尺寸（pot_v3, 每条=一种投料）", font=fb, fill=(0, 0, 0))
    d.text((W // 2 - 120, H - 40), "投料总原子数", font=f, fill=(0, 0, 0))
    d.text((20, T + 200), "最大产物分子尺寸", font=f, fill=(0, 0, 0))
    lx = W - R - 280
    for i, (lab, key) in enumerate([("seed(V140 变体)", "seed"), ("rand(随机大投料)", "rand"),
                                    ("target(易摆放盆地)", "target")]):
        d.rectangle([lx, T + 10 + i * 26, lx + 14, T + 24 + i * 26], fill=colors[key])
        d.text((lx + 20, T + 8 + i * 26), lab, font=fs, fill=(0, 0, 0))
    d.polygon([(lx + 7, T + 92), (lx + 15, T + 100), (lx + 7, T + 108), (lx - 1, T + 100)], fill=(200, 0, 0))
    d.text((lx + 20, T + 90), "lead V140×3/×4", font=fs, fill=(0, 0, 0))
    img.save(path)
    return path


def main():
    rows = load_results()
    by_phase = defaultdict(list)
    for r in rows:
        by_phase[r["phase"]].append(r)
    phase_stats = {k: stats_block(v) for k, v in by_phase.items()}
    phase_stats["all"] = stats_block(rows)

    # 投料区间表（主线：全部候选；另给 rand-only 表）
    bins_all = bins_block(rows)
    bins_rand = bins_block([r for r in rows if r["phase"] == "rand"])
    bins_seed = bins_block([r for r in rows if r["phase"] == "seed"])

    ok = [r for r in rows if r.get("ok")]
    top = sorted(ok, key=lambda r: -r["max"])[:25]
    top_out = [{"max": r["max"], "n": r["n"], "phase": r["phase"], "label": r["label"],
                "nmols": r["nmols"], "formula": r["formula"], "vec": r["vec"], "t": r["t"]}
               for r in top]
    # 单产物（整锅=1 分子）记录
    singles = sorted([r for r in ok if r.get("nmols") == 1], key=lambda r: -r["max"])[:20]
    singles_out = [{"max": r["max"], "n": r["n"], "phase": r["phase"], "label": r["label"],
                    "formula": r["formula"], "vec": r["vec"]} for r in singles]

    embed_initial = load_json("t13_embed.json", [])
    embed_screen = load_json("t13_embed_screen.json", [])
    embed_giant3 = load_json("t13_embed_giant_scale3.json", [])
    embed_giant4 = load_json("t13_embed_giant_scale4.json", [])
    record_full_verify = load_json("t13_record_full_verify.json", [])

    def slim(d):
        e = {k: v for k, v in d.items() if k != "structure"}
        if "structure" in d:
            e["has_structure"] = True
        return e

    verified = [slim(d) for d in embed_initial + embed_screen if d.get("status") == "ok"]
    verified.sort(key=lambda d: -d["max"])
    attempted = [slim(d) for d in embed_initial + embed_screen]

    # 动态可生成（模拟层面） vs 已验证可摆放
    dyn_max = max([r["max"] for r in ok] + [g["max"] for g in LEAD_GIANT])
    legal_max = max((d["max"] for d in verified), default=0)
    corr = None
    if len(rows) > 5:
        corr = round(spearman([r["n"] for r in rows], [r["max"] for r in rows]), 3)

    out = {
        "task": "T13 更大分子搜索与反应尺寸上界验证",
        "simulator": "pot_v3.simulate (rules 1~9)；摆放校验 pot_v2.embed_mol2 + validate_place",
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "counts": {
            "total_candidates": len(rows),
            "phases": {k: len(v) for k, v in by_phase.items()},
            "total_sim_seconds": round(sum(r.get("t", 0) for r in rows), 1),
        },
        "phase_stats": phase_stats,
        "bins_all": bins_all,
        "bins_rand_only": bins_rand,
        "bins_seed_only": bins_seed,
        "spearman_n_vs_max": corr,
        "top25_max": top_out,
        "single_molecule_top": singles_out,
        "lead_giant_feeds": LEAD_GIANT,
        "dynamic_max_graph": dyn_max,
        "verified_legal_max": legal_max,
        "embed": {
            "initial": attempted,
            "screen": [slim(d) for d in embed_screen],
            "giant": [slim(d) for d in embed_giant3 + embed_giant4],
        },
        "verified_records": verified,
        "record_full_verify": record_full_verify,
        "limitations": [
            "「摆放失败」只表示在给定 max_nodes 预算内没找到合法摆放，不是不可能性证明。",
            "「反应生成」的分子图尺寸随投料增长（本报告到 346），但可摆放合法物质目前只验证到 155。",
            "候选是基于总向量采样（总向量决定律），未覆盖全部 9 维空间；随机族样本有限（n=172）。",
            "产品的可摆放性只对最大分子（以及记录投料的全部产物）做了严格校验，不是对整个产物集的完备枚举。",
        ],
        "all_candidates": [
            {k: r[k] for k in ("vec", "n", "phase", "label", "ok", "nmols", "max", "formula", "t")}
            for r in rows
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("wrote", OUT_JSON, os.path.getsize(OUT_JSON), "bytes")
    print(json.dumps({k: out[k] for k in ("counts", "phase_stats", "spearman_n_vs_max",
                                          "dynamic_max_graph", "verified_legal_max")},
                     ensure_ascii=False, indent=1))
    print("\nbins_all:")
    for b in bins_all:
        print(" ", b)
    print("\nbins_rand_only:")
    for b in bins_rand:
        print(" ", b)

    # 图（巨图数据来自 lead）
    giant = [{"n": g["n"], "max": g["max"]} for g in LEAD_GIANT]
    make_scatter(rows, giant, os.path.join(HERE, "t13_scatter.png"))
    print("wrote t13_scatter.png")


if __name__ == "__main__":
    main()
