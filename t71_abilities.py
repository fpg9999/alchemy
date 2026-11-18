# -*- coding: utf-8 -*-
"""T71 能力 / 分化 / 有机-无机涌现。

设计原则
--------
1) **能力来自元素**：九种元素各自对应若干"能力"，分子里某种元素越多，这类能力的等级越高。
2) **骨架都会分化**：38 库里的每个骨架形态（6 级骨架块）都含三价元素，因此都有分化能力；
   分化出哪种形态，由它在分子里"接了几个骨架、长了几根触肢"决定（结构 → 形态，而不是预先指定）。
3) **有机 / 无机是涌现出来的**：把"分化 + 运动 + 感知 + 储能 + 抓取 + 自修复 + 共生"这些能力
   按分子实际结构累加成分数，分数越高越像生命；不是看某个元素，而是看组合。
4) **固态 / 液态 / 气态**：按 X(晶)、W(流)、A(气) 的数量，晶最多=固、流最多=液、气最多=气，
   并列时 X > W > A（晶优先，其次流，其次气），三者相等仍取固。
5) **刚性 / 松散 / 粘性**（暂行推断，等同事上传正式规则后替换）：统计分子内 S/C/L 键的占比，
   S 最多=刚性、L 最多=松散、C 最多=粘性。
"""
import json
import os
from collections import Counter, defaultdict

import pot_all as P

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 能力表
# 能力名: (中文, 类别)。类别 org=生命向 / inorg=材料向
ABIL = {
    "support":   ("结构支撑", "inorg"),
    "rigid":     ("刚性", "inorg"),
    "heat":      ("耐热", "inorg"),
    "dense":     ("致密", "inorg"),
    "insulate":  ("绝缘", "inorg"),
    "conduct":   ("导电", "inorg"),
    "heal":      ("自修复", "org"),
    "sense":     ("感知", "org"),
    "shape_s":   ("形变", "org"),
    "move":      ("移动", "org"),
    "pump":      ("泵送", "org"),
    "flex":      ("柔韧", "org"),
    "store":     ("储能", "org"),
    "elastic":   ("弹性", "org"),
    "catalyze":  ("催化", "org"),
    "differentiate": ("分化", "org"),
    "regenerate": ("再生", "org"),
    "adhere":    ("粘合", "org"),
    "mutate":    ("变异", "org"),
    "float":     ("浮力", "org"),
    "adsorb":    ("吸附", "org"),
    "volatile":  ("挥发", "org"),
    "grasp":     ("抓取", "org"),
    "cold":      ("耐寒", "inorg"),
    "glow":      ("发光", "org"),
    "cut":       ("切割", "org"),
    "defend":    ("防御", "org"),
    "climb":     ("攀附", "org"),
    "charge":    ("放电", "org"),
    "signal":    ("信号", "org"),
}

ELEM_ABIL = {
    "O": [("support", 2), ("heal", 2), ("sense", 1), ("insulate", 1)],
    "X": [("rigid", 2), ("heat", 2), ("dense", 1), ("insulate", 1)],
    "C": [("grasp", 2), ("cold", 1), ("adhere", 1), ("sense", 1)],
    "P": [("store", 2), ("elastic", 2), ("catalyze", 1), ("differentiate", 1)],
    "W": [("move", 2), ("pump", 2), ("flex", 1), ("signal", 1)],
    "L": [("conduct", 2), ("signal", 2), ("charge", 1), ("sense", 1)],
    "K": [("differentiate", 2), ("regenerate", 2), ("adhere", 1), ("mutate", 1)],
    "A": [("float", 2), ("adsorb", 2), ("insulate", 1), ("volatile", 1)],
    "F": [("heat", 1), ("cut", 2), ("glow", 2), ("defend", 1)],
}

# 一个"能力等级"最多 3；同种能力多来源时取较高者，再按该元素数量升级
def _level(cnt):
    if cnt <= 0:
        return 0
    if cnt == 1:
        return 1
    if cnt <= 3:
        return 2
    return 3


def abilities_of(counts):
    """元素计数向量 → {ability: level}"""
    out = {}
    for el, n in counts.items():
        if not n:
            continue
        lv = _level(n)
        for key, base in ELEM_ABIL.get(el, []):
            v = min(3, base + (lv - 1))
            out[key] = max(out.get(key, 0), v)
    return out


