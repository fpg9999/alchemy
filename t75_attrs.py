# -*- coding: utf-8 -*-
"""T75 属性系统：方块世界里的三种数值属性。

- 硬度：由三价元素（秩O / 势P / 沌K）贡献
- 粘性：由二价元素（晶X / 流W / 气A）贡献
- 温度：由一价元素（冰C / 电L / 焰F）贡献（负值=冷，正值=热，0=常温）
值 = Σ 元素个数 × 该元素权重（保留 2 位小数）。权重表集中在这里，方便整体调参。
"""
from collections import Counter

HARD_W = {"O": 1.20, "P": 0.90, "K": 0.60}      # 三价 → 硬度
STICK_W = {"X": 1.00, "W": 1.40, "A": 0.40}     # 二价 → 粘性
TEMP_W = {"C": -2.00, "L": 0.50, "F": 3.00}     # 一价 → 温度

TRI = ("O", "P", "K")
DIV = ("X", "W", "A")
MONO = ("C", "L", "F")

ELEM_ZH = {"O": "秩", "P": "势", "K": "沌", "X": "晶", "W": "流", "A": "气", "C": "冰", "L": "电", "F": "焰"}


def attrs(counts):
    """counts: dict 元素→个数。返回 {hardness, viscosity, temperature, parts}。"""
    h = sum(counts.get(e, 0) * w for e, w in HARD_W.items())
    v = sum(counts.get(e, 0) * w for e, w in STICK_W.items())
    t = sum(counts.get(e, 0) * w for e, w in TEMP_W.items())
    parts = {
        "hardness": [("%s%s" % (ELEM_ZH[e], e), counts.get(e, 0), w) for e, w in HARD_W.items() if counts.get(e, 0)],
        "viscosity": [("%s%s" % (ELEM_ZH[e], e), counts.get(e, 0), w) for e, w in STICK_W.items() if counts.get(e, 0)],
        "temperature": [("%s%s" % (ELEM_ZH[e], e), counts.get(e, 0), w) for e, w in TEMP_W.items() if counts.get(e, 0)],
    }
    return {"hardness": round(h, 2), "viscosity": round(v, 2), "temperature": round(t, 2), "parts": parts}


def attrs_of(mol):
    return attrs(Counter(mol["atoms"]))


# 参考区间：36 个稳定大分子的最大/最小值（用于画属性条）
def norm_ranges(molecules):
    hs = [attrs_of(m)["hardness"] for m in molecules]
    vs = [attrs_of(m)["viscosity"] for m in molecules]
    ts = [attrs_of(m)["temperature"] for m in molecules]
    return (0.0, max(hs) or 1.0), (0.0, max(vs) or 1.0), (min(ts), max(ts)) if min(ts) != max(ts) else (-1.0, 1.0)
