# -*- coding: utf-8 -*-
"""追加一页：所有「活跃原子只剩 1 根键（rem=1）」的形态汇总"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t8_render_forms as R

BASE = R.BASE
forms = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))


def all_rem1(f):
    act = [r for r in f["rems"] if r > 0]
    return act and all(r == 1 for r in act)


sel = [f for f in forms if all_rem1(f)]
sel.sort(key=lambda x: (len(x["types"]), x["types"], x["size"], x["formula"]))
print("全 rem=1 的形态数:", len(sel))
for f in sel:
    print("  ", f["types"], f["formula"], "size", f["size"], "active", f["active"], f["rem_dist"])

R.make_page(BASE + r"\t8_forms_rem1.png",
            "三价元素结合完毕、只剩一根键（rem=1）的全部形态 —— 共 %d 种" % len(sel),
            "四类：{O,P} / {O,K} / {P,K} / {O,P,K}；每个活跃原子恰好还剩 1 根键（金色框）。",
            sel, ncol=5)