# ---------------------------------------------------------------- 状态 / 软硬
def physical_state(counts):
    nx, nw, na = counts.get("X", 0), counts.get("W", 0), counts.get("A", 0)
    if nx == 0 and nw == 0 and na == 0:
        return "晶态", "无二价元素，按纯骨架晶体处理"
    # 规则：数量最多者决定；并列时 X > W > A（晶优先→固，流优先→液，气优先→气）
    best = max((nx, 3, "固态"), (nw, 2, "液态"), (na, 1, "气态"))
    # max 先比数量，再比优先级（3/2/1）
    mx = max(nx, nw, na)
    if nx == mx:
        return "固态", "晶X最多（并列时晶优先）"
    if nw == mx:
        return "液态", "流W最多（并列时流优先）"
    return "气态", "气A最多（并列时气优先）"


def softness(mol):
    """刚性 / 松散 / 粘性：暂行推断（S/C/L 键占比）。"""
    cnt = Counter()
    place = mol["place"]
    for (i, j, m) in mol["edges"]:
        dq = place[j][0] - place[i][0]
        dr = place[j][1] - place[i][1]
        t = P.classify_offset((dq, dr))
        cnt[t] += m
    s, c, l = cnt.get("S", 0), cnt.get("C", 0), cnt.get("L", 0)
    total = s + c + l
    if total == 0:
        return "刚性", {"S": 0, "C": 0, "L": 0}
    if s >= c and s >= l:
        return "刚性", {"S": s, "C": c, "L": l}
    if l >= c:
        return "松散", {"S": s, "C": c, "L": l}
    return "粘性", {"S": s, "C": c, "L": l}


# ---------------------------------------------------------------- 分化形态
FAMILY_PREFIX = {
    "O": ("晶格", "晶柱", "晶刺"),
    "P": ("势囊", "泵核", "储能腔"),
    "K": ("多面芽", "分裂盘", "粘合座"),
    "OP": ("拱脊", "膜翼", "吸盘"),
    "OK": ("盾甲", "鳞片", "刺盾"),
    "PK": ("圆囊", "关节球", "存储腔"),
    "OPK": ("主控腔", "菌丝节", "分化芽"),
}

# 分化规则：按"接了几个骨架 / 长了几根触肢"选择形态
MORPH_RULES = [
    ("clasper",   "抱握型", "接 ≥3 个骨架，分瓣包住邻居，用于把多个器官固定成一个整体"),
    ("bridge",    "桥接型", "接 2 个骨架，两端长出接口，身体沿桥轴拉长"),
    ("tentacle",  "触手型", "只接 1 个骨架但长了 ≥2 根触肢，身体伸出多条触须"),
    ("cap",       "端接型", "只接 1 个骨架，在一端长出接口与短触肢"),
    ("sensory",   "感知型", "不接骨架、长着触肢/端帽，专职感知与吸附"),
    ("basic",     "基础型", "孤立或只有单接口，保持紧凑的基础形态"),
]


def morph_of(n_nbrs, n_term, family):
    pre = FAMILY_PREFIX.get(family, ("器官", "器官", "器官"))
    if n_nbrs >= 3:
        key, name, desc = MORPH_RULES[0]
        return {"key": key, "name": pre[0] + "·抱握型", "desc": desc}
    if n_nbrs == 2:
        key, name, desc = MORPH_RULES[1]
        return {"key": key, "name": pre[1] + "·桥接型", "desc": desc}
    if n_nbrs == 1 and n_term >= 2:
        key, name, desc = MORPH_RULES[2]
        return {"key": key, "name": pre[2] + "·触手型", "desc": desc}
    if n_nbrs == 1:
        key, name, desc = MORPH_RULES[3]
        return {"key": key, "name": pre[0] + "·端接型", "desc": desc}
    if n_term >= 1:
        key, name, desc = MORPH_RULES[4]
        return {"key": key, "name": pre[2] + "·感知型", "desc": desc}
    key, name, desc = MORPH_RULES[5]
    return {"key": key, "name": pre[0] + "·基础型", "desc": desc}


