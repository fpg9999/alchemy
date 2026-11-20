# -*- coding: utf-8 -*-
"""T89 图：T88 群系里找到的"自主移动/生长/分裂/驻留"团簇。

输入：t89_life.json
输出：images/t89_life.png
"""
from __future__ import annotations

import io
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"
INK = (30, 32, 38)
SUB = (98, 102, 112)
COL = [(222, 92, 82), (70, 130, 190), (232, 168, 60), (86, 160, 110),
       (150, 110, 180), (90, 170, 180)]
W, H = 240, 160          # 世界尺寸


def fnt(s, b=False):
    return ImageFont.truetype(FONTB if b else FONT, s)


def trajectory(d, ox, oy, w, h, pts, color, annot=None, grid=True):
    # 按轨迹 bbox 放大（留边），不再整世界缩略
    rs = [p[1] for p in pts]; cs = [p[2] for p in pts]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    pad = max(4.0, 0.45 * max(r1 - r0, c1 - c0, 1.0))
    r0, r1, c0, c1 = r0 - pad, r1 + pad, c0 - pad, c1 + pad
    sw, sh = max(c1 - c0, 1e-6), max(r1 - r0, 1e-6)
    sc = min(w / sw, h / sh)
    offx = ox + (w - sw * sc) / 2.0
    offy = oy + (h - sh * sc) / 2.0
    def px(p):
        return (offx + (p[2] - c0) * sc, offy + (p[1] - r0) * sc)
    if grid:
        step = 5
        c = math.floor(c0 / step) * step
        while c <= c1:
            x = offx + (c - c0) * sc
            d.line([(x, offy), (x, offy + sh * sc)], fill=(238, 238, 242))
            c += step
        r = math.floor(r0 / step) * step
        while r <= r1:
            y = offy + (r - r0) * sc
            d.line([(offx, y), (offx + sw * sc, y)], fill=(238, 238, 242))
            r += step
        d.rectangle([offx, offy, offx + sw * sc, offy + sh * sc],
                    outline=(140, 140, 148))
    if len(pts) >= 2:
        d.line([px(p) for p in pts], fill=color, width=3)
    for p in pts:
        x, y = px(p)
        rr = max(2.5, min(7.0, 2.5 + p[3] / 10.0))
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=color,
                  outline=(255, 255, 255))
    x0, y0 = px(pts[0]); x1, y1 = px(pts[-1])
    d.ellipse([x0 - 8, y0 - 8, x0 + 8, y0 + 8], outline=(40, 140, 70), width=3)
    d.ellipse([x1 - 8, y1 - 8, x1 + 8, y1 + 8], outline=(190, 50, 50), width=3)
    if annot:
        tw = len(annot) * 7
        d.rectangle([ox + 2, oy + 2, ox + 8 + tw, oy + 22], fill=(255, 255, 255))
        d.text((ox + 6, oy + 4), annot, font=fnt(13), fill=SUB)

def text_block(d, x, y, lines, size=15, lh=24, color=INK):
    for i, s in enumerate(lines):
        d.text((x, y + i * lh), s, font=fnt(size), fill=color)


