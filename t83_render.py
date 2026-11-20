"""T83 渲染：三轴环境（质量/物态/温度 + 三素力）的骨架方块切片。

与 T82 渲染的区别
------------------
1) **每个分子恰好占一个单位方格**：骨架图标被统一缩放到 1.0 格内（不再跨越邻居格子）；
2) 切片按"三轴生效后的环境"选取（22x16 格，cell=60），并给出三轴档位构成；
3) 右侧：全环境密度图 + 恒素场 rho（温度轴，10x20 网格）+ 原地放大（14x10 格，cell=68）。
"""

from __future__ import annotations

import io
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

from alchemy import attrs as ATTR
from alchemy.core.elements import classify_offset, ORDER as ELEM_ORDER

BASE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.environ.get("T83_RESULT") or os.path.join(BASE, "t83_env_result.json")
CATALOG = os.path.join(BASE, "t4_catalog_all_validated.json")
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

SQ3 = math.sqrt(3.0)
SPRITE_S = 0.55
ATOM_FRAC = 0.42
ICON_MAX_CELLS = 1.00          # 图标整体正好占一个格子

COL = {
    "O": (214, 69, 69), "K": (224, 142, 43), "P": (154, 168, 37),
    "X": (47, 111, 208), "W": (47, 168, 184), "A": (63, 163, 95),
    "F": (180, 79, 191), "L": (122, 92, 196), "C": (128, 128, 140),
}
BG = (250, 249, 246)
GRID = (228, 225, 218)
INK = (40, 40, 46)
SUB = (90, 90, 100)
LINE = (55, 55, 62)
TIER_CN = {"mass": ("轻", "中", "重"), "state": ("气", "液", "固"),
           "temperature": ("冷", "温", "热")}


