"""T87 渲染：
  images/t87_env.png    全世界 4 个时刻（色块）：看"全体下沉、分层"的时间演化
  images/t87_mover.png  两个"自主移动团簇"案例：上升团 + 横向团，各 3 帧跟随放大 + 轨迹/统计
  images/t87_mover_track.json  两个案例的轨迹点（便于复核）
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

import t84_env_skel as T84

BASE = os.path.dirname(os.path.abspath(__file__))
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"

PALETTE = [
    (228, 87, 86), (67, 114, 196), (120, 186, 106), (243, 172, 65),
    (155, 118, 200), (96, 190, 196), (220, 124, 178), (168, 160, 96),
    (238, 140, 96), (96, 150, 200), (140, 200, 150), (206, 130, 208),
    (176, 120, 96), (110, 176, 226), (200, 196, 104), (150, 130, 190),
    (226, 110, 140), (110, 170, 120),
]


def fnt(size, bold=False):
    try:
        return ImageFont.truetype(FONTB if bold else FONT, size)
    except Exception:
        return ImageFont.load_default()


def color_of(formula):
    h = hashlib.md5(formula.encode("utf-8")).digest()
    base = PALETTE[h[0] % len(PALETTE)]
    f = 0.80 + 0.30 * (h[1] / 255.0)
    return tuple(min(255, int(c * f)) for c in base)


def skel_shape(k):
    try:
        return T84.skel_shape(k)
    except Exception:
        return [(0, 0)]


def build_grid(mols):
    g = {}
    for (r, c, f, k) in mols:
        for (dr, dc) in skel_shape(k):
            g[(r + dr, c + dc)] = f
    return g


def draw_cells(d, grid, ox, oy, cell, r0, c0, sw, sh):
    for rr in range(r0, r0 + sh):
        for cc in range(c0, c0 + sw):
            f = grid.get((rr, cc))
            x0 = ox + (cc - c0) * cell
            y0 = oy + (rr - r0) * cell
            d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1],
                        fill=color_of(f) if f else (250, 250, 251))


def draw_borders(d, grid, ox, oy, cell, r0, c0, sw, sh):
    for rr in range(r0, r0 + sh):
        for cc in range(c0, c0 + sw):
            f = grid.get((rr, cc))
            if f is None:
                continue
            x0 = ox + (cc - c0) * cell
            y0 = oy + (rr - r0) * cell
            for dr, dc in ((0, 1), (1, 0)):
                nb = grid.get((rr + dr, cc + dc))
                if nb != f:
                    if dr == 0:
                        d.line([(x0 + cell - 1, y0), (x0 + cell - 1, y0 + cell)],
                               fill=(56, 56, 64), width=1 if cell < 8 else 2)
                    else:
                        d.line([(x0, y0 + cell - 1), (x0 + cell, y0 + cell - 1)],
                               fill=(56, 56, 64), width=1 if cell < 8 else 2)


def nearest(items, t, key="t"):
    return min(items, key=lambda s: abs(s[key] - t))


def main():
    res = json.load(io.open(os.path.join(BASE, "t87_env_asym_result.json"),
                            encoding="utf-8"))
    ana = json.load(io.open(os.path.join(BASE, "t87_analysis.json"),
                            encoding="utf-8"))
    snaps = res["snapshots"]
    frames = res["track"]
    W, H = res["config"]["W"], res["config"]["H"]
    movers = ana["movers"]

    # ---------------- 图1：全世界 4 时刻 ----------------
    times = [200, 600, 1000, 1400]
    cell = 4
    pw, ph = W * cell, H * cell
    pad, top = 26, 130
    gap = 20
    fig1 = Image.new("RGB", (pad * 2 + 2 * pw + gap,
                             top + 2 * (ph + 52) + 84), (250, 250, 249))
    d = ImageDraw.Draw(fig1)
    d.text((pad, 18), "T87 环境时间切片：连续重力（取消质量阈值）+ 非对称分子间作用力",
           font=fnt(28, True), fill=(28, 28, 34))
    d.text((pad, 60),
           "世界 %dx%d，7000 分子；T: 1000→10°C（t=600 到 10°C）后恒温；"
           "每个格=1 骨架，同物质同色，相邻同物质合并；整幅=全世界（上=顶，下=底）"
           % (W, H), font=fnt(16), fill=(90, 90, 100))
    for i, t in enumerate(times):
        rr = nearest(snaps, t)
        row, col = divmod(i, 2)
        ox = pad + col * (pw + gap)
        oy = top + row * (ph + 52)
        g = build_grid(rr["mols"])
        draw_cells(d, g, ox, oy, cell, 0, 0, W, H)
        draw_borders(d, g, ox, oy, cell, 0, 0, W, H)
        d.rectangle([ox, oy, ox + pw, oy + ph], outline=(80, 80, 90), width=3)
        d.text((ox, oy - 26),
               "t=%d   N=%d   格占用 %.1f%%   T=%.0f°C   团簇最大 %d"
               % (rr["t"], rr["n"], 100.0 * rr["cells_used"] / (W * H),
                  rr["T"], rr["clusters"]["max"]),
               font=fnt(17, True), fill=(40, 40, 48))
    y = top + 2 * (ph + 52) + 6
    d.text((pad, y),
           "读图：冷却结束（t=600, 10°C）时重/中质量分子已沉到下部，轻分子与无质量分子留在上方；"
           "恒温 800 拍里沉积层继续长大、悬浮相逐渐被抽空。", font=fnt(15),
           fill=(70, 70, 80))
    d.text((pad, y + 26),
           "颜色=物质分子式哈希（同色=同物质；不同物质可能碰巧同色）。",
           font=fnt(15), fill=(120, 120, 130))
    fig1.save(os.path.join(BASE, "images", "t87_env.png"))
    print("saved images/t87_env.png", fig1.size)

    # ---------------- 图2：两个 mover 案例 ----------------
    def pick(direction, min_frames=8):
        cand = [m for m in movers if m["dir"] == direction
                and m["frames"] >= min_frames]
        cand.sort(key=lambda m: -m["net"])
        return cand[0] if cand else None

    # 优先用"尺寸稳定"的 track（stable_movers），它们最能说明持续移动
    st = ana.get("stable_movers") or []
    cases = []
    for d, nm in (("上浮", "上升团（逆重力）"), ("横向", "横向漂移团"),
                  ("下沉", "下沉团（重力）")):
        pool = [m for m in st if m["dir"] == d] or []
        if pool:
            cases.append((nm, pool[0]))
    if not cases:
        up = pick("上浮")
        lat = pick("横向")
        if up:
            cases.append(("上升团（逆重力）", up))
        if lat:
            cases.append(("横向漂移团", lat))
    if not cases:
        cases = [("最快团簇", movers[0])]

    zsw, zsh, zcell = 14, 10, 52
    pad2, top2 = 26, 120
    info_w = 620
    fig2 = Image.new("RGB", (pad2 * 2 + 3 * zsw * zcell + 2 * 18 + info_w + 20,
                             top2 + len(cases) * (zsh * zcell + 74) + 70),
                     (250, 250, 249))
    d = ImageDraw.Draw(fig2)
    d.text((pad2, 16),
           "T87 自主移动团簇：逆重力上升与横向漂移的两类案例", font=fnt(26, True),
           fill=(28, 28, 34))
    d.text((pad2, 54),
           "判据：追踪帧≥6、尺寸≥5、速度≥0.06 格/拍、直线度≥0.25；红圈=该帧团簇近似范围；"
           "上升/横向方向的持续移动无法用重力解释", font=fnt(15), fill=(90, 90, 100))
    track_out = []
    for ci, (name, mv) in enumerate(cases):
        pts = mv["pts"]
        t0, t1 = pts[0][0], pts[-1][0]
        ts = [t0, t0 + (t1 - t0) // 2, t1]
        # 固定窗口：以轨迹中点为中心，三帧共用，这样团簇在窗口里可见地移动
        mid = pts[len(pts) // 2]
        zc = max(0, min(W - zsw, int(mid[2] - zsw / 2)))
        zr = max(0, min(H - zsh, int(mid[1] - zsh / 2)))
        y = top2 + ci * (zsh * zcell + 74)
        for j, t in enumerate(ts):
            fr = nearest(frames, t)
            path_pt = min(pts, key=lambda p: abs(p[0] - fr["t"]))
            cl = min(fr["clusters"],
                     key=lambda c: math.hypot(c["cr"] - path_pt[1],
                                              c["cc"] - path_pt[2]))
            ox = pad2 + j * (zsw * zcell + 18)
            g = build_grid(nearest(snaps, fr["t"])["mols"])
            draw_cells(d, g, ox, y, zcell, zr, zc, zsw, zsh)
            draw_borders(d, g, ox, y, zcell, zr, zc, zsw, zsh)
            d.rectangle([ox, y, ox + zsw * zcell, y + zsh * zcell],
                        outline=(80, 80, 90), width=3)
            d.text((ox, y - 24), "t=%d  n=%d  质心(%.0f,%.0f)"
                   % (fr["t"], cl["n"], cl["cr"], cl["cc"]),
                   font=fnt(14, True), fill=(40, 40, 48))
            # 团簇包围盒（frame 内记录的真实 bbox，裁剪到窗口内）
            r0c = max(zr, min(zr + zsh - 1, cl["r0"]))
            r1c = max(r0c, min(zr + zsh - 1, cl["r1"]))
            c0c = max(zc, min(zc + zsw - 1, cl["c0"]))
            c1c = max(c0c, min(zc + zsw - 1, cl["c1"]))
            bx0 = ox + (c0c - zc) * zcell
            by0 = y + (r0c - zr) * zcell
            bx1 = ox + (c1c - zc + 1) * zcell
            by1 = y + (r1c - zr + 1) * zcell
            if bx1 <= bx0:
                bx1 = bx0 + zcell
            if by1 <= by0:
                by1 = by0 + zcell
            d.rectangle([bx0, by0, bx1, by1], outline=(225, 30, 30), width=3)
        # 信息块
        ix = pad2 + 3 * (zsw * zcell + 18) + 10
        iy = y + 6
        d.text((ix, iy), "%s：%s" % (name, mv["dir"]),
               font=fnt(20, True), fill=(30, 30, 40))
        lines = [
            "尺寸 %d~%d（均值 %.1f），追踪 %d 帧（t=%d..%d）"
            % (mv["n_min"], mv["n_max"], mv["n_mean"], mv["frames"],
               mv["t0"], mv["t1"]),
            "速度 %.3f 格/拍，净位移 %.1f 格，直线度 %.2f"
            % (mv["speed"], mv["net"], mv["straight"]),
            "方向 dx=%.1f, dy=%.1f（负 r=向上）" % (mv["dx"], mv["dy"]),
            "平均吸引力 A=%.2f，平均排斥力 R=%.2f，质量 %.2f"
            % (mv["A_mean"], mv["R_mean"], mv["mass_mean"]),
            "主要成分：%s" % "、".join(mv["top"]),
        ]
        for k, s in enumerate(lines):
            d.text((ix, iy + 34 + k * 26), s, font=fnt(15), fill=(70, 70, 80))
        track_out.append({"name": name, "stats": {k: mv[k] for k in
                          ("t0", "t1", "frames", "n_mean", "n_min", "n_max",
                           "speed", "net", "straight", "dir", "dx", "dy",
                           "A_mean", "R_mean", "mass_mean", "top")},
                          "pts": pts})
    y = top2 + len(cases) * (zsh * zcell + 74) + 4
    d.text((pad2, y),
           "规律（本 seed）：团簇普遍在动，速度 0.03~0.13 格/拍；~1/3 向上、1/3 横向、1/3 向下——"
           "向上/横向的部分无法由重力解释，来自非对称力（A 吸 vs R 斥）的净合力。",
           font=fnt(15), fill=(70, 70, 80))
    d.text((pad2, y + 26),
           "尺寸稳定的持续 mover 只有 %d 条（1,243 条多帧 track 里）；其余多为反应并合/分裂造成的瞬态。"
           % len(st),
           font=fnt(15), fill=(70, 70, 80))
    fig2.save(os.path.join(BASE, "images", "t87_mover.png"))
    print("saved images/t87_mover.png", fig2.size)
    with io.open(os.path.join(BASE, "t87_mover_track.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(track_out, fh, ensure_ascii=False, indent=1)
    for name, mv in cases:
        print("case:", name, mv["dir"], "n=%.1f" % mv["n_mean"],
              "speed=%.3f net=%.1f straight=%.2f" % (mv["speed"], mv["net"],
                                                     mv["straight"]))


if __name__ == "__main__":
    main()
