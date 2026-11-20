"""T84 渲染：三轴环境 + 三素力，**每个中间态骨架占 1 格**的骨架切片。

与 T83 渲染的区别：分子不再统一缩到 1 格，而是按 k 个骨架块占 k 个方格；
第 i 个骨架块画在第 i 个格子里（格子由 t84_env_skel.skel_shape 决定），
块之间的二价桥原子跨格相连（用细虚线示意）。
"""

from __future__ import annotations

import io
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont

from alchemy import attrs as A
from alchemy.core.elements import ORDER as ELEM_ORDER, classify_offset
from t84_env_skel import skel_shape

BASE = r"G:\AI work\deepseek\work1\alchemy"
RESULT = os.path.join(BASE, "t84_env_skel_result.json")
CATALOG = os.path.join(BASE, "t4_catalog_all_validated.json")
OUT = os.path.join(BASE, "images", "t84_slices.png")
FONT_R = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

COL = {
    "O": (214, 63, 58), "K": (240, 140, 40), "P": (150, 150, 50),
    "X": (58, 96, 196), "W": (40, 168, 200), "A": (60, 178, 118),
    "F": (208, 60, 190), "L": (150, 80, 210), "C": (132, 78, 60),
}
INK = (30, 30, 36)
SUB = (92, 92, 100)
LINE = (70, 70, 78)
BG = (255, 255, 255)
GRID = (232, 232, 238)
WARM = (236, 74, 52)
COOL = (70, 156, 186)

_fonts = {}


def fnt(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_B if bold else FONT_R, size)
    return _fonts[key]


_comp_cache = {}
_atom_cache = {}
_skel_cache = {}
_cat = None


def catalog():
    global _cat
    if _cat is None:
        recs = json.load(io.open(CATALOG, encoding="utf-8"))
        _cat = {r["formula"]: r for r in recs}
    return _cat


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
    return sum(parse_comp(f).values())


def atoms_edges(f):
    if f in _atom_cache:
        return _atom_cache[f]
    rec = catalog().get(f)
    if rec:
        atoms = tuple(rec["atoms"])
        edges = [tuple(e) for e in rec["edges"]]
        place = {int(k): (v[0], v[1]) for k, v in rec["place"].items()}
    else:
        atoms = []
        for e in ELEM_ORDER:
            atoms.extend([e] * parse_comp(f).get(e, 0))
        edges = []
        place = None
    _atom_cache[f] = (atoms, edges, place)
    return _atom_cache[f]


def skel_units(f):
    if f in _skel_cache:
        return _skel_cache[f]
    atoms, edges, place = atoms_edges(f)
    units = A.skeleton_units(atoms, edges) if place else []
    _skel_cache[f] = units
    return units


def tiers_of(f):
    atoms, edges, _ = atoms_edges(f)
    at = A.molecule_attrs(atoms, edges)
    prop = A.property_of(at)
    g = {"低": 0, "中": 1, "高": 2}
    return (g[prop["grades"]["mass"]], g[prop["grades"]["state"]],
            g[prop["grades"]["temperature"]])


def xy_of(place):
    return {i: (math.sqrt(3.0) * (q + r / 2.0), 1.5 * r)
            for i, (q, r) in place.items()}


def draw_bond(d, x1, y1, x2, y2, kind, w):
    w = max(1, int(w))
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    if kind == "S":
        d.line([(int(x1), int(y1)), (int(x2), int(y2))], fill=LINE, width=w)
    elif kind == "C":
        seg, gap = max(2.0, w * 2.0), max(1.5, w * 1.5)
        t = 0.0
        while t < L:
            t2 = min(L, t + seg)
            d.line([(int(x1 + ux * t), int(y1 + uy * t)),
                    (int(x2 + ux * t2), int(y2 + uy * t2))],
                   fill=LINE, width=w)
            t = t2 + gap
    else:
        dot, gap = max(1.0, w * 0.9), max(2.2, w * 1.6)
        t = 0.0
        while t < L:
            d.ellipse([x1 + ux * t - dot / 2, y1 + uy * t - dot / 2,
                       x1 + ux * t + dot / 2, y1 + uy * t + dot / 2],
                      fill=LINE)
            t += dot + gap


