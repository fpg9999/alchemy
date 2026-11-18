# -*- coding: utf-8 -*-
"""T72 骨架的分化形态库：7 个家族 × 4 种具体形态（共 28 种），每种都带功能标签。"""
import math

import t68_shapes as S
import t72_abilities as AB

INK = (30, 42, 56)


def _poly(d, pts, fill, outline, width=2):
    d.polygon(pts, fill=fill, outline=outline)
    d.line(list(pts) + [pts[0]], fill=outline, width=width)


def _ell(d, cx, cy, rx, ry, fill, outline, width=2):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)


def _path(d, pts, fill, outline, width=2):
    d.line(pts, fill=outline, width=width, joint="curve")
    d.polygon(pts, fill=fill)


def _pts_poly(cx, cy, r, n, rot=-math.pi / 2, squash=1.0):
    return [(cx + math.cos(rot + 2 * math.pi * i / n) * r,
             cy + math.sin(rot + 2 * math.pi * i / n) * r * squash) for i in range(n)]


# ------------------------------------------------------------------ 28 形态
def m_column(d, cx, cy, w, h, fill, out):
    pts = [(cx - w * 0.22, cy - h * 0.5), (cx + w * 0.22, cy - h * 0.5),
           (cx + w * 0.40, cy - h * 0.10), (cx + w * 0.40, cy + h * 0.42),
           (cx + w * 0.16, cy + h * 0.5), (cx - w * 0.16, cy + h * 0.5),
           (cx - w * 0.40, cy + h * 0.42), (cx - w * 0.40, cy - h * 0.10)]
    _poly(d, pts, fill, out)
    for f in (-0.16, 0.16):
        d.line([cx + w * f, cy - h * 0.46, cx + w * f * 1.7, cy + h * 0.44], fill=out, width=1)


def m_cluster(d, cx, cy, w, h, fill, out):
    for ang, ln in ((-90, 0.52), (-140, 0.40), (-40, 0.40), (-165, 0.26), (-15, 0.26)):
        a = math.radians(ang)
        tipx, tipy = cx + math.cos(a) * w * ln, cy + math.sin(a) * h * ln
        bx, by = math.cos(a + math.pi / 2), math.sin(a + math.pi / 2)
        _poly(d, [(cx + bx * w * 0.12, cy + by * w * 0.12),
                  (cx - bx * w * 0.12, cy - by * w * 0.12), (tipx, tipy)], fill, out, 1)
    _ell(d, cx, cy + h * 0.30, w * 0.22, h * 0.14, fill, out, 1)


def m_spine(d, cx, cy, w, h, fill, out):
    _poly(d, [(cx, cy - h * 0.55), (cx + w * 0.18, cy - h * 0.05),
              (cx + w * 0.10, cy + h * 0.5), (cx - w * 0.10, cy + h * 0.5),
              (cx - w * 0.18, cy - h * 0.05)], fill, out)
    for yy in (0.0, 0.22):
        d.line([cx - w * 0.12, cy + h * yy, cx + w * 0.12, cy + h * (yy + 0.10)], fill=out, width=1)


def m_lattice(d, cx, cy, w, h, fill, out):
    _poly(d, _pts_poly(cx, cy, w * 0.46, 6, squash=h / w), fill, out)
    _poly(d, _pts_poly(cx, cy, w * 0.20, 6, squash=h / w), (255, 255, 255), out, 1)
    for i in range(3):
        a = math.radians(30 + 120 * i)
        d.line([cx + math.cos(a) * w * 0.20, cy + math.sin(a) * h * 0.4,
                cx + math.cos(a) * w * 0.44, cy + math.sin(a) * h * 0.44], fill=out, width=1)


def m_sac(d, cx, cy, w, h, fill, out):
    pts = [(cx - w * 0.42, cy), (cx - w * 0.26, cy - h * 0.36), (cx + w * 0.10, cy - h * 0.40),
           (cx + w * 0.40, cy - h * 0.14), (cx + w * 0.40, cy + h * 0.22),
           (cx + w * 0.10, cy + h * 0.42), (cx - w * 0.24, cy + h * 0.34)]
    _poly(d, pts, fill, out)
    _ell(d, cx - w * 0.02, cy + h * 0.02, w * 0.16, h * 0.16, (255, 255, 255), out, 1)


