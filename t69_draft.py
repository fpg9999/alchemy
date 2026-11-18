# -*- coding: utf-8 -*-
"""T69 草稿渲染：先出单卡目检。"""
import json
import os
import sys

from PIL import Image

import t68_shapes as S
import t69_pieces as P
import t69_draw as D
import t69_bodies as B

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "images")
CW, CH = 1540, 620

KIND_ZH = {"X": "晶X 楔块", "W": "流W 肌腱", "A": "气A 薄膜"}
TYPE_ZH = {"S": "短焊", "C": "角铰", "L": "长软"}


def panel(cv, px, y0, mol, info):
    LI = D.lib_index()
    bodies = info["bodies"]
    skmap = {}
    for b in bodies:
        skmap.setdefault(b.block["sk"], []).append(b)
    y = y0 + 8
    cv.txt(px, y, "骨架单元", 20, True, D.INK, "lm")
    y += 26
    for sknum, bs in sorted(skmap.items()):
        parts = " + ".join("单元%s %s·%d原子·#%s" % (chr(0x2460 + b.k), b.block["formula"], b.n,
                                                 LI.get(b.block["formula"], "?")) for b in bs)
        cv.txt(px, y, "骨架%d = %s" % (sknum, parts), 14, bs[0].block["formula"] and True, D.INK, "lm")
        y += 19
        if len(bs) > 1:
            fus = [fu for (ka, kb, fu) in info["fusion"]
                   if bodies.index(bodies[ka]) is not None]
            elems = "、".join(sorted(set("%s%s" % (fu.get("elements", ""), "" if fu.get("m", 1) == 1 else "×%d" % fu["m"])
                                         for (_, _, fu) in info["fusion"])))
            cv.txt(px + 12, y, "融合：两块贴边焊死（%s）" % elems, 13, False, (176, 88, 42), "lm")
            y += 18
    y += 6
    cv.txt(px, y, "连接件（二价桥）", 20, True, D.INK, "lm")
    y += 26
    for it in info["bridges"]:
        br = it["br"]
        els = it.get("elems") or []
        e0 = els[0] if els else "?"
        kind = KIND_ZH.get(e0, "%s 连接件" % e0)
        if len(set(els)) > 1:
            kind = "多元素 " + "/".join(sorted(set(els)))
        ty = "·".join("%s×%d" % (TYPE_ZH.get(t, t), list(br.get("types") or []).count(t))
                      for t in sorted(set(br.get("types") or [])))
        ska = info["skel_of"].get(it.get("ca"), "?")
        skb = info["skel_of"].get(it.get("cb"), "?")
        cv.txt(px, y, "桥%d %s" % (br["bid"] + 1, kind), 13, True, D.INK, "lm")
        cv.txt(px + 150, y, "%d原子 · %s · 骨架%s–%s" % (br.get("k", 0), ty, ska, skb),
               12, False, D.INK2, "lm")
        y += 18
    y += 6
    cv.txt(px, y, "端帽与装饰", 20, True, D.INK, "lm")
    y += 25
    mono = [mol["atoms"][m["atom"]] for m in info["geoms"]["mono"]]
    cnt = {}
    for e in mono:
        cnt[e] = cnt.get(e, 0) + 1
    cap = {"C": "冰C 尖三角", "F": "焰F 软四边形", "L": "电L 细椭圆"}
    txt = "、".join("%s×%d" % (cap.get(e, e), cnt[e]) for e in ("C", "F", "L") if cnt.get(e)) or "无"
    cv.txt(px + 4, y, "端帽 " + txt, 13, False, D.INK, "lm")
    y += 18
    cv.txt(px + 4, y, "支臂 %d 管 · 骨架内桥 %d 铆钉" % (len(info["geoms"]["arms"]),
                                                    len(info["geoms"]["intra"])),
           13, False, D.INK2, "lm")
    y += 28
    cv.txt(px, y, "元素组成", 20, True, D.INK, "lm")
    y += 25
    cv.txt(px + 4, y, P.elem_comp(mol["atoms"]), 13, False, D.INK, "lm")
    y += 19
    cv.txt(px + 4, y, "%d 原子 · %d 骨架 · %s · 全部骨架单元在 38 库内" %
           (mol["n_atoms"], len(mol["skeletons"]), mol.get("family_zh", "")),
           12, False, D.INK2, "lm")


def card(mol, path):
    cv = S.Canvas(CW, CH, (255, 255, 255))
    d = cv.d
    d.rectangle([0, 0, CW - 1, CH - 1], outline=(216, 222, 228), width=2)
    cv.txt(24, 34, mol["mid"], 28, True, D.INK, "lm")
    S.draw_formula(d, 92, 34, mol["formula"], 24, D.INK, True, center=False)
    cv.txt(92, 60, "%s · %d 原子 · %d 骨架 · %d 桥 · 元素隐去，只留骨架外轮廓" %
           (mol["exp"], mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"])),
           13, False, D.INK2, "lm")
    info = D.draw_molecule(cv, (16, 74, 900, 522), mol)
    panel(cv, 946, 76, mol, info)
    cv.save(path)
    return info


def main():
    data = P.load_data()
    by = {m["mid"]: m for m in data["molecules"]}
    for mid in sys.argv[1:] or ["G13", "G26", "G14", "G24"]:
        mol = by[mid]
        info = card(mol, os.path.join(IMG, "t69_draft_%s.png" % mid))
        print(mid, "bodies", len(info["bodies"]), "s=%.1f" % info["s"])


if __name__ == "__main__":
    main()