def draw_unit(d, bx, by, sz, f, members):
    """把一个骨架块的 members 画进 bx,by,sz 的方格里。"""
    atoms, edges, place = atoms_edges(f)
    xy = xy_of(place)
    ms = [i for i in members if i in xy]
    if not ms:
        return
    cx = sum(xy[i][0] for i in ms) / len(ms)
    cy = sum(xy[i][1] for i in ms) / len(ms)
    ext = max(max(abs(xy[i][0] - cx), abs(xy[i][1] - cy)) for i in ms) or 1.0
    s = (sz * 0.40) / ext
    mx = dx = bx + sz / 2.0
    my = dy = by + sz / 2.0
    mset = set(ms)
    for (i, j, *rest) in edges:
        i, j = int(i), int(j)
        if i not in mset or j not in mset:
            continue
        kind = classify_offset((place[j][0] - place[i][0],
                                place[j][1] - place[i][1]))
        draw_bond(d, mx + (xy[i][0] - cx) * s, my + (xy[i][1] - cy) * s,
                  mx + (xy[j][0] - cx) * s, my + (xy[j][1] - cy) * s,
                  kind, max(1, sz * 0.045))
    blk = max(2.6, min(sz * 0.22, s * sz * 0.26))
    r = blk / 2.0
    for i in ms:
        x, y = mx + (xy[i][0] - cx) * s, my + (xy[i][1] - cy) * s
        col = COL.get(atoms[i], (120, 120, 120))
        d.rectangle([int(x - r), int(y - r), int(x + r), int(y + r)],
                    fill=col, outline=(35, 35, 40), width=1)