def m_pump(d, cx, cy, w, h, fill, out):
    _ell(d, cx - w * 0.18, cy, w * 0.26, h * 0.38, fill, out)
    _ell(d, cx + w * 0.18, cy, w * 0.26, h * 0.38, fill, out)
    d.line([cx - w * 0.02, cy - h * 0.10, cx + w * 0.02, cy + h * 0.10], fill=out, width=2)
    d.arc([cx - w * 0.30, cy - h * 0.52, cx + w * 0.30, cy + h * 0.10], 200, 340, fill=out, width=1)


def m_bladder(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy, w * 0.40, h * 0.42, fill, out)
    for i in range(3):
        x = cx - w * 0.18 + i * w * 0.18
        d.arc([x - w * 0.16, cy - h * 0.34, x + w * 0.16, cy + h * 0.34], 250, 290, fill=out, width=1)


def m_reservoir(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy, w * 0.42, h * 0.40, fill, out)
    d.ellipse([cx - w * 0.26, cy - h * 0.24, cx + w * 0.26, cy + h * 0.24], outline=out, width=2)
    for i in range(5):
        a = 2 * math.pi * i / 5
        d.ellipse([cx + math.cos(a) * w * 0.14 - 1.6, cy + math.sin(a) * h * 0.14 - 1.6,
                   cx + math.cos(a) * w * 0.14 + 1.6, cy + math.sin(a) * h * 0.14 + 1.6], fill=out)


def m_polybud(d, cx, cy, w, h, fill, out):
    _poly(d, _pts_poly(cx, cy, w * 0.34, 5, squash=h / w), fill, out)
    for ang in (-30, 90, 210):
        a = math.radians(ang)
        bx, by = cx + math.cos(a) * w * 0.30, cy + math.sin(a) * h * 0.26
        _ell(d, bx, by, w * 0.17, h * 0.17, fill, out, 1)


def m_split(d, cx, cy, w, h, fill, out):
    _ell(d, cx - w * 0.16, cy, w * 0.28, h * 0.40, fill, out)
    _ell(d, cx + w * 0.16, cy, w * 0.28, h * 0.40, fill, out)
    d.line([cx, cy - h * 0.36, cx, cy + h * 0.36], fill=out, width=1)


def m_gluepad(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy + h * 0.14, w * 0.42, h * 0.22, fill, out)
    for i in range(5):
        x = cx - w * 0.34 + i * w * 0.17
        d.line([x, cy + h * 0.02, x + math.sin(i) * w * 0.05, cy + h * 0.42], fill=out, width=1)


def m_pyramid(d, cx, cy, w, h, fill, out):
    _poly(d, [(cx, cy - h * 0.5), (cx + w * 0.40, cy + h * 0.38), (cx - w * 0.40, cy + h * 0.38)], fill, out)
    d.line([cx, cy - h * 0.5, cx, cy + h * 0.38], fill=out, width=1)


def m_arch(d, cx, cy, w, h, fill, out):
    pts = [(cx - w * 0.46, cy + h * 0.40), (cx - w * 0.40, cy - h * 0.10),
           (cx - w * 0.18, cy - h * 0.44), (cx + w * 0.18, cy - h * 0.44),
           (cx + w * 0.40, cy - h * 0.10), (cx + w * 0.46, cy + h * 0.40),
           (cx + w * 0.24, cy + h * 0.40), (cx + w * 0.22, cy - h * 0.02),
           (cx, cy - h * 0.26), (cx - w * 0.22, cy - h * 0.02),
           (cx - w * 0.24, cy + h * 0.40)]
    _poly(d, pts, fill, out)