# ---------------------------------------------------------------- 骨架器官
def skeleton_organs(mol):
    """每个骨架（三价连通体）→ 元素计数 / 能力 / 连接数 / 触肢数 / 分化形态。"""
    atoms = mol["atoms"]
    place = mol["place"]
    skel_of_atom = {}
    for sk in mol["skeletons"]:
        for a in sk["idx"]:
            skel_of_atom[a] = sk["sid"]
    # 骨架之间的桥
    nbrs = defaultdict(set)
    for br in mol["bridges"]:
        comps = br.get("comps") or []
        if len(comps) == 2:
            a, b = comps
            if a != b:
                nbrs[a].add(b)
                nbrs[b].add(a)
    # 端帽 / 支臂归属
    term = Counter()
    arm = Counter()
    for u in mol["decoration"].get("mono", []):
        for (i, j, m) in mol["edges"]:
            v = None
            if i == u:
                v = j
            elif j == u:
                v = i
            if v is not None and v in skel_of_atom:
                term[skel_of_atom[v]] += 1
                break
    for u in mol["decoration"].get("arms", []):
        for (i, j, m) in mol["edges"]:
            v = None
            if i == u:
                v = j
            elif j == u:
                v = i
            if v is not None and v in skel_of_atom:
                arm[skel_of_atom[v]] += 1
                break
    out = []
    for sk in mol["skeletons"]:
        cnt = Counter(atoms[a] for a in sk["idx"])
        ab = abilities_of(cnt)
        nn = len(nbrs.get(sk["sid"], ()))
        nt = term[sk["sid"]]
        mo = morph_of(nn, nt + arm[sk["sid"]], sk["family"])
        out.append({
            "sid": sk["sid"], "num": sk["num"], "formula": sk["formula"],
            "family": sk["family"], "family_zh": sk["family_zh"], "n": sk["n"],
            "counts": dict(cnt), "abilities": ab, "n_nbrs": nn,
            "n_terms": nt, "n_arms": arm[sk["sid"]], "morph": mo,
        })
    return out


# ---------------------------------------------------------------- 有机 / 无机
def _term_elements(mol, skel_of_atom):
    """端帽 / 支臂的原子上元素计数。"""
    out = Counter()
    for u in mol["decoration"].get("mono", []):
        out[mol["atoms"][u]] += 1
    for u in mol["decoration"].get("arms", []):
        out[mol["atoms"][u]] += 1
    return out


def _bridge_elements(mol):
    out = Counter()
    for br in mol["bridges"]:
        for a in br.get("idx", []):
            out[mol["atoms"][a]] += 1
    return out


def life_traits(mol, organs, counts):
    """生命度 = 结构上真正出现的生命向特征之和（不含"元素多所以分高"的通胀）。"""
    br_el = _bridge_elements(mol)
    te_el = _term_elements(mol, {a: sk["sid"] for sk in mol["skeletons"] for a in sk["idx"]})
    n_skel = len(mol["skeletons"])
    n_bridge = len(mol["bridges"])
    n_arm = len(mol["decoration"].get("arms", []))
    n_mono = len(mol["decoration"].get("mono", []))
    has_fusion = any(sk.get("n_fusion_bonds") for sk in mol["skeletons"])
    morphs = {o["morph"]["key"] for o in organs}

    flags = {}
    # 分化：多器官分工，或单器官出现多种分化接口
    if n_skel >= 2:
        flags["differentiate"] = 1.6 + 0.25 * min(3, len(morphs))
    elif len(morphs) >= 2:
        flags["differentiate"] = 0.8
    # 运动：有触须，或流桥成对出现（可推挤）
    if n_arm >= 1 or br_el.get("W", 0) >= 2:
        flags["move"] = 1.4 + (0.3 if n_arm >= 3 else 0)
    # 感知：电端帽/电桥（信号），或冰端帽成组（触觉）
    if te_el.get("L", 0) >= 1 or br_el.get("L", 0) >= 1:
        flags["sense"] = 1.0
    elif te_el.get("C", 0) >= 3:
        flags["sense"] = 0.6
    # 储能：势 P 成组
    if counts.get("P", 0) >= 4:
        flags["store"] = 0.9 + (0.3 if counts.get("P", 0) >= 8 else 0)
    # 抓取/吸附：冰端帽或气原子成组
    if te_el.get("C", 0) >= 2 or n_mono >= 3:
        flags["grasp"] = 0.9
    if counts.get("A", 0) >= 3 or te_el.get("A", 0) >= 2:
        flags["adsorb"] = 0.7
    # 自修复：秩 O 成组
    if counts.get("O", 0) >= 5:
        flags["heal"] = 0.9
    # 共生：融合，或多器官互连
    if has_fusion or (n_skel >= 3 and n_bridge >= 2):
        flags["symbiosis"] = 1.2
    # 泵送：流元素多且有桥形成回路
    if counts.get("W", 0) >= 3 and n_bridge >= 2:
        flags["pump"] = 0.8
    # 防御/切割：焰成组
    if counts.get("F", 0) >= 2:
        flags["defend"] = 0.6
    # 电能力（材料层也会给，但结构上要成组才算"器官"）
    if counts.get("L", 0) >= 1:
        flags["conduct"] = 0.4
    score = round(sum(flags.values()), 1)
    return score, flags


