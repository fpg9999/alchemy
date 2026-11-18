# -*- coding: utf-8 -*-
"""相分类：三条正交轴，每条轴由该价数层的三元素"投票"决定。

## 规则 v4（2026-11-18 定稿：两两并列循环压制、三者全等归聚）

物质量由三个价数层构成，每层恰好三个元素，做成三条**并列、互不冲突**的轴：

======================  ==============================  ==========================
轴                       三元组                          取值
======================  ==============================  ==========================
骨架 skeleton            秩 O / 沌 K / 势 P               秩 / 沌 / 势
状态 state               晶 X / 气 A / 流 W               固 / 液 / 气
能量 energy              冰 C / 焰 F / 电 L               冰 / 焰 / 电
======================  ==============================  ==========================

**判据（默认 ``mode="hybrid"``）**

1. 该层原子数**严格最多**的元素胜出；
2. **两两并列**（恰好两个元素同为最大值）→ **循环压制**：
   ``聚 > 散 > 动 > 聚``（聚压散、散压动、动压聚）；
3. **三者全等**（三个同为最大值，含"全为 0"）→ 按 ``RULE9_PRIORITY`` 取聚素
   （``聚 > 散 > 动``），**永不产生第四相**。

循环压制是石头剪刀布式的三循环，没有绝对高低——这给动素留了胜出的路，
也是它和 v1（层级 `聚>散>动`，动素永不能赢并列）最大的区别。

## 三种模式

``hybrid``（**默认**，v4 定稿）、``hierarchy``（v1 方案）、``cycle``（v2 遗留，已弃用）：

| | 两两并列 | 三者全等 |
|---|---|---|
| ``hybrid`` | 循环压制 聚 > 散 > 动 > 聚 | 聚（按 ``RULE9_PRIORITY``，不产生第四相） |
| ``hierarchy`` | 按 ``RULE9_PRIORITY``：聚 > 散 > 动 | 聚（并进主相，不产生第四相） |
| ``cycle`` | 循环压制 聚 > 散 > 动 > 聚 | **第四相**（``〇``，v2 遗留） |

## 第四相与"无该层"（仅遗留 cycle 模式）

v4 的 ``hybrid`` / ``hierarchy`` **不产生第四相**：``FOURTH`` / ``FOURTH_NAMES`` 与
``absent_mode``（``fourth`` / ``poly`` / ``none``）只为兼容 v2 的 ``cycle`` 模式保留，
第四相 ``〇`` 在各轴显示退化为 刚体 / 固 / 冰。

cycle 下三元素全等有两种来源，必须区分：

- **真·三者全等**（三者相等且 > 0）：三种元素等量制衡 → 第四相；
- **该层全零**（三者都为 0）：根本没有这一层的元素（如 ``LF`` 没有二价原子），
  这不是"平衡"，是"缺席"；``absent_mode="none"`` 时单列为 ``ABSENT``。

全目录实测（v2 口径）：状态轴三者全等 6.42%，其中 **4.74% 是全零、只有 1.68% 是真全等**。

## 用法

    >>> import alchemy.phase as F
    >>> F.DEFAULT_MODE                        # v4 定稿
    'hybrid'
    >>> F.phase_of("OXC")["label"]            # '秩·固·冰'
    >>> F.phase_of("O2XP2WK2A2")["id"]        # 'O/A/C'
    >>> F.phase_of("OXC", mode="cycle")["n_fourth"]   # 遗留模式下才可能出现第四相
    0
"""

from __future__ import annotations

from collections import Counter

from .core.elements import CAT, ORDER, parse_formula

__all__ = [
    "RULE9_PRIORITY", "AXES", "AXIS_LABELS", "PHASE_NAMES", "FOURTH", "ABSENT",
    "FOURTH_PHASE_NAME", "FOURTH_NAMES", "FRAME_NAMES", "STATE_NAMES",
    "ENERGY_NAMES", "ENERGY_EFFECTS",
    "FRAME_ADJ", "ENERGY_ADJ", "STATE_NOUN", "TYPICAL",
    "BEATS", "CATEGORY_ORDER", "SUPPORTED_MODES",
    "ABSENT_MODES", "DEFAULT_MODE", "DEFAULT_ABSENT_MODE",
    "axis_winner", "axis_vote", "phase_of", "phase_names", "phase_id",
    "phase_label", "agree_axes", "distribution", "role_of", "state_of",
    "energy_of", "two_axis_table", "physical_name", "describe", "N_TYPES",
]

