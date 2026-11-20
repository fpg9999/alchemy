"""T86 切片渲染：同一物质用同一种颜色**填满整格**，相邻同物质合并成大色块。

与 T84 的区别（用户 m02870 第 3 点）：
- 不再画"原子方块骨架"，而是把分子 footprint 的每个格子**整格填成该物质的颜色**；
- 相邻格若属于同一分子式，则不画边界 → 相同颜色连成一个大的色块；
- 不同物质之间才画深色边界线，于是"同物质连通区"一眼可见。
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os

from PIL import Image, ImageDraw

from t84_render import (
    fnt, cells_of, natoms, tiers_of, slice_stats, choose_windows,
    INK, SUB, BG, GRID,
)

BASE = r"G:\AI work\deepseek\work1\alchemy"
RESULT = os.path.join(BASE, "t86_env_tri_result.json")
OUT = os.path.join(BASE, "images", "t86_slices.png")

PALETTE = [
    (222, 88, 74), (240, 150, 52), (214, 194, 70), (128, 176, 66),
    (72, 168, 122), (64, 164, 180), (74, 122, 202), (120, 100, 200),
    (176, 92, 190), (206, 104, 148), (150, 110, 86), (108, 128, 148),
]
_col_cache = {}


def color_of(f):
    c = _col_cache.get(f)
    if c is None:
        h = int(hashlib.md5(f.encode()).hexdigest()[:6], 16)
        c = PALETTE[h % len(PALETTE)]
        # 轻微明度扰动：不同物质之间更容易区分
        k = ((h >> 8) % 5) * 0.045 - 0.09
        c = tuple(max(0, min(255, int(v + 255 * k))) for v in c)
        _col_cache[f] = c
    return c


def occ_map(mols):
    om = {}
    for (r, c, f, k) in mols:
        for cell in cells_of(r, c, f, k):
            om[cell] = f
    return om


def draw_block(img, d, mols, ox, oy, sw, sh, cell, label_top=0):
    om = {}
    for (r, c, f, k) in mols:
        for (rr, cc) in cells_of(r, c, f, k):
            if oy <= rr < oy + sh and ox <= cc < ox + sw:
                om[(rr, cc)] = f
    # 背景网格（空格可见）
    for r in range(sh + 1):
        d.line([(0, r * cell), (sw * cell, r * cell)], fill=GRID)
    for c in range(sw + 1):
        d.line([(c * cell, 0), (c * cell, sh * cell)], fill=GRID)
    # 填色：同物质整格同色
    for (rr, cc), f in om.items():
        x0, y0 = (cc - ox) * cell, (rr - oy) * cell
        d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=color_of(f))
    # 区域边界：只在与"不同物质/空格"相邻处画线 → 同物质合并为大色块
    brd = (48, 48, 56)
    for (rr, cc), f in om.items():
        x0, y0 = (cc - ox) * cell, (rr - oy) * cell
        nb = om.get((rr - 1, cc))
        if nb != f:
            d.line([(x0, y0), (x0 + cell - 1, y0)], fill=brd, width=2)
        nb = om.get((rr + 1, cc))
        if nb != f:
            d.line([(x0, y0 + cell - 1), (x0 + cell - 1, y0 + cell - 1)],
                   fill=brd, width=2)
        nb = om.get((rr, cc - 1))
        if nb != f:
            d.line([(x0, y0), (x0, y0 + cell - 1)], fill=brd, width=2)
        nb = om.get((rr, cc + 1))
        if nb != f:
            d.line([(x0 + cell - 1, y0), (x0 + cell - 1, y0 + cell - 1)],
                   fill=brd, width=2)
    if label_top:
        # 给窗口里最大的几个色块标分子式
        comp = {}
        for (r, c, f, k) in mols:
            if oy <= r < oy + sh and ox <= c < ox + sw:
                comp[f] = comp.get(f, 0) + 1
        top = sorted(comp.items(), key=lambda kv: -kv[1])[:label_top]
        y = 4
        for f, n in top:
            d.rectangle([4, y, 4 + 12, y + 12], fill=color_of(f),
                        outline=(30, 30, 30))
            d.text((20, y - 2), "%s×%d" % (f, n), font=fnt(13), fill=INK)
            y += 17


def draw_slice(mols, W, H, ox, oy, sw, sh, cell):
    img = Image.new("RGB", (sw * cell, sh * cell), BG)
    d = ImageDraw.Draw(img)
    draw_block(img, d, mols, ox, oy, sw, sh, cell, label_top=0)
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1], outline=(50, 50, 58),
                width=2)
    return img


def draw_zoom(mols, W, H, ox, oy, sw, sh, cell):
    img = Image.new("RGB", (sw * cell, sh * cell), BG)
    d = ImageDraw.Draw(img)
    draw_block(img, d, mols, ox, oy, sw, sh, cell, label_top=0)
    # 给 ≥10 原子的物质标式（放在色块中心）
    comp = {}
    for (r, c, f, k) in mols:
        if oy <= r < oy + sh and ox <= c < ox + sw:
            comp.setdefault(f, [0, r, c])
            comp[f][0] += 1
    big = [(f, v) for f, v in comp.items() if natoms(f) >= 10]
    big.sort(key=lambda kv: -natoms(kv[0]))
    for f, (n, r, c) in big[:8]:
        tw = d.textlength(f, font=fnt(13))
        x = min(max(0, (c - ox) * cell - tw / 2), sw * cell - tw - 2)
        y = max(0, (r - oy) * cell - 18)
        d.rectangle([x - 2, y - 1, x + tw + 2, y + 15], fill=(255, 255, 255))
        d.text((x, y), f, font=fnt(13), fill=INK)
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1], outline=(50, 50, 58),
                width=2)
    return img


def draw_map(mols, W, H, w, h):
    cnt = [[0] * W for _ in range(H)]
    for (r, c, f, k) in mols:
        for (rr, cc) in cells_of(r, c, f, k):
            cnt[rr][cc] += 1
    mx = max(1, max(max(row) for row in cnt))
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    sx, sy = w / float(W), h / float(H)
    for r in range(H):
        for c in range(W):
            v = cnt[r][c]
            if not v:
                continue
            t = min(1.0, v / 2.6)
            col = (int(255 - 20 * t), int(236 - 150 * t), int(210 - 150 * t))
            d.rectangle([c * sx, r * sy, (c + 1) * sx - 0.4,
                         (r + 1) * sy - 0.4], fill=col)
    d.rectangle([0, 0, w - 1, h - 1], outline=(80, 80, 88), width=2)
    return img, mx


def pick_windows(mols, W, H, sw, sh):
    """A=最密；B=密度最接近全局均值（远离 A）；C=最稀（≥8 分子）；D=最大分子附近。"""
    cnt = [[0] * W for _ in range(H)]
    for (r, c, f, k) in mols:
        for (rr, cc) in cells_of(r, c, f, k):
            cnt[rr][cc] += 1
    used = sum(1 for row in cnt for v in row if v)
    target = used / float(W * H) * sw * sh
    cands = []
    for oy in range(0, H - sh + 1, max(1, sh // 6)):
        for ox in range(0, W - sw + 1, max(1, sw // 6)):
            s = 0
            for r in range(oy, oy + sh):
                s += sum(cnt[r][ox:ox + sw])
            cands.append((s, ox, oy))
    cands.sort(reverse=True)
    picks = [("A", "最密集区域", cands[0][1], cands[0][2])]
    fa = (picks[0][2], picks[0][3])

    def far(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1]) >= min(sw, sh) * 0.9

    # B：密度最接近全局均值
    best = None
    for s, ox, oy in cands:
        if not far((ox, oy), fa):
            continue
        d = abs(s - target)
        if best is None or d < best[0]:
            best = (d, ox, oy)
    picks.append(("B", "接近平均密度", best[1], best[2]))
    fb = (best[1], best[2])
    # C：最稀
    for s, ox, oy in reversed(cands):
        if s < 8:
            continue
        if far((ox, oy), fa) and far((ox, oy), fb):
            picks.append(("C", "最稀疏区域", ox, oy))
            break
    # D：最大分子附近
    bigs = sorted(mols, key=lambda m: -natoms(m[2]))[:300]
    for (r, c, f, k) in bigs:
        ox = min(max(0, c - sw // 2), W - sw)
        oy = min(max(0, r - sh // 2), H - sh)
        if far((ox, oy), fa) and far((ox, oy), fb):
            picks.append(("D", "最大分子附近", ox, oy))
            break
    if len(picks) < 4:
        picks.append(("D", "最大分子附近", 0, 0))
    return picks, cnt


def render():
    res = json.load(io.open(RESULT, encoding="utf-8"))
    snap = res["snapshots"][-1]
    cfg = res["config"]
    sm = res["summary"]
    W, H = cfg["W"], cfg["H"]
    mols = [tuple(m[:4]) for m in snap["mols"]]
    SW, SH, CELL = 24, 18, 52
    picks, cnt = pick_windows(mols, W, H, SW, SH)

    panels = []
    for (key, desc, ox, oy) in picks:
        img = draw_slice(mols, W, H, ox, oy, SW, SH, CELL)
        st = slice_stats(mols, W, H, ox, oy, SW, SH)
        panels.append((key, desc, ox, oy, st, img))

    mapw, maph = 760, 560
    mimg, mmax = draw_map(mols, W, H, mapw, maph)

    # 放大窗口：取最大分子附近
    bigs = sorted(mols, key=lambda m: -natoms(m[2]))[:300]
    zx = zy = 0
    for (r, c, f, k) in bigs:
        zx = min(max(0, c - 7), W - 14)
        zy = min(max(0, r - 5), H - 10)
        break
    ZSW, ZSH, ZCELL = 14, 10, 66
    zimg = draw_zoom(mols, W, H, zx, zy, ZSW, ZSH, ZCELL)
    zimg.save(os.path.join(BASE, "images", "t86_slice_zoom.png"))

    # 画布
    head_h = 160
    gap = 10
    row_gap = 56
    left_w = SW * CELL * 2 + gap
    left_h = head_h + (SH * CELL) * 2 + row_gap
    right_w = max(mapw, ZSW * ZCELL)
    H_IMG = max(left_h, head_h + maph + 40 + ZSH * ZCELL + 60) + 200
    W_IMG = left_w + right_w + 40
    canvas = Image.new("RGB", (W_IMG, H_IMG), BG)
    d = ImageDraw.Draw(canvas)

    d.text((24, 14), "T86 九元素环境：默认质量阈值 + 三价富集投料 + 多分子反应，同物质同色大色块",
           font=fnt(29, True), fill=INK)
    d.text((24, 56),
           "世界 %d×%d（硬边界）· 投料 %d 分子（三价 O/X/F 各 %.0f%%）· 每格 1 个分子（骨架 k 占 k 格）· "
           "质量阈值 %.2f/%.2f（内核默认）· 1000→10°C 后恒温 %d 拍 · "
           "反应 = resolve，2~%d 分子同组（cap %d）"
           % (W, H, sm["n0"], 100.0 * cfg["feed"]["share"]["O"],
              cfg["thresholds"]["mass"][0], cfg["thresholds"]["mass"][1],
              cfg["ticks"] - cfg["cool_ticks"], cfg["max_group"], cfg["cap"]),
           font=fnt(15), fill=SUB)
    d.text((24, 82),
           "终态 N=%d · 占用 %d 格（%.1f%%）· %d 种物质 · 反应 C%d/I%d/none%d/decomp%d · "
           "新物质 %d · T=%.1f°C"
           % (sm["n_final"], sm["cells_used_final"],
              100.0 * sm["cells_used_final"] / sm["cells_total"],
              snap["n_distinct"], sm["n_complete"], sm["n_incomplete"],
              sm["n_none"], sm["n_decomp"], sm["n_new_species"], snap["T"]),
           font=fnt(15, True), fill=(120, 40, 30))
    d.text((24, 106),
           "质量档 y 均值：轻 %.1f / 中 %.1f / 重 %.1f（行号越小越靠顶）· "
           "团簇 %d 个，最大 %d"
           % (sm["y_mean_mass"][0], sm["y_mean_mass"][1],
              sm["y_mean_mass"][2], sm["clusters"]["n_components"],
              sm["clusters"]["max"]),
           font=fnt(14), fill=SUB)

    # 2×2 切片
    for idx, (key, desc, ox, oy, st, img) in enumerate(panels):
        px = 24 + (idx % 2) * (SW * CELL + gap)
        py = head_h + (idx // 2) * (SH * CELL + row_gap)
        canvas.paste(img, (px, py))
        cap = "%s %s  窗口(%d,%d) %d×%d" % (key, desc, ox, oy, SW, SH)
        d.text((px + 2, py - 46), cap, font=fnt(17, True), fill=INK)
        d.text((px + 2, py - 23),
               "N=%d · %d 格 · 密度 %.1f%% · %d 种 · 平均 %.1f 原子/%.1f 骨架 · 最大团 %d"
               % (st["n"], st["cells"], 100 * st["density"], st["n_distinct"],
                  st["mean_atoms"], st["mean_k"], st["clusters"]["max"]),
               font=fnt(13), fill=SUB)

    # 右侧：密度图 + 放大图
    mx = 24 + left_w + 12
    d.text((mx, head_h - 34), "全环境地图（格占用，越暗越密）", font=fnt(17, True),
           fill=INK)
    canvas.paste(mimg, (mx, head_h))
    for (key, desc, ox, oy, st, img) in panels:
        d.rectangle([mx + ox * mapw // W, head_h + oy * maph // H,
                     mx + (ox + SW) * mapw // W, head_h + (oy + SH) * maph // H],
                    outline=(40, 60, 140), width=2)
        d.text((mx + ox * mapw // W + 4, head_h + oy * maph // H + 3), key,
               font=fnt(15, True), fill=(30, 40, 120))

    zy0 = head_h + maph + 34
    d.text((mx, zy0 - 26), "原地放大 %d×%d 格（同色合并后的色块）" % (ZSW, ZSH),
           font=fnt(17, True), fill=INK)
    canvas.paste(zimg, (mx, zy0))
    d.text((mx, zy0 + ZSH * ZCELL + 4),
           "窗口(%d,%d)；同色=同一物质，连通同色区=相邻同物质合并" % (zx, zy))
    d.text((mx, zy0 + ZSH * ZCELL + 22),
           "颜色由分子式的哈希决定；空格=没有分子", font=fnt(13), fill=SUB)

    # 图例（底部）：最常见物质
    comp = {}
    for m in mols:
        comp[m[2]] = comp.get(m[2], 0) + 1
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:24]
    ly = H_IMG - 160
    d.text((24, ly), "图例：颜色 = 物质（前 24 名，括号内为分子数）", font=fnt(16, True),
           fill=INK)
    x, y = 24, ly + 26
    for i, (f, n) in enumerate(top):
        col = color_of(f)
        d.rectangle([x, y, x + 18, y + 18], fill=col, outline=(40, 40, 46))
        d.text((x + 24, y - 1), "%s(%d)" % (f, n), font=fnt(13), fill=INK)
        x += 24 + 96
        if x > W_IMG - 200:
            x, y = 24, y + 24
    d.text((24, H_IMG - 40),
           "读图：每格最多 1 个分子（k 个骨架占 k 格）；同物质用同一种颜色整格填充，"
           "相邻同物质不画边界 → 连成大色块；不同物质/空格处才画深色边界。",
           font=fnt(14), fill=SUB)

    canvas.save(OUT)
    print("saved", OUT, canvas.size)
    for (key, desc, ox, oy, st, img) in panels:
        img.save(os.path.join(BASE, "images", "t86_slice_%s.png" % key.lower()))
    meta = {"config": cfg, "final_summary": sm,
            "windows": [{"key": k, "desc": d0, "window": [ox, oy, SW, SH],
                         "stats": st} for (k, d0, ox, oy, st, img) in panels],
            "zoom": [zx, zy, ZSW, ZSH]}
    with io.open(os.path.join(BASE, "t86_slices.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    print("saved t86_slices.json")
    return meta


if __name__ == "__main__":
    render()