def m_wing(d, cx, cy, w, h, fill, out):
    pts = [(cx - w * 0.46, cy + h * 0.30), (cx - w * 0.10, cy - h * 0.42),
           (cx + w * 0.46, cy - h * 0.28), (cx + w * 0.30, cy + h * 0.10),
           (cx + w * 0.46, cy + h * 0.36), (cx - w * 0.02, cy + h * 0.20)]
    _poly(d, pts, fill, out)
    for i in range(3):
        d.line([cx - w * 0.28 + i * w * 0.18, cy + h * 0.18, cx - w * 0.12 + i * w * 0.18, cy - h * 0.24],
               fill=out, width=1)


def m_sucker(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy - h * 0.06, w * 0.40, h * 0.34, fill, out)
    d.arc([cx - w * 0.22, cy + h * 0.04, cx + w * 0.22, cy + h * 0.46], 0, 180, fill=out, width=2)
    d.arc([cx - w * 0.34, cy - h * 0.02, cx + w * 0.34, cy + h * 0.40], 0, 180, fill=out, width=1)


def m_crystal_pump(d, cx, cy, w, h, fill, out):
    _poly(d, [(cx - w * 0.40, cy + h * 0.34), (cx - w * 0.30, cy - h * 0.20),
              (cx, cy - h * 0.46), (cx + w * 0.30, cy - h * 0.20),
              (cx + w * 0.40, cy + h * 0.34)], fill, out)
    _ell(d, cx, cy + h * 0.10, w * 0.14, h * 0.14, (255, 255, 255), out, 1)


def m_shield(d, cx, cy, w, h, fill, out):
    pts = [(cx - w * 0.42, cy - h * 0.40), (cx + w * 0.42, cy - h * 0.40),
           (cx + w * 0.34, cy + h * 0.16), (cx, cy + h * 0.48),
           (cx - w * 0.34, cy + h * 0.16)]
    _poly(d, pts, fill, out)
    d.line([cx, cy - h * 0.34, cx, cy + h * 0.40], fill=out, width=1)


def m_scale(d, cx, cy, w, h, fill, out):
    for i in range(3):
        cx2 = cx - w * 0.26 + i * w * 0.26
        d.arc([cx2 - w * 0.20, cy - h * 0.30, cx2 + w * 0.20, cy + h * 0.26],
              200, 340, fill=out, width=2)
    for i in range(2):
        cx2 = cx - w * 0.13 + i * w * 0.26
        d.arc([cx2 - w * 0.20, cy + h * 0.04, cx2 + w * 0.20, cy + h * 0.60],
              200, 340, fill=out, width=2)


def m_spike_shield(d, cx, cy, w, h, fill, out):
    m_shield(d, cx, cy, w, h, fill, out)
    for ang in (-150, -90, -30):
        a = math.radians(ang)
        d.line([cx + math.cos(a) * w * 0.40, cy + math.sin(a) * h * 0.40,
                cx + math.cos(a) * w * 0.58, cy + math.sin(a) * h * 0.58], fill=out, width=2)


def m_socket(d, cx, cy, w, h, fill, out):
    m_shield(d, cx, cy, w, h, fill, out)
    _ell(d, cx, cy + h * 0.02, w * 0.16, h * 0.16, (255, 255, 255), out, 1)


def m_ball(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy, w * 0.38, h * 0.40, fill, out)
    d.arc([cx - w * 0.38, cy - h * 0.10, cx + w * 0.38, cy + h * 0.62], 200, 340, fill=out, width=1)


def m_round_sac(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy, w * 0.42, h * 0.42, fill, out)
    d.ellipse([cx - w * 0.24, cy - h * 0.24, cx + w * 0.24, cy + h * 0.24], outline=out, width=1)


def m_store_chamber(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy, w * 0.44, h * 0.34, fill, out)
    for f in (-0.16, 0.16):
        d.line([cx + w * f, cy - h * 0.32, cx + w * f, cy + h * 0.32], fill=out, width=1)
    _ell(d, cx, cy, w * 0.08, h * 0.10, (255, 255, 255), out, 1)


