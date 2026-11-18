# -*- coding: utf-8 -*-
"""T73c 大分子无机物：按能力+结构判定（T74 规则），不是按有没有端帽。"""
import copy
import json
from collections import Counter

import t68_shapes as S
import t69_pieces as P
import pot_all as PA
import t72_morphs as M
import t73_body as T73B
import t74_rules as R

INK = (40, 52, 66)
INK2 = (100, 116, 132)
MZH = {}
for _fam, _lst in M.MORPHS.items():
    for _e in _lst:
        MZH[_e[0]] = _e[1]


def norm(mol):
    m = copy.deepcopy(mol)
    m.setdefault("mid", m.get("key", m.get("formula")))
    for i, sk in enumerate(m["skeletons"]):
        sk.setdefault("num", i + 1)
        sk.setdefault("sid", i + 1)
        fam = S.fam_key([m["atoms"][j] for j in sk["idx"]])
        sk.setdefault("family", fam)
        sk.setdefault("family_zh", S.FAMILY.get(fam, {}).get("zh", "?"))
        sk.setdefault("n", len(sk["idx"]))
    return m


def candidates():
    out = []
    data = P.load_data()
    for mol in data["molecules"]:
        out.append((mol, "T68"))
    pool = json.load(open("t68_pool.json", encoding="utf-8"))["pool"]
    for mol in pool:
        out.append((norm(mol), "POOL"))
    return out


def page(path="images/t73_inorganic.png"):
    rows = []
    seen = set()
    for mol, src in candidates():
        key = mol.get("mol_label") or mol["formula"]
        if key in seen:
            continue
        seen.add(key)
        try:
            c = R.classify(mol)
        except Exception:
            continue
        if c["kind"] in ("活性无机物", "无机晶体") and mol["n_atoms"] >= 14:
            rows.append((c, mol))
    rows.sort(key=lambda r: (-r[0]["score"], -r[1]["n_atoms"]))
    picks = rows[:14]

    cw, ch = 780, 372
    cols = 2
    nrows = (len(picks) + cols - 1) // cols
    cv = S.Canvas(40 + cols * cw, 168 + nrows * ch, (255, 255, 255))
    cv.txt(40, 46, "T73 大分子无机物：按能力与结构判定（不是看有没有端帽）", 26, True, INK, "lm")
    cv.txt(40, 78, "有机/无机 = 结构门控生命度：≥5 有机物、3~5 活性无机物、<3 无机晶体。"
                   "状态按 X>W>A 数量，硬度按 O>P>K，高温/低温/导电按 C>L>F 数量（并列按该优先级）。",
           12.3, False, INK2, "lm")
    cv.txt(40, 102, "共 %d 个大分子被判为无机（活性无机物 %d + 无机晶体 %d），这里展示生命度最高的 14 个。" % (
        len(rows), sum(1 for r in rows if r[0]["kind"] == "活性无机物"),
        sum(1 for r in rows if r[0]["kind"] == "无机晶体")), 11.5, False, INK2, "lm")

    for i, (c, mol) in enumerate(picks):
        cc, r = i % cols, i // cols
        x = 40 + cc * cw
        y = 126 + r * ch
        cv.d.rounded_rectangle([x, y, x + cw - 18, y + ch - 18], radius=12,
                               fill=(252, 253, 255), outline=(226, 232, 238))
        info = T73B.draw_organ_body(cv, mol, (x + 12, y + 22, 330, ch - 78), max_s=40)
        organs = info.get("organs") or []
        tx = x + 356
        cnt = Counter(mol["atoms"])
        col = (0x8e, 0x44, 0xad) if c["kind"] == "活性无机物" else (0x2c, 0x3e, 0x50)
        cv.txt(tx, y + 22, mol["formula"], 15.5, True, INK, "lm")
        cv.txt(tx, y + 46, "生命分 %.1f · %s" % (c["score"], c["kind"]), 11, True, col, "lm")
        cv.txt(tx, y + 68, "状态 %s · %s · %s" % (c["state"], c["hardness"], c["thermal"]),
               11, False, INK, "lm")
        cv.txt(tx, y + 90, "·".join("%s%s×%d" % (R.ELEM_ZH.get(el, el), el, n) for el, n in cnt.items()),
               9.5, False, INK2, "lm")
        cv.txt(tx, y + 112, "%d 原子 · %d 骨架 · %d 桥" % (mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"])),
               10, False, INK2, "lm")
        cv.txt(tx, y + 138, "器官（整块外形 = 分化形态）", 10.5, True, INK, "lm")
        seen_zh = []
        yy = y + 158
        for og in organs:
            zh = MZH.get(og.get("morph"), og.get("morph"))
            reason = og.get("reason", "")
            kind = reason.split("→")[-1] if "→" in reason else "—"
            if zh in seen_zh:
                continue
            seen_zh.append(zh)
            cv.txt(tx, yy, "· %s（%s）" % (zh, kind), 10, False, INK, "lm")
            yy += 16
            if yy > y + ch - 62:
                break
        place = mol["place"]
        pl = [tuple(place[str(j)]) for j in range(len(place))] if isinstance(place, dict) else [tuple(p) for p in place]
        bt = Counter()
        for (a, b, mm) in mol["edges"]:
            bt[PA.classify_offset((pl[b][0] - pl[a][0], pl[b][1] - pl[a][1])) or "?"] += 1
        cv.txt(tx, y + ch - 56, "键：" + " · ".join("%s×%d" % ({"S": "S 短", "C": "C 角", "L": "L 长"}.get(k, k), v)
                                                   for k, v in bt.items()), 9.5, False, INK2, "lm")
        fams = sorted({(sk.get("family") or "?") for sk in mol["skeletons"]})
        cv.txt(tx, y + ch - 38, "骨架家族：" + " / ".join(S.FAMILY.get(f, {}).get("zh", f) for f in fams),
               9.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path, "rows", len(rows))


def main():
    page()


if __name__ == "__main__":
    main()