#: 与反应规则 9 完全相同的元素优先级（层级模式用）。不要另定一套。
RULE9_PRIORITY: tuple[str, ...] = ("O", "X", "C", "K", "A", "F", "P", "W", "L")

#: 大类优先级：聚 > 散 > 动（由 RULE9_PRIORITY 推出）。
CATEGORY_ORDER: tuple[str, ...] = ("聚", "散", "动")

#: 循环压制关系：聚压散、散压动、动压聚。三者成环，没有绝对最高。
BEATS: frozenset[tuple[str, str]] = frozenset({("聚", "散"), ("散", "动"), ("动", "聚")})

#: 三条轴：(键, 中文名, 三元组)。
AXES: tuple[tuple[str, str, tuple[str, str, str]], ...] = (
    ("skeleton", "骨架", ("O", "K", "P")),
    ("state", "状态", ("X", "A", "W")),
    ("energy", "能量", ("C", "F", "L")),
)

AXIS_LABELS = {k: label for k, label, _ in AXES}

#: 概念族（= 3 价层 O/K/P）的相名：骨架的**力学形态**。
#: 依据是三价主导元素决定的骨架键型（实测 S/C/L 各 60%/62%/58% 分离）：
#:
#:   秩 O(聚) -> S 短键为主 -> 不弯只断 -> 刚体
#:   沌 K(散) -> L 长键为主 -> 松散分散 -> 胶体
#:   势 P(动) -> C 角键为主 -> 铰接可弯 -> 软体
#:   第四相   -> 三种键各 1/3 -> 对称无主导 -> 晶体
FRAME_NAMES: dict[str, str] = {"O": "刚体", "K": "胶体", "P": "软体"}

#: 物态轴的相名（2 价层 X/A/W），第四相 = 虚。
STATE_NAMES: dict[str, str] = {"X": "固", "A": "气", "W": "液"}

#: 能量轴的相名（1 价层 C/F/L），第四相 = 无属性。
ENERGY_NAMES: dict[str, str] = {"C": "冰", "F": "焰", "L": "电"}

#: 能量相的实际含义（2026-11-17 修正）。
#: **注意**：这里描述的是**真实温度现象**，不是恒素密度（ρ_E），也**不引起物态相变**——
#: 物态只由组成（X/A/W）决定，相变必须靠化学反应改变组成。
ENERGY_EFFECTS: dict[str, str] = {
    "冰": "冷：降低真实温度 → 结霜、冻伤、低温现象",
    "焰": "热：升高真实温度 → 燃烧、灼烧、高温现象",
    "电": "电磁与光：导电、发光、磁性、信号传递",
    "无属性": "惰性：不导不燃不冻，绝热绝缘，不与能量场耦合",
}

#: 元素 -> 该轴的中文相名。状态轴已定（固/液/气），另两轴暂用元素本名。
PHASE_NAMES: dict[str, str] = {
    "O": "秩", "K": "沌", "P": "势",
    "X": "固", "A": "气", "W": "液",
    "C": "冰", "F": "焰", "L": "电",
}

#: 第四相占位符（三元素全等，含全零）。
FOURTH = "〇"
#: 第四相的相名 = **虚**（虚态）。定义见 docs/PHASE_RULE.md §A.6。
FOURTH_PHASE_NAME = "虚"
#: "该层全零"占位符（``absent_mode="none"`` 时才用；本方案不使用）。
ABSENT = "—"

PHASE_NAMES[FOURTH] = FOURTH_PHASE_NAME
PHASE_NAMES[ABSENT] = "无该层"

#: **每条轴各自的第四相名字**——第四相的含义因轴而异，不能共用一个名字：
#: 物态轴 = 虚（不占空间）、概念轴 = 待定、能量轴 = 待定。
FOURTH_NAMES: dict[str, str] = {
    # v4：晶体已并入刚体；虚与无属性不再存在。第四相只在遗留 cycle 模式下出现，
    # 其显示一律退化为"聚素"那一侧的结果。
    "skeleton": "刚体",
    "state": "固",
    "energy": "冰",
}

SUPPORTED_MODES = ("hybrid", "hierarchy", "cycle")
#: "该层全零"的处理方式（只在 cycle 模式下有意义）。
ABSENT_MODES = ("fourth", "poly", "none")
#: **v4 定稿**：两两并列走循环压制；三者全等（含全零）归聚。
#: 兼具 v2 的平衡性与 v3 的简洁性，且不产生第四相。
DEFAULT_MODE = "hybrid"
DEFAULT_ABSENT_MODE = "fourth"