def main():
    data = json.load(io.open(os.path.join(BASE, "t89_life.json"),
                             encoding="utf-8"))
    bs = data["biomes"]
    W_IMG, H_IMG = 2600, 2050
    img = Image.new("RGB", (W_IMG, H_IMG), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 24), "T89 群系里的“类生命”候选：能自主移动 / 生长 / 分裂 / 驻留的分子团簇",
           font=fnt(31, True), fill=INK)
    d.text((40, 70), "规则 = T88 六群系（T87 连续重力 + 非对称力 + 骨架占格 + resolve）；"
                     "只看恒温阶段 t≥400 拍；判据见 §判据", font=fnt(16), fill=SUB)

    # A: 计数柱状
    ax, ay, aw, ah = 40, 112, 860, 470
    d.text((ax, ay), "A 各群系候选数量", font=fnt(19, True), fill=INK)
    ay2 = ay + 40
    cats = [("movers", "自主移动", COL[0]), ("growth", "生长", COL[2]),
            ("divisions", "分裂", COL[3]), ("colonies", "驻留大团", COL[1])]
    n = max(max(b.get("n_" + c) if "n_" + c in b else len(b[c])
                for c, _, _ in cats) for b in bs) or 1
    colw = (aw - 20) / len(bs)
    for i, b in enumerate(bs):
        bx = ax + 10 + i * colw
        for j, (key, label, col) in enumerate(cats):
            v = b.get("n_" + key, len(b.get(key, [])))
            bh = (ah - 120) * v / n
            x = bx + 8 + j * (colw - 16) / 4
            d.rectangle([x, ay2 + ah - 70 - bh, x + (colw - 16) / 4 - 6,
                         ay2 + ah - 70], fill=col)
            if v:
                d.text((x, ay2 + ah - 70 - bh - 18), str(v), font=fnt(12), fill=SUB)
        d.text((bx + 4, ay2 + ah - 60), b["biome"].replace("_", " "),
               font=fnt(12), fill=SUB)
    d.line([(ax + 10, ay2 + ah - 70), (ax + aw - 10, ay2 + ah - 70)],
           fill=(120, 120, 128))
    lx = ax + 20
    for j, (key, label, col) in enumerate(cats):
        d.rectangle([lx, ay2 + ah - 34, lx + 16, ay2 + ah - 18], fill=col)
        d.text((lx + 22, ay2 + ah - 36), label, font=fnt(13), fill=SUB)
        lx += 150

    # B: 每群系最佳候选轨迹（2×3）
    bx0, by0 = 940, 112
    bw, bh = 520, 270
    d.text((bx0, by0 - 6), "B 各群系最佳“自主移动团”的质心轨迹（绿=起点、红=终点、点大小∝团簇尺寸；已按轨迹 bbox 放大）",
           font=fnt(18, True), fill=INK)
    for i, b in enumerate(bs):
        row, col = divmod(i, 3)
        ox = bx0 + col * (bw + 16)
        oy = by0 + 58 + row * (bh + 74)
        mv = b["movers"][0] if b["movers"] else None
        sub = b["biome"].replace("_", " ")
        d.text((ox, oy - 24), sub, font=fnt(15, True), fill=INK)
        if mv is None:
            d.text((ox, oy + 10), "本群系未找到持续 mover", font=fnt(14), fill=SUB)
            continue
        trajectory(d, ox, oy, bw, bh, mv["pts"], COL[i % len(COL)],
                   "n≈%.0f  v=%.3f  straight=%.2f  %s→%s"
                   % (mv["n_mean"], mv["speed"], mv["straight"],
                      mv["dir"], ",".join(mv["top"][:2])))

    # C: 总冠军细节
    cy = 760
    allm = []
    for b in bs:
        for m in b["movers"]:
            m = dict(m)
            m["biome"] = b["biome"]
            allm.append(m)
    allm.sort(key=lambda s: -s.get("life_score", 0))
    hero = allm[0] if allm else None
    d.text((40, cy), "C 总冠军：life_score 最高的候选（轨迹放大）",
           font=fnt(19, True), fill=INK)
    if hero:
        trajectory(d, 40, cy + 40, 760, 500, hero["pts"], COL[0],
                   grid=True)
        lines = [
            "群系：%s（%s）" % (hero["biome"],
                               "".join(next(b["subset"] for b in bs
                                            if b["biome"] == hero["biome"]))),
            "life_score = %.3f" % hero.get("life_score", 0),
            "平均尺寸 n = %.1f（%d~%d），持续 %d 帧（t=%d~%d）"
            % (hero["n_mean"], hero["n_min"], hero["n_max"],
               hero["frames"], hero["t0"], hero["t1"]),
            "路径 %.1f 格，净位移 %.1f 格，速度 %.3f 格/拍，直线度 %.2f"
            % (hero["path"], hero["net"], hero["speed"], hero["straight"]),
            "方向：%s（dx=%.1f, dy=%.1f）" % (hero["dir"], hero["dx"], hero["dy"]),
            "平均 A=%.2f  R=%.2f  质量=%.2f" % (hero["A_mean"], hero["R_mean"],
                                              hero["mass_mean"]),
            "主要成分：%s" % "、".join(hero["top"]),
            "",
            "形态：%s" % ("一条持续朝一个方向的漂移轨迹"
                        if hero["straight"] >= 0.35 else
                        "先扩散后回收的游走轨迹（直线度中等）"),
        ]
        text_block(d, 840, cy + 40, lines, size=17, lh=30)

    # D: 判据与结论
    d.text((40, 1330), "D 判据与统计", font=fnt(19, True), fill=INK)
    stats_lines = []
    for b in bs:
        mv = b["movers"][0] if b["movers"] else None
        stats_lines.append(
            "%-9s tracks %4d  多帧 %3d  移动团 %3d（占分子 %.1f%%）  生长 %3d  分裂 %2d  驻留大团 %2d   最优：%s"
            % (b["biome"], b["n_tracks"], b["n_multi"], b["n_movers"],
               100 * b["frac_in_movers"], b["n_growth"], b["n_divisions"],
               b["n_colonies"],
               ("n=%.0f v=%.3f s=%.2f" % (mv["n_mean"], mv["speed"], mv["straight"]))
               if mv else "—"))
    text_block(d, 40, 1372, stats_lines, size=14, lh=26, color=INK)

    rules = [
        "判据（恒温阶段 t≥400，25 拍/帧）：",
        "  mover  = frames≥4 且 n_mean≥4 且 速度≥0.06 格/拍 且 直线度≥0.25",
        "  growth = 同一 track 内 n 从 n_min 涨到 ≥1.5×n_min；division = track 结束后一帧在质心 10 格内出现 2+ 个尺寸合计≈原尺寸的簇；",
        "  colony = n_mean≥80 且 frames≥6 且 速度<0.05（大会在原地反应、不迁移）",
        "结论：所谓“自主行动”在这套规则里只是**局部非对称力 + 重力 + 边界**造成的持续漂移，没有自我维持/繁殖/边界；",
        "      真正“像生命”的候选是：①持续漂移的小团（10~30 个分子，速度 0.06~0.1 格/拍）；②原地驻留的大团（反应持续但几乎不移动）；③极少数生长/分裂事件。",
    ]
    text_block(d, 40, 1600, rules, size=14, lh=26, color=SUB)

    d.text((40, H_IMG - 40),
           "读图：轨迹图为世界坐标（c 向右、r 向下，世界 240×160）。所有候选都是点粒子/骨架块团簇，"
           "“移动”=团簇质心位移；没有内部构象、没有遗传/边界/复制。",
           font=fnt(14), fill=SUB)
    out = os.path.join(BASE, "images", "t89_life.png")
    img.save(out)
    print("saved", out, img.size)


if __name__ == "__main__":
    main()
