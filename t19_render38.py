# -*- coding: utf-8 -*-
"""t19_render38.py：38 种 6 级中间态骨架完整字典（一张图）"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
forms = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
forms.sort(key=lambda f: (f["size"], f["formula"]))
print("forms:", len(forms))
R.make_page(BASE + r"\images\t19_level6_library38.png",
            "6 级中间态骨架完整字典（38 种 = 3 孤立单原子 + 35 多原子形态）",
            "6 级 = 只连「异类三价原子」（周期表距离 6）的阶段；这些块再经 0 级同类键（O–O/P–P/K–K）加固/融合成终态骨架。",
            forms, ncol=8, pw=240, ph=250)