#: 物质空间大小（3 轴 × 3 相，不含第四相）。
N_TYPES = 3 ** len(AXES)


def _pick_cycle(a: str, b: str) -> str:
    """两两并列时的循环裁决：聚压散、散压动、动压聚。"""
    ca, cb = CAT[a], CAT[b]
    if (ca, cb) in BEATS:
        return a
    if (cb, ca) in BEATS:
        return b
    raise AssertionError(f"同类并列不应出现：{a}/{b} ({ca}/{cb})")


def _pick_hierarchy(a: str, b: str) -> str:
    """两两并列时的层级裁决：按 RULE9_PRIORITY，聚 > 散 > 动。"""
    return a if RULE9_PRIORITY.index(a) < RULE9_PRIORITY.index(b) else b


def axis_vote(vec, trio, mode: str = DEFAULT_MODE,
              absent_mode: str = "fourth") -> dict:
    """一条轴的完整投票结果。

    返回 ``{'element', 'phase', 'count', 'kind', 'counts', 'tops'}``，其中 ``kind``：

    - ``'strict'`` 严格多数
    - ``'two'``    两两并列（已裁决）
    - ``'three'``  三者全等（含全零，已裁决）

    ## 三种模式

    ==========  =====================  =====================
    模式        两两并列               三者全等（含全零）
    ==========  =====================  =====================
    ``hybrid``  循环压制 聚>散>动>聚    按 聚>散>动 裁决
    ``hierarchy`` 按 聚>散>动 裁决       按 聚>散>动 裁决
    ``cycle``   循环压制               第四相（v2 遗留，已弃用）
    ==========  =====================  =====================

    ``hybrid`` 是 **v4 定稿**：两两并列走循环（让动素有机会胜出、保住液/电/软体的比例），
    三者全等归聚（此时三种元素等量制衡，取聚素作为兜底），**永不产生第四相**。
    """
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"mode 只支持 {SUPPORTED_MODES}，收到 {mode!r}")
    if absent_mode not in ABSENT_MODES:
        raise ValueError(f"absent_mode 只支持 {ABSENT_MODES}，收到 {absent_mode!r}")

    counts = {e: vec[ORDER.index(e)] for e in trio}
    mx = max(counts.values())
    tops = [e for e in trio if counts[e] == mx]
    all_zero = mx == 0 and len(tops) == 3

    if len(tops) == 1:
        el, kind = tops[0], "strict"
    elif len(tops) == 3:
        if mode == "cycle":
            # v2 遗留：三者全等 → 第四相（v4 已弃用该行为）
            if all_zero and absent_mode == "poly":
                el = min(tops, key=lambda e: RULE9_PRIORITY.index(e))
                kind = "three"
            elif all_zero and absent_mode == "none":
                el, kind = ABSENT, "absent"
            else:
                el, kind = FOURTH, "three"
        else:
            # v3 / v4：三者全等（含全零）→ 按 聚>散>动 裁决
            el = min(tops, key=lambda e: RULE9_PRIORITY.index(e))
            kind = "three"
    else:
        # 两两并列：hierarchy 走优先级，cycle / hybrid 走循环压制
        el = (_pick_hierarchy if mode == "hierarchy" else _pick_cycle)(tops[0], tops[1])
        kind = "two"

    return {
        "element": el,
        "phase": PHASE_NAMES[el],
        "count": mx,
        "kind": kind,
        "counts": counts,
        "tops": tops,
    }


def axis_winner(vec, trio, mode: str = DEFAULT_MODE, absent_mode: str = "fourth"):
    """兼容接口：返回 ``(胜出元素, 最大计数, 是否发生并列)``。

    第四相时元素为 ``"〇"``；``absent_mode="none"`` 且该层全零时为 ``"—"``。
    """
    v = axis_vote(vec, trio, mode=mode, absent_mode=absent_mode)
    return v["element"], v["count"], v["kind"] in ("two", "three")