def draw_mol(d, ox, oy, cell, r, c, f, k):
    cells = skel_shape(k)
    units = skel_units(f)
    if units and len(units) == len(cells):
        for idx, (dr, dc) in enumerate(cells):
            draw_unit(d, ox + dc * cell, oy + dr * cell, cell,
                      f, units[idx]["members"])
    else:
        # 未知分子：灰块铺满 footprint
        for (dr, dc) in cells:
            c0 = ox + dc * cell + cell * 0.26
            r0 = oy + dr * cell + cell * 0.26
            d.rectangle([c0, r0, c0 + cell * 0.48, r0 + cell * 0.48],
                        fill=(168, 168, 172), outline=(96, 96, 100))
    # footprint 轮廓：让"多骨架=多格"一眼可辨（虚线浅蓝框）
    if k > 1:
        rows = max(dr for dr, dc in cells) + 1
        cols = max(dc for dr, dc in cells) + 1
        x0, y0 = ox + 1, oy + 1
        x1, y1 = ox + cols * cell - 2, oy + rows * cell - 2
        dash = max(3, cell // 12)
        for x in range(x0, x1, dash * 2):
            d.line([(x, y0), (min(x1, x + dash), y0)], fill=(130, 160, 210))
            d.line([(x, y1), (min(x1, x + dash), y1)], fill=(130, 160, 210))
        for y in range(y0, y1, dash * 2):
            d.line([(x0, y), (x0, min(y1, y + dash))], fill=(130, 160, 210))
            d.line([(x1, y), (x1, min(y1, y + dash))], fill=(130, 160, 210))
        # 骨架块之间的连接（示意）
        for a, b in zip(cells, cells[1:]):
            ax = ox + a[1] * cell + cell // 2
            ay = oy + a[0] * cell + cell // 2
            bx = ox + b[1] * cell + cell // 2
            by = oy + b[0] * cell + cell // 2
            d.line([(ax, ay), (bx, by)], fill=(160, 180, 220), width=1)


def cells_of(r, c, f, k):
    return [(r + dr, c + dc) for dr, dc in skel_shape(k)]


def analysis(mols, W, H):
    om = {}
    for (r, c, f, k) in mols:
        for cell in cells_of(r, c, f, k):
            om[cell] = (r, c, f, k)
    return om


def clusters_in(mols, W, H):
    om = analysis(mols, W, H)
    seen = set()
    sizes = []
    for start in list(om):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        mids = set()
        while stack:
            (r, c) = stack.pop()
            m = om[(r, c)]
            mids.add(m)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    p = (r + dr, c + dc)
                    if p in om and p not in seen:
                        seen.add(p)
                        stack.append(p)
        sizes.append(len(mids))
    return sizes


def slice_stats(mols, W, H, ox, oy, sw, sh):
    sub = [(r, c, f, k) for (r, c, f, k) in mols
           if oy <= r < oy + sh and ox <= c < ox + sw]
    comp = {}
    for (r, c, f, k) in sub:
        comp[f] = comp.get(f, 0) + 1
    comps = clusters_in(sub, W, H)
    used = set()
    for (r, c, f, k) in sub:
        used.update(cells_of(r, c, f, k))
    tiers = {"mass": [0, 0, 0], "state": [0, 0, 0], "temperature": [0, 0, 0]}
    for (r, c, f, k) in sub:
        t = tiers_of(f)
        for idx, ax in enumerate(("mass", "state", "temperature")):
            tiers[ax][t[idx]] += 1
    n = max(1, len(sub))
    for ax in tiers:
        tiers[ax] = [round(v / n, 3) for v in tiers[ax]]
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    return {"window": [ox, oy, sw, sh], "n": len(sub),
            "cells": len(used), "density": round(len(used) / float(sw * sh), 4),
            "n_distinct": len(comp), "mean_atoms": round(
                sum(natoms(f) for (r, c, f, k) in sub) / n, 2),
            "mean_k": round(sum(k for (r, c, f, k) in sub) / n, 2),
            "top": top, "tiers": tiers,
            "clusters": {"n_components": len(comps),
                         "max": max(comps) if comps else 0}}


def choose_windows(mols, W, H, sw, sh):
    cnt = [[0] * W for _ in range(H)]
    for (r, c, f, k) in mols:
        for (rr, cc) in cells_of(r, c, f, k):
            cnt[rr][cc] += 1
    cands = []
    for oy in range(0, H - sh + 1, max(1, sh // 4)):
        for ox in range(0, W - sw + 1, max(1, sw // 4)):
            s = 0
            for r in range(oy, oy + sh):
                s += sum(cnt[r][ox:ox + sw])
            cands.append((s, ox, oy))
    cands.sort(reverse=True)
    picks = []
    mind = min(sw, sh) * 0.8

    def far(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1]) >= mind

    picks.append(("A", "最密集区域", cands[0][1], cands[0][2]))
    chosen = None
    for s, ox, oy in cands[len(cands) // 2:]:
        if far((ox, oy), (picks[0][2], picks[0][3])):
            chosen = (ox, oy)
            break
    picks.append(("B", "中等密度区域", chosen[0], chosen[1]))
    chosen = None
    for s, ox, oy in reversed(cands):
        if s < 10:
            continue
        if far((ox, oy), (picks[0][2], picks[0][3])) and \
                far((ox, oy), (picks[1][2], picks[1][3])):
            chosen = (ox, oy)
            break
    picks.append(("C", "最稀疏区域", chosen[0], chosen[1]))
    bigs = sorted(mols, key=lambda m: -natoms(m[2]))[:400]
    chosen = None
    for (r, c, f, k) in bigs:
        ox = min(max(0, c - sw // 2), W - sw)
        oy = min(max(0, r - sh // 2), H - sh)
        if all(far((ox, oy), (p[2], p[3])) for p in picks):
            chosen = (ox, oy)
            break
    picks.append(("D", "最大分子附近", chosen[0], chosen[1]))
    return picks, cnt


def draw_slice(mols, W, H, ox, oy, sw, sh, cell):
    img = Image.new("RGB", (sw * cell, sh * cell), BG)
    d = ImageDraw.Draw(img)
    for r in range(sh + 1):
        d.line([(0, r * cell), (sw * cell, r * cell)], fill=GRID)
    for c in range(sw + 1):
        d.line([(c * cell, 0), (c * cell, sh * cell)], fill=GRID)
    for (r, c, f, k) in mols:
        if not (oy <= r < oy + sh and ox <= c < ox + sw):
            continue
        rr, cc = r - oy, c - ox
        draw_mol(d, cc * cell, rr * cell, cell, rr, cc, f, k)
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1],
                outline=(60, 60, 70), width=2)
    return img


def draw_zoom(mols, W, H, ox, oy, sw, sh, cell, cat):
    img = Image.new("RGB", (sw * cell, sh * cell), BG)
    d = ImageDraw.Draw(img)
    for r in range(sh + 1):
        d.line([(0, r * cell), (sw * cell, r * cell)], fill=GRID)
    for c in range(sw + 1):
        d.line([(c * cell, 0), (c * cell, sh * cell)], fill=GRID)
    picked = [m for m in mols if oy <= m[0] < oy + sh and ox <= m[1] < ox + sw]
    for (r, c, f, k) in picked:
        draw_mol(d, (c - ox) * cell, (r - oy) * cell, cell,
                 r - oy, c - ox, f, k)
    for (r, c, f, k) in picked:
        if natoms(f) < 12:
            continue
        tw = d.textlength(f, font=fnt(14))
        x = min(max(0, (c - ox) * cell + 4), sw * cell - tw - 4)
        y = min(max(0, (r - oy) * cell + 4), sh * cell - 18)
        d.rectangle([x - 2, y - 1, x + tw + 2, y + 16], fill=(255, 255, 255))
        d.text((x, y), f, font=fnt(14), fill=INK)
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1],
                outline=(60, 60, 70), width=2)
    return img


def render():
    res = json.load(io.open(RESULT, encoding="utf-8"))
    snap = res["snapshots"][-1]
    cfg = res["config"]
    W, H = cfg["W"], cfg["H"]
    mols = [(r, c, f, k) for (r, c, f, k) in snap["mols"]]

    SW, SH, CELL = 24, 18, 54
    picks, cnt = choose_windows(mols, W, H, SW, SH)
    print("windows:", [(p[0], p[1], p[2], p[3]) for p in picks])

    panels = []
    for key, desc, ox, oy in picks:
        st = slice_stats(mols, W, H, ox, oy, SW, SH)
        img = draw_slice(mols, W, H, ox, oy, SW, SH, CELL)
        panels.append((key, desc, ox, oy, img, st))
        print("[%s] %s window=(%d,%d) n=%d cells=%d density=%.3f "
              "distinct=%d mean_atoms=%.1f mean_k=%.2f max_cl=%d tiers=%s"
              % (key, desc, ox, oy, st["n"], st["cells"], st["density"],
                 st["n_distinct"], st["mean_atoms"], st["mean_k"],
                 st["clusters"]["max"], st["tiers"]))

    pad, head_h = 24, 96
    slice_w, slice_h = SW * CELL, SH * CELL
    left_w = pad * 3 + slice_w * 2
    right_w = 940
    map_w, map_h = right_w - 24, int((right_w - 24) * H / float(W))
    rho_w, rho_h = 470, 260
    zoom_cell = 72
    zsw, zsh = 12, 9
    legend_h = 215
    head = 120
    left_h = head + (slice_h + 84) * 2 - 10
    right_h = head + 30 + map_h + 20 + 28 + rho_h + 60
    H_IMG = max(left_h, right_h) + legend_h
    W_IMG = pad * 3 + slice_w * 2 + right_w

    canvas = Image.new("RGB", (W_IMG, H_IMG), BG)
    d = ImageDraw.Draw(canvas)
    d.text((pad, 20), "T84 九元素环境：三轴 + 三素力，每个中间态骨架占 1 格",
           font=fnt(34, True), fill=INK)
    d.text((pad, 64),
           "方格 %dx%d、每分子 k 个骨架块占 k 格、k=len(skeleton_units)；初始 1000°C 自然冷却到 %.1f°C；"
           "N=%d 分子 / %d 格占用（%.1f%%）；三轴+三素+规则1~11 反应；conservation_ok=%s"
           % (W, H, snap["T"], snap["n"], snap["cells_used"],
              100.0 * snap["cells_used"] / (W * H),
              res["summary"]["conservation_ok"]),
           font=fnt(17), fill=SUB)

    for idx, (key, desc, ox, oy, img, st) in enumerate(panels):
        col = idx % 2
        row = idx // 2
        x0 = pad + col * (slice_w + pad)
        y0 = head + row * (slice_h + 74)
        canvas.paste(img, (x0, y0))
        d.rectangle([x0, y0, x0 + slice_w, y0 + slice_h],
                    outline=(60, 60, 70), width=2)
        d.text((x0, y0 - 40), "%s %s   窗口 (%d,%d) %dx%d 格"
               % (key, desc, ox, oy, SW, SH), font=fnt(19, True), fill=INK)
        d.text((x0, y0 - 18),
               "N=%d · %d 种 · 平均 %.1f 原子 / %.2f 骨架 · 格占用 %.1f%% · 最大团 %d"
               % (st["n"], st["n_distinct"], st["mean_atoms"], st["mean_k"],
                  100 * st["density"], st["clusters"]["max"]),
               font=fnt(15), fill=SUB)
        t = st["tiers"]
        d.text((x0, y0 + slice_h + 4),
               "质量 轻/中/重 %.1f/%.1f/%.1f%% ｜ 物态 气/液/固 %.0f/%.0f/%.0f%% ｜ 温度 冷/温/热 %.0f/%.0f/%.0f%%"
               % (100 * t["mass"][0], 100 * t["mass"][1], 100 * t["mass"][2],
                  100 * t["state"][0], 100 * t["state"][1], 100 * t["state"][2],
                  100 * t["temperature"][0], 100 * t["temperature"][1],
                  100 * t["temperature"][2]),
               font=fnt(15), fill=SUB)
        d.text((x0, y0 + slice_h + 24),
               "前 4：%s" % "、".join("%s×%d" % (f, c) for f, c in st["top"][:4]),
               font=fnt(15), fill=SUB)

    # 右侧：密度图 / rho 场 / 放大
    mx = pad * 2 + slice_w * 2
    my = head + 40
    d.text((mx, my - 30), "全环境地图（格占用：越红越密；蓝框=四个切片）",
           font=fnt(18, True), fill=INK)
    mm = Image.new("RGB", (map_w, map_h), BG)
    md = ImageDraw.Draw(mm)
    vmax = max(1, max(max(row) for row in cnt))
    for r in range(H):
        for c in range(W):
            v = cnt[r][c]
            if v:
                t = min(1.0, v / 2.2)
                col = (int(255 - 120 * t), int(235 - 120 * t), int(230 - 120 * t))
                x0 = int(c * map_w / W)
                y0 = int(r * map_h / H)
                x1 = max(x0 + 1, int((c + 1) * map_w / W))
                y1 = max(y0 + 1, int((r + 1) * map_h / H))
                md.rectangle([x0, y0, x1, y1], fill=col)
    md.rectangle([0, 0, map_w - 1, map_h - 1], outline=(60, 60, 70), width=2)
    for (key, desc, ox, oy, img, st) in panels:
        x0 = int(ox * map_w / W)
        y0 = int(oy * map_h / H)
        x1 = int((ox + SW) * map_w / W)
        y1 = int((oy + SH) * map_h / H)
        md.rectangle([x0, y0, x1, y1], outline=(40, 70, 190), width=2)
        md.text((x0 + 4, y0 + 2), key, font=fnt(16, True), fill=(40, 70, 190))
    canvas.paste(mm, (mx, my))

    # rho 场
    ry = my + map_h + 46
    d.text((mx, ry - 26), "恒素场 ρ（温度轴，10×20；蓝=稀薄 白=中性 红=富集）",
           font=fnt(17, True), fill=INK)
    rho = res["summary"]["rho"]
    grid = rho["grid"]
    eh, ew = len(grid), len(grid[0])
    gw, gh = rho_w, int(rho_w * eh / float(ew))
    rm = Image.new("RGB", (gw, gh), BG)
    rd = ImageDraw.Draw(rm)
    for i in range(eh):
        for j in range(ew):
            v = grid[i][j]
            t = min(1.0, max(0.0, v))
            col = (int(255 - 120 * t), int(248 - 130 * t), int(245 - 120 * t))
            rd.rectangle([j * gw / ew, i * gh / eh,
                          (j + 1) * gw / ew - 1, (i + 1) * gh / eh - 1],
                         fill=col)
    rd.rectangle([0, 0, gw - 1, gh - 1], outline=(60, 60, 70), width=2)
    canvas.paste(rm, (mx, ry))
    d.text((mx, ry + gh + 8),
           "ρ 均值 %.3f · 标准差 %.3f ｜ 质量档 y 均值 %s（轻/中/重）"
           % (rho["mean"], rho["std"],
              "/".join("%.1f" % v if v is not None else "—"
                       for v in snap["y_mean_mass"])),
           font=fnt(16), fill=SUB)

    # 放大（单独保存，合成图只放 4 切片 + 地图 + ρ 场）
    big = max(mols, key=lambda m: natoms(m[2]))
    zox = min(max(0, big[1] - zsw // 2), W - zsw)
    zoy = min(max(0, big[0] - zsh // 2), H - zsh)
    zimg = draw_zoom(mols, W, H, zox, zoy, zsw, zsh, zoom_cell, catalog())
    zimg.save(os.path.join(BASE, "images", "t84_slice_zoom.png"))

    # 底部图例
    ly = H_IMG - legend_h + 10
    d.rectangle([pad, ly, W_IMG - pad, H_IMG - 12], outline=(200, 200, 208))
    lx = pad + 12
    d.text((lx, ly + 10), "元素配色（原子方块）：", font=fnt(16), fill=INK)
    lx += 190
    for e in ELEM_ORDER:
        d.rectangle([lx, ly + 12, lx + 16, ly + 28], fill=COL[e],
                    outline=(40, 40, 45))
        d.text((lx + 20, ly + 9), e, font=fnt(16), fill=INK)
        lx += 46
    d.text((pad + 12, ly + 40), "键型：S 实线 · C 虚线 · L 点线", font=fnt(16), fill=SUB)
    d.text((pad + 12, ly + 64),
           "分子 = k 个中间态骨架块，占 k 个相邻方格；第 i 块画在第 i 格；块间二价桥用虚线连接（示意）。",
           font=fnt(15), fill=SUB)
    d.text((pad + 12, ly + 88),
           "三轴：质量 轻/中/重→上升/悬浮/下沉；物态 气/液/固→穿过/游泳/阻挡；温度 冷/温/热→稀薄/中性/富集；"
           "三素力：聚=吸引、散=覆盖半径、动=排斥。",
           font=fnt(15), fill=SUB)
    d.text((pad + 12, ly + 112),
           "诚实注：模拟中分子是点粒子，但占格/移动/接触按骨架块数 k 处理（k 格 footprint）；"
           "骨架按目录 place 绘制；目录外产物画灰块。",
           font=fnt(15), fill=SUB)

    canvas.save(OUT)
    print("saved", OUT, canvas.size)
    for (key, desc, ox, oy, img, st) in panels:
        img.save(os.path.join(BASE, "images", "t84_slice_%s.png" % key.lower()))
    zimg.save(os.path.join(BASE, "images", "t84_slice_zoom.png"))
    meta = {"config": cfg, "final_summary": {
        "n": snap["n"], "T": snap["T"], "n_distinct": snap["n_distinct"],
        "cells_used": snap["cells_used"], "clusters": snap["clusters"],
        "tiers": snap["tiers"], "y_mean_mass": snap["y_mean_mass"],
        "rho": {"mean": rho["mean"], "std": rho["std"]},
        "band_react": snap["band_react"], "mode_counts": snap["mode_counts"]},
        "windows": [{"key": k, "desc": dsc, "ox": ox, "oy": oy, "stats": st}
                    for (k, dsc, ox, oy, im, st) in panels],
        "zoom": {"ox": zox, "oy": zoy, "sw": zsw, "sh": zsh}}
    with io.open(os.path.join(BASE, "t84_slices.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    print("saved t84_slices.json")


if __name__ == "__main__":
    render()
