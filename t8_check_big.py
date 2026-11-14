# -*- coding: utf-8 -*-
"""结构化大计数抽检：计数到 60/类，检查是否出现库外骨架"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import t8_level6_forms as T

BASE = r"G:\AI work\deepseek\work1\alchemy"
lib = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
lib_keys = {(P.mol_label(f["atoms"], [tuple(e) for e in f["edges"]]),
             tuple(sorted(f["rems"])), tuple(sorted(f["atoms"]))) for f in lib}

tests = [(30, 30, 30), (60, 0, 60), (40, 40, 0), (0, 45, 45), (36, 36, 36),
         (20, 60, 20), (50, 20, 50), (60, 60, 60), (12, 7, 2), (24, 14, 4)]
new = []
mx = ma = 0
for c in tests:
    comps = T.level6_components(c)
    for comp in comps:
        mx = max(mx, len(comp["atoms"]))
        ma = max(ma, sum(1 for r in comp["rems"] if r > 0))
        k = (comp["label"], tuple(sorted(comp["rems"])), tuple(sorted(comp["atoms"])))
        if k not in lib_keys:
            new.append((c, T.formula_of(comp["atoms"])))
    print(c, "组件数:", len(comps), "最大:", max(len(x["atoms"]) for x in comps) if comps else 0,
          "公式:", [T.formula_of(x["atoms"]) for x in comps][:8], flush=True)
print("新形态:", len(new), new[:5])
print("总最大组件:", mx, "最大活跃:", ma)