def fnt(size, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    except Exception:
        return ImageFont.load_default()


def load_catalog():
    cat = json.load(io.open(CATALOG, encoding="utf-8"))
    return {r["formula"]: r for r in cat}


_comp_cache = {}
_natoms_cache = {}
_tier_cache = {}


def parse_comp(f):
    if f in _comp_cache:
        return _comp_cache[f]
    d = {}
    i = 0
    while i < len(f):
        ch = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        d[ch] = d.get(ch, 0) + (int(num) if num else 1)
    _comp_cache[f] = d
    return d


def natoms(f):
    if f not in _natoms_cache:
        _natoms_cache[f] = sum(parse_comp(f).values())
    return _natoms_cache[f]


def tiers_of(f, cat):
    """返回 (mass_tier, state_tier, temp_tier)，0/1/2；读不到按元素计数估算。"""
    if f in _tier_cache:
        return _tier_cache[f]
    rec = cat.get(f)
    if rec:
        atoms = tuple(rec["atoms"])
        edges = [tuple(e) for e in rec["edges"]]
    else:
        atoms = []
        for e in ELEM_ORDER:
            atoms.extend([e] * parse_comp(f).get(e, 0))
        edges = []
    at = ATTR.molecule_attrs(atoms, edges)
    prop = ATTR.property_of(at)
    g = {"低": 0, "中": 1, "高": 2}
    out = (g[prop["grades"]["mass"]], g[prop["grades"]["state"]],
           g[prop["grades"]["temperature"]])
    _tier_cache[f] = out
    return out


# ---------------------------------------------------------------------------
# 骨架 sprite（单位 = 格）
# ---------------------------------------------------------------------------

def sprite_for(rec):
    place = {int(k): (v[0], v[1]) for k, v in rec["place"].items()}
    xy = {i: (SQ3 * (q + r / 2.0), 1.5 * r) for i, (q, r) in place.items()}
    n = len(rec["atoms"])
    cx = sum(v[0] for v in xy.values()) / n
    cy = sum(v[1] for v in xy.values()) / n
    off = {i: ((x - cx) * SPRITE_S, (y - cy) * SPRITE_S) for i, (x, y) in xy.items()}
    atoms = [(rec["atoms"][i], off[i][0], off[i][1]) for i in range(n)]
    bonds = []
    for e in rec["edges"]:
        i, j = int(e[0]), int(e[1])
        q1, r1 = place[i]
        q2, r2 = place[j]
        kind = classify_offset((q2 - q1, r2 - r1))
        bonds.append((off[i][0], off[i][1], off[j][0], off[j][1], kind))
    return atoms, bonds, n


_sprite_cache = {}


def get_sprite(rec):
    key = rec["formula"]
    if key not in _sprite_cache:
        _sprite_cache[key] = sprite_for(rec)
    return _sprite_cache[key]


def draw_bond(d, x1, y1, x2, y2, kind, w, color=LINE):
    w = max(1, int(w))
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    if kind == "S":
        d.line([(int(x1), int(y1)), (int(x2), int(y2))], fill=color, width=w)
    elif kind == "C":
        seg, gap = max(2.0, w * 2.0), max(1.5, w * 1.5)
        t = 0.0
        while t < L:
            t2 = min(L, t + seg)
            d.line([(int(x1 + ux * t), int(y1 + uy * t)),
                    (int(x1 + ux * t2), int(y1 + uy * t2))],
                   fill=color, width=w)
            t = t2 + gap
    else:
        dot, gap = max(1.0, w * 0.9), max(2.2, w * 1.6)
        t = 0.0
        while t < L:
            d.ellipse([x1 + ux * t - dot / 2, y1 + uy * t - dot / 2,
                       x1 + ux * t + dot / 2, y1 + uy * t + dot / 2], fill=color)
            t += dot + gap


def draw_molecule(d, cx, cy, rec, cell, max_cells=ICON_MAX_CELLS):
    """画在一个格子内：**统一图标大小** —— 每个骨架都缩放到占满 max_cells 格。"""
    atoms, bonds, n = get_sprite(rec)
    ext = 0.0
    for (el, dx, dy) in atoms:
        ext = max(ext, abs(dx), abs(dy))
    s = (max_cells / 2.0) / ext if ext > 1e-9 else 1.0
    blk = max(2.4, min(cell * 0.28, s * cell * 0.34))
    for (ax1, ay1, ax2, ay2, kind) in bonds:
        draw_bond(d, cx + ax1 * s * cell, cy + ay1 * s * cell,
                  cx + ax2 * s * cell, cy + ay2 * s * cell, kind,
                  max(1.0, min(cell * 0.09, s * cell * 0.09)))
    r = blk / 2.0
    wpx = 1 if blk < 7 else 2
    for (el, dx, dy) in atoms:
        x, y = cx + dx * s * cell, cy + dy * s * cell
        col = COL.get(el, (120, 120, 120))
        d.rectangle([int(round(x - r)), int(round(y - r)),
                     int(round(x + r)), int(round(y + r))],
                    fill=col, outline=(35, 35, 40), width=wpx)
    return n


# ---------------------------------------------------------------------------
# 窗口选择 / 统计 / 绘制
# ---------------------------------------------------------------------------

def density_map(mols, W, H):
    dens = [[0] * W for _ in range(H)]
    for (r, c, f) in mols:
        dens[r][c] += 1
    return dens


def win_score(dens, H, W, ox, oy, sw, sh):
    s = 0
    for r in range(oy, oy + sh):
        row = dens[r]
        for c in range(ox, ox + sw):
            s += row[c]
    return s


def choose_windows(mols, W, H, sw, sh):
    dens = density_map(mols, W, H)
    cands = []
    for oy in range(0, H - sh + 1, max(1, sh // 4)):
        for ox in range(0, W - sw + 1, max(1, sw // 4)):
            cands.append((win_score(dens, H, W, ox, oy, sw, sh), ox, oy))
    cands.sort(reverse=True)
    picks = []
    min_dist = min(sw, sh) * 0.8

    def far(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1]) >= min_dist

    picks.append(("A", "最密集区域", cands[0][1], cands[0][2], cands[0][0]))
    mid = cands[len(cands) // 2]
    chosen = None
    for s, ox, oy in cands[len(cands) // 2:]:
        if far((ox, oy), (picks[0][2], picks[0][3])):
            chosen = (ox, oy, s)
            break
    chosen = chosen or (mid[1], mid[2], mid[0])
    picks.append(("B", "中等密度区域", chosen[0], chosen[1], chosen[2]))
    chosen = None
    for s, ox, oy in reversed(cands):
        if s < 10:
            continue
        if (far((ox, oy), (picks[0][2], picks[0][3]))
                and far((ox, oy), (picks[1][2], picks[1][3]))):
            chosen = (ox, oy, s)
            break
    chosen = chosen or (0, 0, 0)
    picks.append(("C", "最稀疏区域", chosen[0], chosen[1], chosen[2]))
    prev = [(p[2], p[3]) for p in picks]
    bigs = sorted(mols, key=lambda m: -natoms(m[2]))[:400]
    chosen = None
    for (r, c, f) in bigs:
        ox = min(max(0, c - sw // 2), W - sw)
        oy = min(max(0, r - sh // 2), H - sh)
        if all(far((ox, oy), p) for p in prev):
            chosen = (ox, oy)
            break
    if chosen is None:
        chosen = (max(0, W - sw), max(0, H - sh))
    ox, oy = chosen
    picks.append(("D", "最大分子附近", ox, oy,
                  win_score(dens, H, W, ox, oy, sw, sh)))
    return picks, dens


def slice_stats(mols, W, H, ox, oy, sw, sh, cat):
    sub = [(r, c, f) for (r, c, f) in mols
           if oy <= r < oy + sh and ox <= c < ox + sw]
    comp = {}
    tiers = {"mass": [0, 0, 0], "state": [0, 0, 0], "temperature": [0, 0, 0]}
    atoms_total = 0
    for (r, c, f) in sub:
        comp[f] = comp.get(f, 0) + 1
        atoms_total += natoms(f)
        mt, st, tt = tiers_of(f, cat)
        tiers["mass"][mt] += 1
        tiers["state"][st] += 1
        tiers["temperature"][tt] += 1
    n = max(1, len(sub))
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    cellset = {(r, c): f for (r, c, f) in sub}
    seen = set()
    sizes = []
    for p in cellset:
        if p in seen:
            continue
        stack = [p]
        seen.add(p)
        k = 0
        while stack:
            q = stack.pop()
            k += 1
            r, c = q
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nb = (r + dr, c + dc)
                    if nb in cellset and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        sizes.append(k)
    sizes.sort(reverse=True)
    return {
        "window": [ox, oy, sw, sh],
        "n": len(sub),
        "density": round(len(sub) / float(sw * sh), 4),
        "n_distinct": len(comp),
        "mean_atoms": round(atoms_total / n, 2) if sub else 0.0,
        "top": top,
        "tiers": {k: [round(v / n, 3) for v in vals] for k, vals in tiers.items()},
        "clusters": {"n_components": len(sizes),
                     "max": sizes[0] if sizes else 0,
                     "in_big": sum(s for s in sizes if s >= 3)},
    }


def draw_slice_image(mols, W, H, ox, oy, sw, sh, cell, cat):
    img = Image.new("RGB", (sw * cell, sh * cell), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i in range(sw + 1):
        d.line([(i * cell, 0), (i * cell, sh * cell)], fill=GRID, width=1)
    for j in range(sh + 1):
        d.line([(0, j * cell), (sw * cell, j * cell)], fill=GRID, width=1)
    sub = [(r, c, f) for (r, c, f) in mols
           if oy <= r < oy + sh and ox <= c < ox + sw]
    sub.sort(key=lambda m: natoms(m[2]))
    for (r, c, f) in sub:
        rec = cat.get(f)
        cx = (c - ox) * cell + cell / 2.0
        cy = (r - oy) * cell + cell / 2.0
        if rec:
            draw_molecule(d, cx, cy, rec, cell)
        else:
            rr = cell * 0.20
            d.rectangle([cx - rr, cy - rr, cx + rr, cy + rr],
                        fill=(150, 150, 150), outline=(60, 60, 60))
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1], outline=(60, 60, 70), width=2)
    return img


def draw_zoom(mols, W, H, ox, oy, sw, sh, cell, cat):
    img = Image.new("RGB", (sw * cell, sh * cell), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i in range(sw + 1):
        d.line([(i * cell, 0), (i * cell, sh * cell)], fill=(236, 233, 226), width=1)
    for j in range(sh + 1):
        d.line([(0, j * cell), (sw * cell, j * cell)], fill=(236, 233, 226), width=1)
    sub = [(r, c, f) for (r, c, f) in mols
           if oy <= r < oy + sh and ox <= c < ox + sw]
    sub.sort(key=lambda m: natoms(m[2]))
    labels = []
    for (r, c, f) in sub:
        rec = cat.get(f)
        cx = (c - ox) * cell + cell / 2.0
        cy = (r - oy) * cell + cell / 2.0
        if rec:
            draw_molecule(d, cx, cy, rec, cell)
        else:
            rr = cell * 0.20
            d.rectangle([cx - rr, cy - rr, cx + rr, cy + rr],
                        fill=(150, 150, 150), outline=(60, 60, 60))
        if natoms(f) >= 9:
            labels.append((cx, cy, f))
    lf = fnt(15)
    placed = []
    for (cx, cy, f) in labels:
        if len(placed) >= 7:
            break
        tw = d.textlength(f, font=lf)
        th = 18
        x = min(max(2.0, cx + cell * 0.42), sw * cell - 2 - tw)
        y = min(max(2.0, cy - cell * 0.70), sh * cell - 2 - th)
        box = (x, y, x + tw, y + th)
        if any(not (box[2] < b[0] or b[2] < box[0]
                    or box[3] < b[1] or b[3] < box[1]) for b in placed):
            continue
        placed.append(box)
        d.text((x, y), f, font=lf, fill=(25, 25, 35))
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1], outline=(80, 80, 90), width=2)
    return img


def rho_image(grid, wpx, hpx):
    eh, ew = len(grid), len(grid[0])
    img = Image.new("RGB", (ew, eh), (255, 255, 255))
    p = img.load()
    for i in range(eh):
        for j in range(ew):
            v = max(0.0, min(1.0, grid[i][j]))
            # 蓝(0) -> 白(0.5) -> 红(1)
            if v < 0.5:
                t = v / 0.5
                col = (int(46 + (250 - 46) * t), int(110 + (250 - 110) * t),
                       int(190 + (250 - 190) * t))
            else:
                t = (v - 0.5) / 0.5
                col = (int(250 - (250 - 180) * t), int(250 - (250 - 60) * t),
                       int(250 - (250 - 46) * t))
            p[j, i] = col
    return img.resize((wpx, hpx), Image.NEAREST)


def main():
    result = json.load(io.open(RESULT, encoding="utf-8"))
    cat = load_catalog()
    snap = result["snapshots"][-1]
    cfg = result["config"]
    W, H = cfg["W"], cfg["H"]
    mols = [(r, c, f) for (r, c, f) in snap["mols"]]

    SW, SH, CELL = 22, 16, 60
    picks, dens = choose_windows(mols, W, H, SW, SH)
    print("windows:", [(p[0], p[1], p[2], p[3], p[4]) for p in picks])

    panels = []
    for key, desc, ox, oy, score in picks:
        st = slice_stats(mols, W, H, ox, oy, SW, SH, cat)
        img = draw_slice_image(mols, W, H, ox, oy, SW, SH, CELL, cat)
        panels.append((key, desc, ox, oy, img, st))
        print("[%s] %s window=(%d,%d) n=%d distinct=%d mean_atoms=%.1f "
              "max_cluster=%d tiers=%s"
              % (key, desc, ox, oy, st["n"], st["n_distinct"], st["mean_atoms"],
                 st["clusters"]["max"], st["tiers"]))

    sw_px, sh_px = SW * CELL, SH * CELL
    pad = 22
    right_w = 900
    head_h = 104
    row_h = sh_px + 92
    maph = int(round(right_w * H / float(W)))
    rho_w, rho_h = 460, 300
    zoom_cell = 68
    zoom_w, zoom_h = 13 * zoom_cell, 9 * zoom_cell
    right_h = 34 + maph + 20 + 34 + rho_h + 20 + 34 + zoom_h + 20
    left_h = head_h + row_h * 2 + 8
    H_IMG = max(left_h, head_h + right_h) + 205
    W_IMG = pad + (sw_px * 2 + pad * 3) + right_w + pad

    canvas = Image.new("RGB", (W_IMG, H_IMG), BG)
    d = ImageDraw.Draw(canvas)
    d.text((pad, 22), "T83 九元素环境：三轴（质量/物态/温度）+ 三素力 · 骨架方块切片",
           font=fnt(40, True), fill=INK)
    d.text((pad, 74),
           "方格世界 %dx%d（硬边界）· 每格 1 分子、每个图标=1 单位方格 · 投料 %d 分子 · %d 拍 · "
           "初始 1000°C 冷却到 25°C · 终态 N=%d、T=%.1f°C"
           % (W, H, cfg["feed"]["n_molecules"], cfg["ticks"], snap["n"], snap["T"]),
           font=fnt(19), fill=SUB)

    positions = [(pad, head_h), (pad * 2 + sw_px, head_h),
                 (pad, head_h + row_h), (pad * 2 + sw_px, head_h + row_h)]
    for (key, desc, ox, oy, img, st), (x, y) in zip(panels, positions):
        t3 = st["tiers"]
        d.text((x, y), "%s  %s   窗口 (%d,%d) %dx%d 格" %
               (key, desc, ox, oy, SW, SH), font=fnt(21, True), fill=INK)
        d.text((x, y + 28),
               "N=%d 种数=%d 平均%.1f原子 局部最大团=%d 密度%.1f%%"
               % (st["n"], st["n_distinct"], st["mean_atoms"],
                  st["clusters"]["max"], st["density"] * 100),
               font=fnt(15), fill=SUB)
        d.text((x, y + 48),
               "质量 %d/%d/%d%%  物态 %d/%d/%d%%  温度 %d/%d/%d%%   顶: %s"
               % tuple([int(v * 100) for v in t3["mass"]]
                       + [int(v * 100) for v in t3["state"]]
                       + [int(v * 100) for v in t3["temperature"]]
                       + [", ".join("%s×%d" % (f, k) for f, k in st["top"][:3])]),
               font=fnt(15), fill=SUB)
        canvas.paste(img, (x, y + 74))
        d.rectangle([x, y + 74, x + sw_px, y + 74 + sh_px],
                    outline=(60, 60, 70), width=2)

    # ---------------- 全环境密度图 ----------------
    mx = pad * 2 + sw_px * 2 + pad
    y0 = head_h
    d.text((mx, y0), "全环境地图（密度：越红越密；蓝框=四个切片）",
           font=fnt(21, True), fill=INK)
    mimg = Image.new("RGB", (W, H), (255, 255, 255))
    mp = mimg.load()
    for r in range(H):
        for c in range(W):
            v = dens[r][c]
            t = min(1.0, v / 1.4)
            base = (250, 248, 242)
            hot = (196, 74, 44)
            mp[c, r] = tuple(int(base[i] + (hot[i] - base[i]) * t) for i in range(3))
    mimg = mimg.resize((right_w, maph), Image.BILINEAR)
    canvas.paste(mimg, (mx, y0 + 32))
    d.rectangle([mx, y0 + 32, mx + right_w, y0 + 32 + maph],
                outline=(60, 60, 70), width=2)
    for (key, desc, ox, oy, img, st) in panels:
        sx = mx + ox * right_w / float(W)
        sy = y0 + 32 + oy * maph / float(H)
        sx2 = mx + (ox + SW) * right_w / float(W)
        sy2 = y0 + 32 + (oy + SH) * maph / float(H)
        d.rectangle([sx, sy, sx2, sy2], outline=(20, 90, 160), width=3)
        d.text((sx + 4, sy + 3), key, font=fnt(20, True), fill=(20, 90, 160))

    # ---------------- 恒素场 rho（温度轴） ----------------
    ry = y0 + 32 + maph + 22
    d.text((mx, ry), "恒素场 ρ（温度轴，10×20 网格；蓝=稀薄、红=富集）",
           font=fnt(21, True), fill=INK)
    rim = rho_image(snap["rho"]["grid"], rho_w, rho_h)
    canvas.paste(rim, (mx, ry + 32))
    d.rectangle([mx, ry + 32, mx + rho_w, ry + 32 + rho_h],
                outline=(60, 60, 70), width=2)
    d.text((mx + rho_w + 18, ry + 40),
           "ρ 均值 %.3f" % snap["rho"]["mean"], font=fnt(17), fill=SUB)
    d.text((mx + rho_w + 18, ry + 66),
           "ρ 标准差 %.3f" % snap["rho"]["std"], font=fnt(17), fill=SUB)
    d.text((mx + rho_w + 18, ry + 100), "质量档 y 均值", font=fnt(16, True), fill=INK)
    for k, nm in enumerate(("轻", "中", "重")):
        yv = snap.get("y_mean_mass", [None] * 3)[k]
        d.text((mx + rho_w + 18, ry + 124 + k * 22),
               "%s: %s" % (nm, ("%.1f 行" % yv) if yv is not None else "—"),
               font=fnt(15), fill=SUB)

    # ---------------- 原地放大 ----------------
    zy = ry + 32 + rho_h + 22
    d.text((mx, zy), "E 原地放大（14×10 格）：每个图标 = 一个单位方格",
           font=fnt(21, True), fill=INK)
    big = max(mols, key=lambda m: natoms(m[2]))
    zox = min(max(0, big[1] - 6), W - 13)
    zoy = min(max(0, big[0] - 4), H - 9)
    zimg = draw_zoom(mols, W, H, zox, zoy, 14, 10, zoom_cell, cat)
    canvas.paste(zimg, (mx, zy + 32))
    d.rectangle([mx, zy + 32, mx + zoom_w, zy + 32 + zoom_h],
                outline=(60, 60, 70), width=2)
    d.text((mx, zy + 38 + zoom_h),
           "窗口 (%d,%d)；只给 ≥9 原子的分子标式" % (zox, zoy),
           font=fnt(15), fill=SUB)

    # ---------------- 图例/页脚 ----------------
    ly = H_IMG - 178
    d.text((pad, ly), "元素配色（原子方块）", font=fnt(18, True), fill=INK)
    lx = pad
    for e in ELEM_ORDER:
        d.rectangle([lx, ly + 28, lx + 18, ly + 46], fill=COL[e], outline=(40, 40, 45))
        d.text((lx + 22, ly + 27), e, font=fnt(17), fill=INK)
        lx += 52
    d.text((pad, ly + 62), "键型：S 实线 · C 虚线 · L 点线", font=fnt(17), fill=SUB)
    d.text((pad, ly + 88),
           "三轴：质量 轻/中/重→上升/悬浮/下沉；物态 气/液/固→穿过/游泳/阻挡；温度 冷/温/热→稀薄/中性/富集。"
           "图标统一缩放到 1.0 格（每分子占一格），相邻两格的两个分子在图上不会互相覆盖。",
           font=fnt(16), fill=SUB)
    d.text((pad, ly + 112),
           "读法：颜色=元素（原子方块），线型=化学键；图标位置=分子真实占据的格子。"
           "诚实注：模拟中分子是点粒子，骨架按目录结构绘制；180 种目录外产物画灰块。",
           font=fnt(16), fill=SUB)

    out = os.path.join(BASE, "images", "t83_slices.png")
    canvas.save(out)
    print("saved", out, canvas.size)
    for (key, desc, ox, oy, img, st) in panels:
        img.save(os.path.join(BASE, "images", "t83_slice_%s.png" % key.lower()))
    zimg.save(os.path.join(BASE, "images", "t83_slice_zoom.png"))

    meta = {
        "config": cfg,
        "final_summary": {
            "n": snap["n"], "T": snap["T"], "n_distinct": snap["n_distinct"],
            "clusters": snap["clusters"], "tiers": snap["tiers"],
            "y_mean_mass": snap["y_mean_mass"], "rho": snap["rho"]["mean"],
            "band_react": snap["band_react"], "mode_counts": snap["mode_counts"],
            "n_react": snap["n_react"], "n_new_species": snap["n_new_species"],
        },
        "windows": [{"key": k, "desc": ds, "ox": ox, "oy": oy, "stats": st}
                    for (k, ds, ox, oy, img, st) in panels],
        "zoom": {"ox": zox, "oy": zoy, "sw": 14, "sh": 10},
    }
    with io.open(os.path.join(BASE, "t83_slices.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    print("saved t83_slices.json")


if __name__ == "__main__":
    main()
