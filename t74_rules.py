# -*- coding: utf-8 -*-
"""T74 分类规则（按用户 m02223 订正）：

- 固/液/气：晶X vs 流W vs 气A 的数量，最多者决定；并列优先 X > W > A；三者相等取固。
- 刚/粘/松：秩O vs 势P vs 沌K 的数量，最多者决定；并列优先 O > P > K；三者相等取刚性。
- 高温/低温/导电：冰C vs 电L vs 焰F 的数量，最多者决定；并列优先 C > L > F（与元素表顺序一致）。
- 有机 / 无机：不看有没有端帽，按"能力 + 结构"判断（沿用 T71 的结构门控生命度）：
  生命度 ≥5 → 有机物（生命/拟生命）；3~5 → 活性无机物；<3 → 无机晶体。
"""
from collections import Counter

import t71_abilities as A71

ELEM_ZH = {"O": "秩", "P": "势", "K": "沌", "X": "晶", "W": "流", "A": "气", "C": "冰", "L": "电", "F": "焰"}


def _pick(counts, keys, names, fallback):
    vals = [(counts.get(k, 0), names[i], keys[i]) for i, k in enumerate(keys)]
    mx = max(v[0] for v in vals)
    if mx == 0:
        return fallback, 0
    for v in vals:            # 已按优先级排序，第一个达到最大值的胜出
        if v[0] == mx:
            return v[1], mx
    return fallback, 0


def physical_state(counts):
    """固/液/气：X > W > A。"""
    return _pick(counts, ["X", "W", "A"], ["固态", "液态", "气态"], "晶态")


def hardness(counts):
    """刚性/粘性/松散：O > P > K。"""
    return _pick(counts, ["O", "P", "K"], ["刚性", "粘性", "松散"], "刚性")


def thermal(counts):
    """高温/低温/导电：C > L > F。"""
    return _pick(counts, ["C", "L", "F"], ["低温", "导电", "高温"], "常温")


def life_class(mol):
    """有机/无机：按能力+结构（T71 生命度）。"""
    t = A71.molecule_traits(mol)
    score = float(t.get("life_score") or 0.0)
    cls = t.get("class")
    if cls in ("life", "proto"):
        return ("有机物", score, t)
    if cls == "active":
        return ("活性无机物", score, t)
    return ("无机晶体", score, t)


def classify(mol):
    counts = Counter(mol["atoms"])
    st, st_n = physical_state(counts)
    hd, hd_n = hardness(counts)
    th, th_n = thermal(counts)
    kind, score, t = life_class(mol)
    return {
        "state": st, "state_n": st_n,
        "hardness": hd, "hardness_n": hd_n,
        "thermal": th, "thermal_n": th_n,
        "kind": kind, "score": score,
        "counts": dict(counts),
        "traits": t,
    }