def m_pulse_node(d, cx, cy, w, h, fill, out):
    d.ellipse([cx - w * 0.42, cy - h * 0.34, cx + w * 0.42, cy + h * 0.34], outline=out, width=3)
    d.line([cx - w * 0.42, cy, cx - w * 0.16, cy], fill=out, width=2)
    d.line([cx + w * 0.16, cy, cx + w * 0.42, cy], fill=out, width=2)
    _ell(d, cx, cy, w * 0.12, h * 0.18, fill, out, 1)


def m_master(d, cx, cy, w, h, fill, out):
    _poly(d, _pts_poly(cx, cy, w * 0.40, 6, squash=h / w), fill, out)
    d.ellipse([cx - w * 0.22, cy - h * 0.20, cx + w * 0.22, cy + h * 0.20], outline=out, width=2)
    for ang in (-60, 60, 180):
        a = math.radians(ang)
        d.line([cx + math.cos(a) * w * 0.38, cy + math.sin(a) * h * 0.34,
                cx + math.cos(a) * w * 0.60, cy + math.sin(a) * h * 0.56], fill=out, width=1)


def m_hypha(d, cx, cy, w, h, fill, out):
    for ang in (-90, -20, 140):
        a = math.radians(ang)
        pts = []
        for t in (0.0, 0.35, 0.7, 1.0):
            pts.append((cx + math.cos(a) * w * 0.52 * t,
                        cy + math.sin(a) * h * 0.52 * t))
        d.line(pts, fill=out, width=3, joint="curve")
        d.line(pts, fill=(255, 255, 255), width=1, joint="curve")
    _ell(d, cx, cy, w * 0.13, h * 0.13, fill, out, 1)


def m_diff_bud(d, cx, cy, w, h, fill, out):
    _ell(d, cx, cy + h * 0.10, w * 0.26, h * 0.28, fill, out)
    for ang, r in ((-125, 0.34), (-55, 0.34), (-90, 0.52)):
        a = math.radians(ang)
        _ell(d, cx + math.cos(a) * w * r, cy + math.sin(a) * h * r, w * 0.13, h * 0.13, fill, out, 1)


def m_ganglion(d, cx, cy, w, h, fill, out):
    _poly(d, _pts_poly(cx, cy, w * 0.22, 8), fill, out)
    for i in range(6):
        a = math.radians(60 * i)
        d.line([cx + math.cos(a) * w * 0.20, cy + math.sin(a) * h * 0.20,
                cx + math.cos(a) * w * 0.48, cy + math.sin(a) * h * 0.48], fill=out, width=1)
        d.ellipse([cx + math.cos(a) * w * 0.48 - 2, cy + math.sin(a) * h * 0.48 - 2,
                   cx + math.cos(a) * w * 0.48 + 2, cy + math.sin(a) * h * 0.48 + 2], fill=out)


