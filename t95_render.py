# -*- coding: utf-8 -*-
"""T95 出图：推挤统计 / 核心存留 / 速度场对比（中文，读 t95_ab.json）。

图 1 images/t95_push.png    推挤次数、失败、链长直方图、团簇整体移动与 mean|v|
图 2 images/t95_core.png    主体原子留存、环境-主体接触、核心-环境反应、膜覆盖
图 3 images/t95_vfield.png  速度场对比：v0（无速度场）vs v2（团簇/分子速度箭头）
                             另加 mean|v| 时间曲线与团簇移动计数
"""

import io
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
IMGDIR = os.path.join(BASE, "images")
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"
INK = (32, 32, 40)
SUB = (92, 92, 102)
GRID = (226, 228, 234)
RED = (206, 64, 64)
BLUE = (52, 96, 190)
GREEN = (46, 150, 90)
ORANGE = (214, 132, 44)
PURPLE = (138, 92, 178)
TEAL = (36, 140, 150)
GRAY = (120, 120, 130)

VCOL = {"v0": GRAY, "v1": BLUE, "v2": RED}
VLAB = {"v0": "v0 基线（T94 规则）", "v1": "v1 P1 单格推挤",
        "v2": "v2 P2 团簇动量"}


def fnt(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def load(name):
    with io.open(os.path.join(BASE, "t95_ab.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    arm = [a for a in d["arms"] if a["version"] == name[0] and a["arm"] == name[1]]
    return d, (arm[0] if arm else None)


def axes(d, box, ymax, ylab, xlab, xmax=600, fmt="%.0f", ymin=0.0,
         xticks=True):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], outline=(70, 70, 80), width=2)
    d.text((x0, y0 - 24), ylab, font=fnt(15), fill=SUB)
    for k in range(1, 5):
        y = y1 - (y1 - y0) * k / 5.0
        d.line([(x0, y), (x1, y)], fill=GRID, width=1)
        d.text((x0 - 10, y - 9), fmt % (ymin + (ymax - ymin) * k / 5.0),
               font=fnt(13), fill=SUB, anchor="ra")
    if xticks:
        for k in range(1, 5):
            x = x0 + (x1 - x0) * k / 5.0
            d.text((x, y1 + 8), "%d" % (xmax * k / 5.0), font=fnt(13), fill=SUB,
                   anchor="ma")
    d.text(((x0 + x1) / 2.0 - 40, y1 + 30), xlab, font=fnt(15), fill=SUB)


def line(d, box, xs, ys, xmax, ymax, col, w=3, ymin=0.0):
    x0, y0, x1, y1 = box
    pts = []
    for x, y in zip(xs, ys):
        if y is None:
            continue
        px = x0 + (x1 - x0) * min(1.0, max(0.0, x / float(xmax or 1)))
        py = y1 - (y1 - y0) * (min(ymax, max(ymin, y)) - ymin) / float(ymax - ymin or 1)
        pts.append((px, py))
    if len(pts) > 1:
        d.line(pts, fill=col, width=w)


def bars_h(d, x0, y0, items, w, h, dy, vmax, fmt="%.0f"):
    for i, (lab, val, col) in enumerate(items):
        y = y0 + i * dy
        d.text((x0, y), lab, font=fnt(14), fill=INK)
        bw = int(w * min(1.0, abs(val) / float(vmax or 1)))
        if bw > 0:
            d.rectangle([x0 + 330, y, x0 + 330 + bw, y + h], fill=col)
        d.text((x0 + 340 + bw, y - 1), fmt % val, font=fnt(14), fill=SUB)


def legend(d, x, y, items, dy=24):
    for i, (lab, col) in enumerate(items):
        yy = y + i * dy
        d.rectangle([x, yy + 5, x + 18, yy + 18], fill=col)
        d.text((x + 26, yy - 1), lab, font=fnt(14), fill=SUB)


def short(arm):
    return arm.replace("_G00", " G=0").replace("_G02", " G=0.2")


# --------------------------------------------------------------- 图 1
def fig_push(ab):
    arms = [(a["version"], a["arm"], a) for a in ab["arms"]]
    img = Image.new("RGB", (2400, 1200), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((60, 36), "T95：推挤事件统计（v0 / v1 / v2 × 6 臂）", font=fnt(30, True), fill=INK)
    d.text((60, 82), "n_push=成功链式推挤次数；n_push_fail=动量/质量/边界/占格判据拒绝；"
                     "chain_hist=每次成功推动的链分子数分布。所有计数为 600 拍累计原始计数。",
           font=fnt(15), fill=SUB)
    # A n_push
    boxA = (120, 150, 1080, 560)
    d.text((120, 118), "A 成功推挤次数 n_push", font=fnt(18, True), fill=INK)
    vmax = 100.0
    for _, _, a in arms:
        vmax = max(vmax, a["n_push"])
    vmax = 500.0 * math.ceil(vmax / 500.0)
    axes(d, boxA, vmax, "次（累计）", "", xmax=18, fmt="%.0f", xticks=False)
    bw = (boxA[2] - boxA[0]) / 18.0
    for i, (ver, arm, a) in enumerate(arms):
        h = (boxA[3] - boxA[1]) * a["n_push"] / vmax
        x = boxA[0] + i * bw + 2
        d.rectangle([x, boxA[3] - h, x + bw - 4, boxA[3]],
                    fill=VCOL.get(ver, GRAY))
    for t, ver in enumerate(("v0", "v1", "v2")):
        cx = boxA[0] + (t * 6 + 3) * bw
        d.text((cx, boxA[3] + 30), ver, font=fnt(15, True), fill=VCOL[ver],
               anchor="ma")
    legend(d, 60, 600, [(VLAB[v], VCOL[v]) for v in ("v0", "v1", "v2")])
    # B n_push_fail
    boxB = (1240, 150, 2200, 560)
    d.text((1240, 118), "B 推挤失败 n_push_fail", font=fnt(18, True), fill=INK)
    vmaxb = 100.0
    for _, _, a in arms:
        vmaxb = max(vmaxb, a["n_push_fail"])
    vmaxb = 1000.0 * math.ceil(vmaxb / 1000.0)
    axes(d, boxB, vmaxb, "次（累计）", "", xmax=18, fmt="%.0f", xticks=False)
    for i, (ver, arm, a) in enumerate(arms):
        h = (boxB[3] - boxB[1]) * a["n_push_fail"] / vmaxb
        x = boxB[0] + i * bw + 2
        d.rectangle([x, boxB[3] - h, x + bw - 4, boxB[3]],
                    fill=VCOL.get(ver, GRAY))
    for t, ver in enumerate(("v0", "v1", "v2")):
        cx = boxB[0] + (t * 6 + 3) * bw
        d.text((cx, boxB[3] + 30), ver, font=fnt(15, True), fill=VCOL[ver],
               anchor="ma")
    # C chain hist（按版本汇总）
    boxC = (120, 700, 1080, 1090)
    d.text((120, 668), "C 推挤链长分布（按版本汇总成功次数）", font=fnt(18, True), fill=INK)
    hist = {"v1": {}, "v2": {}}
    for ver, arm, a in arms:
        if ver in hist:
            for k, v in (a.get("chain_hist") or {}).items():
                hist[ver][int(k)] = hist[ver].get(int(k), 0) + v
    ks = sorted(set(list(hist["v1"]) + list(hist["v2"])))[:7]
    ymaxc = 100.0
    for v in hist.values():
        for k in ks:
            ymaxc = max(ymaxc, v.get(k, 0))
    ymaxc = 1000.0 * math.ceil(ymaxc / 1000.0)
    axes(d, boxC, ymaxc, "次（累计）", "", xmax=max(1, len(ks)),
         fmt="%.0f", xticks=False)
    gw = (boxC[2] - boxC[0]) / float(max(1, len(ks)))
    for j, k in enumerate(ks):
        for t, ver in enumerate(("v1", "v2")):
            val = hist[ver].get(k, 0)
            h = (boxC[3] - boxC[1]) * val / ymaxc
            x = boxC[0] + j * gw + 4 + t * gw / 2.0
            d.rectangle([x, boxC[3] - h, x + gw / 2.0 - 6, boxC[3]],
                        fill=VCOL[ver])
        d.text((boxC[0] + j * gw + gw / 2.0 - 8, boxC[3] + 10), str(k),
               font=fnt(13), fill=SUB)
    legend(d, 60, 1122, [(VLAB["v1"], VCOL["v1"]), (VLAB["v2"], VCOL["v2"])])
    # D 团簇移动 / 重力推挤
    boxD = (1240, 700, 2200, 1090)
    d.text((1240, 668), "D 团簇整体移动与重力推挤（v2）", font=fnt(18, True), fill=INK)
    LBL = {"nomem_G00": "无膜G0", "nomem_G02": "无膜G.2",
           "PK_G00": "PK G0", "PK_G02": "PK G.2",
           "double_G00": "双 G0", "double_G02": "双 G.2"}
    items = []
    for ver, arm, a in arms:
        if ver != "v2":
            continue
        items.append((arm, a.get("n_cluster_moves", 0), PURPLE))
    axes(d, boxD, max(100.0, 200.0 * math.ceil(max([x[1] for x in items] + [1]) / 200.0)),
         "次（累计）", "", xmax=6, fmt="%.0f", xticks=False)
    vmaxd = max([x[1] for x in items] + [1])
    vmaxd = 200.0 * math.ceil(vmaxd / 200.0)
    for i, (lab, val, col) in enumerate(items):
        h = (boxD[3] - boxD[1]) * val / vmaxd
        x = boxD[0] + i * (boxD[2] - boxD[0]) / 6.0 + 8
        d.rectangle([x, boxD[3] - h, x + (boxD[2] - boxD[0]) / 6.0 - 16, boxD[3]],
                    fill=col)
        d.text((x - 6, boxD[3] + 12), LBL.get(lab, lab),
               font=fnt(11), fill=SUB)
    d.text((60, 1172),
           "读法：v0 的 n_push=0（基线无推挤通道）；v1/v2 的推挤失败数随膜层数与 G 上升，"
           "因多格团簇与地面支撑提高了 J_B。", font=fnt(14), fill=SUB)
    img.save(os.path.join(IMGDIR, "t95_push.png"))
    print("saved images/t95_push.png", img.size)


# --------------------------------------------------------------- 图 2
def fig_core(ab):
    arms = [(a["version"], a["arm"], a) for a in ab["arms"]]
    img = Image.new("RGB", (2400, 1240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((60, 36), "T95：主体存留与保护效果（A/B，600 拍）", font=fnt(30, True), fill=INK)
    d.text((60, 82), "主体=初始 24×O2 刚性冻结体及其并入后代；envC=环境-主体相邻接触累计；"
                     "coreER=核心-环境反应；cov=终态角覆盖（36 扇区）。全部为原始计数；"
                     "每组 18 列，左 6=v0、中 6=v1、右 6=v2（臂序：无膜G0、无膜G.2、PK G0、PK G.2、双 G0、双 G.2）。",
           font=fnt(15), fill=SUB)
    bw = 1060 / 18.0

    def panel(box, title, key, ylab, fmtv="%.0f", ref=None, ref_lab=""):
        d.text((box[0], box[1] - 54), title, font=fnt(18, True), fill=INK)
        vals = [x[2].get(key) or 0 for x in arms]
        vmax = max(vals + [1])
        vmax = max(1.0, 1.2 * vmax)
        axes(d, box, vmax, ylab, "", xmax=18, fmt=fmtv, xticks=False)
        for i, (ver, arm, a) in enumerate(arms):
            val = a.get(key) or 0
            h = (box[3] - box[1]) * val / vmax
            x = box[0] + i * bw + 2
            d.rectangle([x, box[3] - h, x + bw - 4, box[3]],
                        fill=VCOL.get(ver, GRAY))
        for t, ver in enumerate(("v0", "v1", "v2")):
            d.text((box[0] + (t * 6 + 3) * bw, box[3] + 30), ver,
                   font=fnt(15, True), fill=VCOL[ver], anchor="ma")
        if ref is not None:
            yy = box[3] - (box[3] - box[1]) * ref / vmax
            d.line([(box[0], yy), (box[2], yy)], fill=ORANGE, width=2)
            d.text((box[2] - 10, yy - 18), ref_lab, font=fnt(13), fill=ORANGE,
                   anchor="ra")

    panel((120, 160, 1120, 560), "A 主体原子数（终/初 48）", "body_atoms_final",
          "原子数", ref=48.0, ref_lab="初始 48")
    panel((1280, 160, 2280, 560), "B 环境-主体接触累计 envC", "contacts_env_body_total",
          "次")
    panel((120, 700, 1120, 1100), "C 核心-环境反应 coreER", "core_env_react_total",
          "次")
    panel((1280, 700, 2280, 1100), "D 终态膜角覆盖 cov", "coverage_ang_final",
          "比例", fmtv="%.2f")
    legend(d, 60, 1150, [(VLAB[v], VCOL[v]) for v in ("v0", "v1", "v2")])
    d.text((1500, 1150),
           "说明：v0 无推挤通道；v1/v2 的 P1/P2 不改变化学与放置，只改变受阻时的位移规则，"
           "故 envC/coreER 差异来自动力学而非化学。", font=fnt(14), fill=SUB)
    img.save(os.path.join(IMGDIR, "t95_core.png"))
    print("saved images/t95_core.png", img.size)


# --------------------------------------------------------------- 图 3
def _run_vfield():
    """跑两局 160 拍小世界（v0 / v2 · PK_G02），取终态位置与速度画场。"""
    import t94_life as T94
    import t95_run as R
    from t95_collision import PushWorld
    pool, _meta = R.build_e4_pool(n_pool=150, seed=20261124)
    out = {}
    for stage in (0, 2):
        arm = [a for a in R.ARMS if a["key"] == "PK_G02"][0]
        p = R.arm_params(arm, quick=True)
        w = PushWorld(W=p["W"], H=p["H"], seed=20261124, env_feed=pool,
                      env_name="E4", membrane=p["membrane"], n_mem=p["n_mem"],
                      body_n=p["body_n"], food_formula=T94.FOOD_FORMULA,
                      food_n=p["food_n"], grav=p["grav"], ticks_total=160,
                      center=p["center"], body_formula=T94.BODY_FORMULA,
                      stage=stage, outer_membrane=p["outer"],
                      outer_n=p["outer_n"], push_params=R.params())
        for t in range(1, 161):
            w.t = t
            w.step()
        rows = []
        for m in w.mols:
            if m["dead"]:
                continue
            rows.append((m["r"], m["c"], m["f"],
                         float(m.get("vx", 0.0)), float(m.get("vy", 0.0)),
                         m["id"] in w.body_set,
                         m["id"] in w.membrane_ids))
        out["stage%d" % stage] = {"rows": rows, "W": w.W, "H": w.H,
                                  "center": list(w.center),
                                  "meanv": w.measure(160)["mean_abs_v"]}
    return out


def fig_vfield(ab):
    try:
        vf = _run_vfield()
    except Exception as ex:
        print("vfield 小跑失败（跳过 C/D 面板）:", ex)
        vf = None
    img = Image.new("RGB", (2400, 1240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((60, 36), "T95：速度场对比（v0 无速度场 vs v2 团簇/分子动量）", font=fnt(30, True), fill=INK)
    d.text((60, 82), "说明性 160 拍小世界（PK 膜 + G=0.2，W=120 H=80）；箭头=分子速度，长度∝|v|"
                     "（放大 6×），颜色按 |v|；灰点=静止分子。", font=fnt(15), fill=SUB)
    if vf:
        for k, stage in enumerate((0, 2)):
            box = (80 + k * 1180, 150, 1060 + k * 1180, 700)
            d.rectangle(box, outline=(70, 70, 80), width=2)
            dat = vf["stage%d" % stage]
            W, H, cen = dat["W"], dat["H"], dat["center"]
            sc = min((box[2] - box[0]) / float(W), (box[3] - box[1]) / float(H))
            ox = box[0] + ((box[2] - box[0]) - W * sc) / 2.0
            oy = box[1] + ((box[3] - box[1]) - H * sc) / 2.0
            d.text((box[0], box[1] - 28),
                   "A v0 基线（无速度场）" if stage == 0
                   else "B v2 P2（团簇动量 + 推挤）", font=fnt(17, True), fill=INK)
            # 参考圈
            for rr, col in ((7, (230, 200, 200)), (12, (230, 200, 200))):
                bb = [ox + (cen[1] - rr) * sc, oy + (cen[0] - rr) * sc,
                      ox + (cen[1] + rr) * sc, oy + (cen[0] + rr) * sc]
                d.ellipse(bb, outline=col, width=1)
            for (r, c, f, vx, vy, is_body, is_mem) in dat["rows"]:
                x = ox + c * sc
                y = oy + r * sc
                spd = math.hypot(vx, vy)
                if is_body:
                    col = (200, 50, 50)
                elif is_mem:
                    col = (60, 110, 210)
                else:
                    col = (170, 170, 180)
                d.rectangle([x, y, x + max(2, sc * 0.9), y + max(2, sc * 0.9)],
                            fill=col)
                if spd > 0.03:
                    L = min(26.0, 6.0 * spd / 0.2 * 4.0)
                    d.line([(x, y), (x + vx / spd * L, y + vy / spd * L)],
                           fill=(40, 90, 160), width=1)
        # C mean|v| 曲线
        boxC = (120, 790, 1120, 1120)
        d.text((120, 734), "C 平均速率 |v|（600 拍正式跑，v2 臂）", font=fnt(18, True), fill=INK)
        axes(d, boxC, 0.5, "格/拍", "t（拍）", xmax=600, fmt="%.2f")
        order = ["nomem_G02", "PK_G02", "double_G02"]
        cols = [GRAY, BLUE, TEAL]
        for nm, col in zip(order, cols):
            a = [x for x in ab["arms"] if x["version"] == "v2" and x["arm"] == nm]
            if not a:
                continue
            a = a[0]
            xs = [p[0] for p in a["timeline"]]
            ys = [p[5] for p in a["timeline"]]
            line(d, boxC, xs, ys, 600, 0.5, col, 3)
        legend(d, 900, 800, [(short(n), c) for n, c in zip(order, cols)])
        # D n_push 与 n_cluster_moves 对比
        boxD = (1280, 790, 2280, 1120)
        d.text((1280, 734), "D v2 各臂 n_push 与 n_cluster_moves", font=fnt(18, True), fill=INK)
        armsv2 = [a for a in ab["arms"] if a["version"] == "v2"]
        mx = max([a["n_push"] for a in armsv2] + [a.get("n_cluster_moves", 0) for a in armsv2] + [1])
        mx = 500.0 * math.ceil(mx / 500.0)
        axes(d, boxD, mx, "次（累计）", "", xmax=6, fmt="%.0f", xticks=False)
        gw = (boxD[2] - boxD[0]) / 6.0
        for i, a in enumerate(armsv2):
            for t, (key, col) in enumerate((("n_push", BLUE),
                                            ("n_cluster_moves", PURPLE))):
                val = a.get(key, 0)
                h = (boxD[3] - boxD[1]) * val / mx
                x = boxD[0] + i * gw + 6 + t * gw / 2.0
                d.rectangle([x, boxD[3] - h, x + gw / 2.0 - 10, boxD[3]], fill=col)
            d.text((boxD[0] + i * gw + gw / 2.0 - 22, boxD[3] + 20),
                   {"nomem_G00": "无膜G0", "nomem_G02": "无膜G.2",
                    "PK_G00": "PK G0", "PK_G02": "PK G.2",
                    "double_G00": "双 G0", "double_G02": "双 G.2"}[a["arm"]],
                   font=fnt(11), fill=SUB)
        legend(d, 60, 1160, [("n_push", BLUE), ("n_cluster_moves", PURPLE)])
    img.save(os.path.join(IMGDIR, "t95_vfield.png"))
    print("saved images/t95_vfield.png", img.size)


def main():
    os.makedirs(IMGDIR, exist_ok=True)
    with io.open(os.path.join(BASE, "t95_ab.json"), encoding="utf-8") as fh:
        ab = json.load(fh)
    print("arms: %d runtime %s" % (len(ab["arms"]), ab.get("runtime_s")))
    fig_push(ab)
    fig_core(ab)
    fig_vfield(ab)
    print("all images ->", IMGDIR)


if __name__ == "__main__":
    main()
