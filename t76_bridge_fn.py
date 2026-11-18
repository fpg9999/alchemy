# -*- coding: utf-8 -*-
"""T76 桥的功用标签：桥只负责“连”，但不同元素的桥连法不同，功能也不同。

判定输入：桥的原子序列（按链序）+ 该桥两端骨架的属性对比 + 同一对骨架之间的并联桥数。
输出：功能标签（中文名）、功能代码、判定理由。
"""

FUNCS = {
    "weld":     ("刚性焊接", "weld",     "把两块骨架固定成一个刚体，传力但不允许相对运动"),
    "anchor":   ("承重锚固", "anchor",   "把载荷沿桥轴传到另一块骨架，抗拉/抗剪"),
    "hinge":    ("铰接关节", "hinge",    "允许两块骨架相对转动/折角，像门轴"),
    "tendon":   ("可伸缩肌腱", "tendon",  "能拉伸回弹，吸收冲击、储存弹性能"),
    "cable":    ("牵拉缆索", "cable",    "长距离承拉，把远端骨架拉向主体"),
    "gap":      ("隔空软连", "gap",      "两块骨架不接触也能联动，留出空隙"),
    "buffer":   ("缓冲气囊", "buffer",   "受挤压时压缩缓冲，减震/浮动"),
    "insulate": ("隔热隔振", "insulate", "阻断热与振动传递，只保留弱连接"),
    "rigidflex":("刚柔复合", "rigidflex","一端锁死一端可弯：既定位又能微调"),
    "damper":   ("阻尼传动", "damper",   "把运动经可变形段传出去，带阻尼/滞后"),
    "braid":    ("多点编织", "braid",    "多段不同元素交替编成，分担载荷又保留柔性"),
    "bundle":   ("并联加固", "bundle",   "同一对骨架之间多根桥并行，整体更牢"),
    "spacer":   ("定距隔空", "spacer",   "刚性件 + 空腔：把两块骨架固定在固定间距，中间不传热/不传振"),
}

ELEM_ROLE = {"X": "刚", "W": "柔", "A": "空"}


def bridge_chain(bridge):
    """桥原子按链序排列。"""
    if "chain" in bridge and bridge["chain"]:
        return list(bridge["chain"])
    return list(bridge.get("idx", []))


def classify(bridge, mol, parallel=1):
    """返回 (key, 中文名, 理由)。"""
    elems = [mol["atoms"][i] for i in bridge_chain(bridge)]
    k = len(elems)
    n_x = elems.count("X")
    n_w = elems.count("W")
    n_a = elems.count("A")
    kinds = {ELEM_ROLE[e] for e in elems if e in ELEM_ROLE}

    def _mk(key, why):
        zh, code, desc = FUNCS[key]
        return (key, zh, desc, why)

    # 多元素：按组成定复合功能
    if n_x and n_w and n_a:
        return _mk("braid", "%s 刚柔空三段编成" % "-".join(elems),)
    if n_x and n_a:
        return _mk("spacer", "%s 刚性件+空腔" % "-".join(elems),)
    if n_x and n_w:
        return _mk("rigidflex", "%s 刚柔混编" % "-".join(elems),)
    if n_w and n_a:
        if k >= 3:
            return _mk("braid", "%s 柔-空交替" % "-".join(elems),)
        return _mk("damper", "%s 柔+空" % "-".join(elems),)

    # 单元素
    if n_x == k:
        key = "weld" if k == 1 else "anchor"
        return _mk(key, "%d 个晶原子（%s）" % (k, "单点焊死" if k == 1 else "整段刚性"),)
    if n_w == k:
        key = "hinge" if k == 1 else ("tendon" if k == 2 else "cable")
        return _mk(key, "%d 个流原子（%s）" % (k, {1: "单关节", 2: "双段可伸", }.get(k, "长链承拉")),)
    if n_a == k:
        key = "gap" if k == 1 else ("buffer" if k == 2 else "insulate")
        return _mk(key, "%d 个气原子（%s）" % (k, {1: "单点隔空", 2: "双段缓冲"}.get(k, "长段隔热")),)
    return _mk("weld", "其他",)


def all_bridges(mol):
    """返回该分子每条桥的 (bid, 功能key, 中文名, 理由, 元素串, 端点)"""
    out = []
    # 统计同一对骨架之间的并联桥数
    pair_count = {}
    for br in mol["bridges"]:
        comps = br.get("comps") or []
        key = tuple(sorted(comps)) if len(comps) >= 2 else tuple(sorted(br.get("bonds_to_skel", {}).keys()))
        pair_count[key] = pair_count.get(key, 0) + 1
    for br in mol["bridges"]:
        comps = br.get("comps") or []
        key = tuple(sorted(comps)) if len(comps) >= 2 else tuple(sorted(br.get("bonds_to_skel", {}).keys()))
        par = pair_count.get(key, 1)
        fk, zh, desc, why = classify(br, mol, par)
        elems = [mol["atoms"][i] for i in bridge_chain(br)]
        out.append({
            "bid": br.get("bid"),
            "par": par,
            "bundle": par >= 2,
            "fn": fk,
            "fn_zh": zh,
            "desc": desc,
            "why": why,
            "elems": "".join(elems),
            "k": len(elems),
            "comps": comps,
        })
    return out


def stats(mols):
    from collections import Counter
    c = Counter()
    for mol in mols:
        for b in all_bridges(mol):
            c[b["fn"]] += 1
    return c


def fanout(mols):
    """桥 → 被哪些骨架使用（功能分摊表）。"""
    from collections import defaultdict
    d = defaultdict(list)
    for mol in mols:
        for b in all_bridges(mol):
            d[b["fn"]].append((mol["mid"], b["bid"], b["elems"], b.get("par", 1)))
    return d