def phase_of(formula_or_vec, mode: str = DEFAULT_MODE,
             absent_mode: str = "fourth") -> dict:
    """物质的相分类。

    参数可以是分子式字符串，也可以是 9 维元素计数向量（``ORDER`` 顺序）。

    返回 ``{'formula','vec','mode','skeleton','state','energy','axes','id','names',
    'label','n_tied_axes','n_fourth','n_absent'}``。
    """
    if isinstance(formula_or_vec, str):
        formula = formula_or_vec
        vec = parse_formula(formula)
    else:
        vec = tuple(int(x) for x in formula_or_vec)
        from .core.elements import formula_of, vec_to_atoms
        formula = formula_of(vec_to_atoms(vec))

    axes = {}
    picked = {}
    n_tied = n_fourth = n_absent = 0
    for key, label, trio in AXES:
        v = axis_vote(vec, trio, mode=mode, absent_mode=absent_mode)
        v["label"] = label
        if v["element"] == FOURTH:
            v["phase"] = FOURTH_NAMES[key]     # 每条轴的第四相名字不同
        axes[key] = v
        picked[key] = v["element"]
        if v["kind"] in ("two", "three"):
            n_tied += 1
        if v["kind"] == "three" and v["element"] == FOURTH:
            n_fourth += 1
        if v["kind"] == "absent":
            n_absent += 1

    names = tuple(axes[k]["phase"] for k, _, _ in AXES)
    return {
        "formula": formula,
        "vec": vec,
        "mode": mode,
        "absent_mode": absent_mode,
        "skeleton": picked["skeleton"],
        "state": picked["state"],
        "energy": picked["energy"],
        "axes": axes,
        "id": "/".join(picked[k] for k, _, _ in AXES),
        "names": names,
        "label": "·".join(names),
        "n_tied_axes": n_tied,
        "n_fourth": n_fourth,
        "n_absent": n_absent,
    }


def phase_names(formula_or_vec, **kw) -> tuple[str, ...]:
    """只取三个相名，如 ``('秩', '固', '冰')``。"""
    return phase_of(formula_or_vec, **kw)["names"]


def phase_id(formula_or_vec, **kw) -> str:
    """只取三元素 id，如 ``'O/X/C'``（第四相为 ``〇``，缺席为 ``—``）。"""
    return phase_of(formula_or_vec, **kw)["id"]


def phase_label(formula_or_vec, **kw) -> str:
    """可读标签，如 ``'秩·固·冰'``。"""
    return phase_of(formula_or_vec, **kw)["label"]


def agree_axes(formula_or_vec, **kw) -> int:
    """有几条轴发生了并列（含第四相），0~3。"""
    return phase_of(formula_or_vec, **kw)["n_tied_axes"]


def role_of(formula_or_vec, **kw) -> dict:
    """概念族的**骨架力学形态**：刚体 / 胶体 / 软体（v4 只有这三态）。

    依据三价主导元素决定的骨架键型倾向（S/C/L 三者各 60%/62%/58% 分离）：

    ==========  ============  ==================  ==========
    相          主导元素       骨架主导键型         力学表现
    ==========  ============  ==================  ==========
    刚体        秩 O (聚)      S 短键（共享边）     硬、不弯、受击只断
    胶体        沌 K (散)      L 长键（隔一格）     松散、分散、可吸附
    软体        势 P (动)      C 角键（共享顶点）   铰接、可弯、形变不断
    ==========  ============  ==================  ==========

    **晶体已并入刚体**（v4）：``hybrid`` / ``hierarchy`` 不产生第四相，
    这里不会再回出"晶体"；只有遗留 ``cycle`` 模式才可能出现。

    返回 ``{'element','role','kind','count','counts','fourth_source'}``。
    """
    p = phase_of(formula_or_vec, **kw)
    a = p["axes"]["skeleton"]
    role = FRAME_NAMES.get(a["element"], FOURTH_NAMES["skeleton"])
    return {"element": a["element"], "role": role, "phase": a["phase"],
            "kind": a["kind"], "count": a["count"], "counts": a["counts"],
            "fourth_source": (
                None if a["element"] != FOURTH
                else ("无骨" if a["count"] == 0 else "三键均衡")
            )}


def state_of(formula_or_vec, **kw) -> str:
    """物态的相名：固 / 液 / 气（``虚`` 只在遗留 ``cycle`` 模式出现）。"""
    return phase_of(formula_or_vec, **kw)["names"][1]


def energy_of(formula_or_vec, **kw) -> dict:
    """能量相：冰(冷) / 焰(热) / 电(电磁与光)；``无属性`` 只在遗留 ``cycle`` 模式出现。

    返回 ``{'element','energy','effect','kind','count','counts','fourth_source'}``。
    """
    p = phase_of(formula_or_vec, **kw)
    a = p["axes"]["energy"]
    name = ENERGY_NAMES.get(a["element"], FOURTH_NAMES["energy"])
    return {"element": a["element"], "energy": name,
            "effect": ENERGY_EFFECTS.get(name),
            "kind": a["kind"], "count": a["count"], "counts": a["counts"],
            "fourth_source": (
                None if a["element"] != FOURTH
                else ("无端帽" if a["count"] == 0 else "三元均衡")
            )}