MORPHS = {
    "O": [("column", "晶柱", m_column, ["tensile", "dense", "laminate"], "高瘦立柱：抗拉、层状、导光"),
          ("cluster", "晶簇", m_cluster, ["crystallize", "cleavage", "rigid"], "一丛尖晶：结晶、解理、刺防"),
          ("spine", "尖晶刺", m_spine, ["cleavage", "self_heal", "presso"], "单根长刺：穿刺、断口自愈"),
          ("frame", "晶格框", m_lattice, ["porous", "laminate", "insulate"], "带孔的晶格框：过滤、绝缘")],
    "P": [("sac", "势囊", m_sac, ["store", "osmosis", "tough"], "柔软囊体：储能、调压"),
          ("pump", "泵核", m_pump, ["pump", "catalyze", "release"], "双腔泵核：泵送、催化"),
          ("bladder", "胀囊", m_bladder, ["jerk", "store", "release"], "可鼓胀的气囊：蓄势弹射"),
          ("reservoir", "储腔", m_reservoir, ["store", "dense", "press"], "厚壁储腔：长期蓄能")],
    "K": [("polybud", "多面芽", m_polybud, ["differentiate", "bud", "adhere"], "多面体芽：分化、出芽、粘合"),
          ("split", "分裂盘", m_split, ["divide", "regenerate", "metamorph"], "可一分为二的盘：分裂、变态"),
          ("gluepad", "粘合座", m_gluepad, ["adhere", "fuse", "press"], "带黏毛的底座：把器官焊在一起"),
          ("pyramid", "棱锥", m_pyramid, ["cleavage", "compress", "rigid"], "硬棱锥：抗压、解理")],
    "OP": [("arch", "拱脊", m_arch, ["tensile", "pump", "compress"], "拱形脊：抗弯 + 内部泵道"),
           ("wing", "膜翼", m_wing, ["drift", "synthesis", "thermo_taxis"], "薄翼：滑翔、受光"),
           ("sucker", "吸盘", m_sucker, ["adhere", "chemo", "osmosis"], "带缘的吸盘：吸附、采样"),
           ("cpump", "晶泵", m_crystal_pump, ["pump", "store", "crystallize"], "晶体外壳里的泵腔")],
    "OK": [("shield", "盾甲", m_shield, ["compress", "press", "rigid"], "整块盾甲：抗压、防撞"),
           ("scale", "鳞片", m_scale, ["laminate", "camo", "acid"], "叠层鳞：耐蚀、伪装"),
           ("spike", "刺盾", m_spike_shield, ["cleavage", "compress", "presso"], "带外刺的盾：防御反击"),
           ("socket", "眶甲", m_socket, ["memory", "presso", "crystallize"], "开孔的甲：嵌合其他器官")],
    "PK": [("ball", "关节球", m_ball, ["joint", "tough", "crawl"], "球关节：可转动、缓冲"),
           ("rsac", "圆囊", m_round_sac, ["store", "osmosis", "tough"], "圆囊：储液、调压"),
           ("chamber", "存储腔", m_store_chamber, ["store", "insulate", "press"], "分格储腔：保温储存"),
           ("pulse", "胀节", m_pulse_node, ["pump", "jerk", "crawl"], "会搏动的节：推动体液")],
    "OPK": [("master", "主控腔", m_master, ["differentiate", "encode", "memory"], "带核心的腔：统筹、编码、记忆"),
            ("hypha", "菌丝节", m_hypha, ["symbiosis", "receive", "chemo_taxis"], "放射菌丝：连接、感知浓度"),
            ("bud", "分化芽", m_diff_bud, ["differentiate", "bud", "regenerate"], "多个芽头：长成不同器官"),
            ("ganglion", "神经节", m_ganglion, ["pulse", "emit", "swarm"], "星状节点：脉冲、群体协调")],
}

FAM_ORDER = ["O", "P", "K", "OP", "OK", "PK", "OPK"]


def morph_list(fam):
    return MORPHS.get(fam, MORPHS["OPK"])


def pick_morphs(fam, counts, n3=1, seed=0):
    """按家族选 3 种可长成的具体形态；用 seed 旋转，避免同家族所有块都长成同样三种。"""
    items = MORPHS[fam]

    def score(it):
        sc = 0.0
        for t in it[3]:
            info = AB.ABIL.get(t)
            if not info:
                continue
            for el, w in info["elems"].items():
                sc += w * counts.get(el, 0)
        return sc

    cand = sorted(items, key=lambda it: -score(it))
    k = seed % len(cand)
    cand = cand[k:] + cand[:k]
    return [it[0] for it in cand[:3]]


def draw_morph(cv, cx, cy, w, h, key, fam, tint=None, alpha=None):
    """按 key 画一个分化形态。tint 默认用家族色。"""
    from t72_abilities import CAT_COL  # noqa: F401  (仅避免循环)
    col = tint or S.FAMILY.get(fam, S.FAMILY["OPK"])["col"]
    fill = S.lighten(col, 0.86)
    for (k, zh, fn, tags, desc) in morph_list(fam):
        if k == key:
            fn(cv.d, cx, cy, w, h, fill, col)
            return zh
    fam0 = fam
    fn = morph_list(fam0)[0][2]
    fn(cv.d, cx, cy, w, h, fill, col)
    return morph_list(fam0)[0][1]