def classify_life(score):
    if score >= 8.0:
        return "life", "有机生命"
    if score >= 5.0:
        return "proto", "拟生命"
    if score >= 3.0:
        return "active", "活性无机物"
    return "inert", "无机晶体"


def molecule_traits(mol):
    counts = Counter(mol["atoms"])
    organs = skeleton_organs(mol)
    ab = abilities_of(counts)
    # 结构带来的能力（器官级）
    if len(mol["skeletons"]) >= 2:
        ab["differentiate"] = max(ab.get("differentiate", 0), 2)
        ab["support"] = max(ab.get("support", 0), 2)
    if mol["decoration"].get("arms"):
        ab["move"] = max(ab.get("move", 0), 2)
        ab["grasp"] = max(ab.get("grasp", 0), 1)
    if len(mol["bridges"]) >= 3:
        ab["flex"] = max(ab.get("flex", 0), 2)
        ab["signal"] = max(ab.get("signal", 0), 1)
    if any(sk.get("n_fusion_bonds") for sk in mol["skeletons"]):
        ab["regenerate"] = max(ab.get("regenerate", 0), 2)

    score, flags = life_traits(mol, organs, counts)
    klass, klass_zh = classify_life(score)
    state, state_why = physical_state(counts)
    soft, bondcnt = softness(mol)
    morphs = sorted({o["morph"]["key"] for o in organs})
    name = species_name(mol, organs, ab, klass, state, soft, counts, flags)
    return {
        "mid": mol["mid"], "formula": mol["formula"], "n_atoms": mol["n_atoms"],
        "counts": dict(counts), "abilities": ab, "organs": organs,
        "life_score": score, "life_flags": flags,
        "class": klass, "class_zh": klass_zh,
        "state": state, "state_why": state_why, "softness": soft, "bondcnt": bondcnt,
        "morphs": morphs, "name": name,
        "n_skel": len(mol["skeletons"]), "n_bridge": len(mol["bridges"]),
        "n_arm": len(mol["decoration"].get("arms", [])),
        "n_mono": len(mol["decoration"].get("mono", [])),
        "family_zh": mol.get("family_zh", ""),
    }


STATE_WORD = {"固态": "固", "液态": "流", "气态": "浮", "晶态": "晶"}
CLASS_WORD = {"life": "生体", "proto": "拟生", "active": "活体", "inert": "晶体"}
MORPH_SHAPE = {"clasper": "抱握簇", "bridge": "桥接体", "tentacle": "触手体",
               "cap": "端接体", "sensory": "感知芽", "basic": "基体"}
SHAPE_WORD = {"O": "晶柱", "P": "势球", "K": "多面体", "OP": "拱脊体",
              "OK": "盾甲体", "PK": "圆囊体", "OPK": "六面簇体"}
FLAG_WORD = {"differentiate": "分化", "move": "移动", "sense": "感知", "store": "储能",
             "grasp": "抓取", "adsorb": "吸附", "heal": "自修", "symbiosis": "共生",
             "pump": "泵送", "defend": "防御", "conduct": "导电"}


def species_name(mol, organs, ab, klass, state, soft, counts, flags):
    fam = mol["skeletons"][0]["family"] if mol["skeletons"] else "OPK"
    shape = SHAPE_WORD.get(fam, "多面体")
    if len(organs) >= 4:
        shape = "多器官" + shape
    top = sorted(flags.items(), key=lambda kv: -kv[1])[:3]
    feat = "·".join(FLAG_WORD.get(k, k) for k, v in top if v > 0)
    return "%s·%s %s·%s「%s」" % (state, soft, CLASS_WORD.get(klass, "体"), shape, feat)


# ---------------------------------------------------------------- 入口
def load_molecules(path=None):
    path = path or os.path.join(HERE, "t68_data.json")
    d = json.load(open(path, encoding="utf-8"))
    return d["molecules"]


def all_traits():
    out = []
    for m in load_molecules():
        out.append(molecule_traits(m))
    return out


if __name__ == "__main__":
    import sys
    ts = all_traits()
    ts.sort(key=lambda t: -t["life_score"])
    for t in ts:
        print("%-4s %-18s %-6s %-6s 生命分 %4.1f  %-6s  %-26s 形态 %s" % (
            t["mid"], t["formula"], t["state"], t["softness"], t["life_score"],
            t["class_zh"], t["name"], ",".join(t["morphs"])))