def two_axis_table(formulas, **kw) -> dict:
    """概念族 × 物态 的 4×4 计数表。

    返回 ``{(概念相, 物态相): 数量}``，可直接画表。
    """
    out: dict[tuple[str, str], int] = {}
    for f in formulas:
        r = role_of(f, **kw)
        s = state_of(f, **kw)
        out[(r["role"], s)] = out.get((r["role"], s), 0) + 1
    return out


# ---------------------------------------------------------------- 物性名合成
#: 概念相 -> 形容词
FRAME_ADJ: dict[str, str] = {"刚体": "刚性", "胶体": "黏性", "软体": "松散", "晶体": "晶质"}
#: 能量相 -> 形容词
ENERGY_ADJ: dict[str, str] = {"冰": "低温", "焰": "高温", "电": "带电", "无属性": "惰性"}
#: 物态相 -> 名词
STATE_NOUN: dict[str, str] = {"固": "固体", "液": "液体", "气": "气体", "虚": "虚体"}

#: 9 格的典型对应物（概念, 物态）。v4：晶体并入刚体，虚不再存在。
TYPICAL: dict[tuple[str, str], str] = {
    ("刚体", "固"): "岩石、金属、水晶",
    ("刚体", "液"): "液态金属",
    ("刚体", "气"): "气湖 / 沉气",
    ("胶体", "固"): "泥土、杂项",
    ("胶体", "液"): "蜂蜜、泥浆",
    ("胶体", "气"): "雾、烟、霾",
    ("软体", "固"): "沙子、沙砾",
    ("软体", "液"): "水",
    ("软体", "气"): "空气、清风",
}


def physical_name(formula_or_vec, **kw) -> str:
    """由三轴合成**物性名**：``{概念形容词}{能量形容词}{物态名词}``。

    例：``OXC`` → ``刚性低温固体``（= 岩石）；``O2XCP3WK2`` → ``松散低温液体``。
    """
    r = role_of(formula_or_vec, **kw)["role"]
    s = state_of(formula_or_vec, **kw)
    e = energy_of(formula_or_vec, **kw)["energy"]
    return f"{FRAME_ADJ[r]}{ENERGY_ADJ[e]}{STATE_NOUN[s]}"


def describe(formula_or_vec, **kw) -> dict:
    """一次给出物质的三轴相、物性名、典型对应物。

    返回 ``{'formula','frame','state','energy','id','name','typical',
    'hardness','density','cohesion','gravity','energy_effect'}``。

    ``hardness`` / ``density`` / ``cohesion`` 是**概念族的相对展示档位（1~4）**，
    属于历史表现层字段，与 :mod:`alchemy.attrs` 的 27 格物性**口径不同、不可混用**；
    内核属性请直接看 :mod:`alchemy.attrs` / :mod:`alchemy.ability`。
    """
    p = phase_of(formula_or_vec, **kw)
    frame = role_of(formula_or_vec, **kw)["role"]
    state = state_of(formula_or_vec, **kw)
    en = energy_of(formula_or_vec, **kw)
    profile = _PROFILE[frame]
    return {
        "formula": p["formula"],
        "frame": frame,
        "state": state,
        "energy": en["energy"],
        "id": f"{frame}·{state}·{en['energy']}",
        "name": physical_name(formula_or_vec, **kw),
        "typical": TYPICAL.get((frame, state), ""),
        "hardness": profile[0],
        "density": profile[1],
        "cohesion": profile[2],
        "gravity": (state != "虚"),
        "energy_effect": en["effect"],
    }


#: 概念相 -> (硬度, 密度, 黏聚) 的相对档位（1~4）
_PROFILE: dict[str, tuple[int, int, int]] = {
    "刚体": (3, 4, 4),
    "晶体": (4, 3, 3),
    "胶体": (1, 2, 2),
    "软体": (2, 1, 1),
}


def distribution(formulas, axis: str | None = None, mode: str = DEFAULT_MODE,
                 absent_mode: str = DEFAULT_ABSENT_MODE) -> dict:
    """统计一批物质的相分布。``axis`` 省略时返回 27 型（含第四相）分布。"""
    if axis is None:
        c = Counter(phase_of(f, mode=mode, absent_mode=absent_mode)["id"]
                    for f in formulas)
        return dict(c.most_common())
    idx = {"skeleton": 0, "state": 1, "energy": 2}[axis]
    c = Counter(phase_of(f, mode=mode, absent_mode=absent_mode)["id"].split("/")[idx]
                for f in formulas)
    return dict(c.most_common())
