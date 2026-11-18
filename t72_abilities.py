# -*- coding: utf-8 -*-
"""T72 能力总表（72 项，9 大类）+ 家族专属能力加成。

能力 = 材料层（元素亲和，权重 1~3）+ 器官层（家族加成 + 结构触发）。
目的：能力数目多、区分度高，能像现实里的有机物/无机物一样描述物质“会什么”。
"""

CATS = [
    ("struct", "结构", (74, 92, 118), "承力、成形、抗环境破坏"),
    ("motion", "运动", (196, 118, 44), "位移、关节、抓握、推进"),
    ("sense", "感知", (168, 72, 96), "光/热/震/化学/电/磁/压力/本体"),
    ("metab", "代谢", (46, 140, 130), "储能放能、催化、合成分解、循环"),
    ("inter", "交互", (140, 82, 160), "粘附融合、共生寄生、信号"),
    ("defend", "防御", (60, 100, 170), "耐热寒压辐射酸碱盐、绝缘导电"),
    ("env", "环境", (86, 140, 92), "浮力、隔热、发光、压电热电"),
    ("grow", "生长", (52, 132, 180), "分化再生、出芽分裂、结晶结壳"),
    ("info", "信息", (110, 100, 170), "脉冲、编码、记忆、群体协调"),
]
CAT_ZH = {k: zh for (k, zh, c, d) in CATS}
CAT_COL = {k: c for (k, zh, c, d) in CATS}

# (key, 中文名, 类别, 有机/无机, 元素亲和 {元素: 权重}, 说明)
ABILITY = [
    # 结构
    ("rigid", "刚性刚架", "struct", "inorg", {"X": 3, "K": 1}, "骨架抗弯、保持形状"),
    ("compress", "抗压", "struct", "inorg", {"X": 2, "K": 2}, "承受来向压缩"),
    ("tensile", "抗拉", "struct", "inorg", {"O": 2, "P": 2}, "沿轴向抗拉"),
    ("tough", "韧性", "struct", "inorg", {"P": 2, "W": 2}, "形变不裂"),
    ("porous", "多孔", "struct", "inorg", {"K": 2, "A": 2}, "有孔道，可过滤/容纳"),
    ("dense", "致密", "struct", "inorg", {"X": 3, "O": 1}, "无孔，防渗透"),
    ("laminate", "层状", "struct", "inorg", {"O": 2, "X": 2}, "分层叠片，抗裂扩展"),
    ("cleavage", "晶体解理", "struct", "inorg", {"O": 2, "K": 2}, "沿晶面整齐断裂并露出新面"),
    # 运动
    ("tentacle", "触手伸缩", "motion", "org", {"W": 2, "C": 2}, "伸/缩/卷的触须"),
    ("joint", "关节铰接", "motion", "org", {"W": 2, "K": 2}, "两段之间可转动"),
    ("crawl", "蠕动", "motion", "org", {"W": 3, "P": 1}, "分段收缩爬行"),
    ("glide", "滑行", "motion", "org", {"A": 2, "W": 1}, "低摩擦滑移"),
    ("jerk", "弹跳", "motion", "org", {"P": 3, "W": 1}, "蓄势释放弹开"),
    ("drift", "漂浮", "motion", "org", {"A": 3, "O": 1}, "气腔悬浮"),
    ("screw", "螺旋推进", "motion", "org", {"W": 2, "A": 2}, "螺旋形旋进"),
    ("grasp", "抓握", "motion", "org", {"C": 3, "X": 1}, "端部合拢夹住"),
    # 感知
    ("photo", "光感", "sense", "org", {"O": 2, "F": 2}, "感光/趋光"),
    ("thermo", "热感", "sense", "org", {"F": 2, "X": 2}, "感温"),
    ("vibro", "震感", "sense", "org", {"X": 2, "C": 2}, "感机械振动"),
    ("chemo", "化学感", "sense", "org", {"A": 2, "W": 2}, "感气味/浓度"),
    ("electro", "电场感", "sense", "org", {"L": 3}, "感电场变化"),
    ("magno", "磁感", "sense", "org", {"X": 2, "L": 2}, "感磁场"),
    ("presso", "压力感", "sense", "org", {"X": 2, "K": 2}, "感接触压力"),
    ("proprio", "本体感", "sense", "org", {"K": 2, "W": 2}, "知道自身各段位置"),
    # 代谢
    ("store", "储能", "metab", "org", {"P": 3, "O": 1}, "把能量存在势能里"),
    ("release", "放能", "metab", "org", {"F": 2, "P": 2}, "集中释放能量"),
    ("catalyze", "催化", "metab", "org", {"P": 3}, "加速邻体反应"),
    ("decompose", "分解", "metab", "org", {"W": 2, "F": 2}, "切断键、拆解物质"),
    ("synthesis", "合成", "metab", "org", {"O": 2, "P": 2}, "把碎片重新组装"),
    ("osmosis", "渗透调节", "metab", "org", {"A": 2, "W": 2}, "调水分/内压"),
    ("pump", "循环泵送", "metab", "org", {"W": 3}, "推动体液循环"),
    ("latt_swap", "晶格置换", "metab", "inorg", {"O": 2, "X": 2}, "晶格里换原子改性质"),
    # 交互
    ("adhere", "粘附", "inter", "org", {"C": 2, "K": 2}, "贴住别的表面"),
    ("fuse", "融合", "inter", "org", {"K": 3, "O": 1}, "与别的骨架焊成一个"),
    ("symbiosis", "共生", "inter", "org", {"K": 2, "A": 2}, "与邻体互相供养"),
    ("parasitism", "寄生", "inter", "org", {"W": 2, "C": 2}, "附着他体吸取"),
    ("predate", "捕食", "inter", "org", {"C": 2, "F": 2}, "抓取并分解猎物"),
    ("camo", "伪装", "inter", "org", {"A": 2, "O": 2}, "外观/表面性质拟态"),
    ("emit", "信号发射", "inter", "org", {"L": 3}, "发出电/化学信号"),
    ("receive", "信号接收", "inter", "org", {"L": 2, "A": 2}, "接收邻近信号"),
    # 防御
    ("heat", "耐热", "defend", "inorg", {"X": 2, "F": 2}, "高温下不软化"),
    ("cold", "耐寒", "defend", "inorg", {"C": 3}, "低温不脆裂"),
    ("press", "耐压", "defend", "inorg", {"X": 2, "K": 2}, "抗高压"),
    ("rad", "耐辐射", "defend", "inorg", {"X": 2, "L": 2}, "抗射线"),
    ("acid", "耐酸", "defend", "inorg", {"O": 2, "A": 2}, "抗腐蚀"),
    ("salt", "耐盐", "defend", "inorg", {"A": 2, "W": 2}, "抗渗透压"),
    ("insulate", "绝缘", "defend", "inorg", {"O": 2, "X": 2}, "阻断电流/热流"),
    ("conduct", "导电", "defend", "inorg", {"L": 3}, "传导电流"),
    # 环境
    ("buoy", "浮力", "env", "inorg", {"A": 3}, "气腔/低密度浮起"),
    ("insul_heat", "隔热", "env", "inorg", {"A": 2, "O": 2}, "阻热流"),
    ("glow", "发光", "env", "org", {"F": 3}, "自发光"),
    ("fluor", "荧光", "env", "org", {"F": 2, "L": 2}, "受激后发光"),
    ("piezo", "压电", "env", "inorg", {"X": 2, "L": 2}, "受压产生电"),
    ("thermoe", "热电", "env", "inorg", {"X": 2, "L": 1, "A": 1}, "温差生电"),
    ("magnetize", "磁化", "env", "inorg", {"X": 2, "L": 2}, "带磁性/被磁吸"),
    ("volatile", "挥发", "env", "inorg", {"A": 3, "F": 1}, "向空气散出物质"),
    # 生长
    ("differentiate", "分化", "grow", "org", {"K": 3, "P": 1}, "长出不同形态的器官"),
    ("regenerate", "再生", "grow", "org", {"K": 3, "O": 1}, "断口重新长出"),
    ("bud", "出芽", "grow", "org", {"K": 2, "P": 2}, "侧面长出芽体"),
    ("divide", "分裂", "grow", "org", {"K": 3, "W": 1}, "一分为二"),
    ("encrust", "结壳", "grow", "inorg", {"X": 2, "A": 2}, "表面沉积硬壳"),
    ("crystallize", "结晶", "grow", "inorg", {"O": 2, "X": 2}, "长出规则晶体"),
    ("metamorph", "变态", "grow", "org", {"K": 2, "P": 2}, "整体形态重构"),
    ("self_heal", "自修复", "grow", "org", {"O": 3, "K": 1}, "损伤处自动补回"),
    # 信息
    ("pulse", "脉冲传导", "info", "org", {"L": 3}, "沿身体传电脉冲"),
    ("encode", "信号编码", "info", "org", {"L": 2, "K": 2}, "编码不同信号"),
    ("memory", "状态记忆", "info", "org", {"L": 2, "O": 2}, "保留受刺激的状态"),
    ("swarm", "群体协调", "info", "org", {"L": 2, "A": 2}, "与同类同步行动"),
    ("photo_taxis", "趋光", "info", "org", {"O": 2, "F": 2}, "朝光移动"),
    ("chemo_taxis", "趋化", "info", "org", {"A": 2, "W": 2}, "沿浓度梯度移动"),
    ("thermo_taxis", "趋温", "info", "org", {"F": 2, "X": 1}, "朝适温区移动"),
    ("electrochromic", "电致变色", "info", "inorg", {"L": 2, "O": 2}, "加电改变颜色"),
]

ABIL = {k: {"zh": zh, "cat": cat, "kind": kind, "elems": el, "desc": desc}
        for (k, zh, cat, kind, el, desc) in ABILITY}

# 家族专属加成：让同类骨架的能力谱显著不同
FAMILY_BONUS = {
    "O": {"tensile": 2, "laminate": 3, "synthesis": 1, "crystallize": 2, "self_heal": 2,
          "cleavage": 1, "photo": 1},
    "P": {"store": 3, "jerk": 2, "tough": 1, "catalyze": 2, "pump": 1,
          "osmosis": 1, "bud": 1},
    "K": {"differentiate": 3, "regenerate": 3, "divide": 2, "metamorph": 2, "fuse": 2,
          "adhere": 1, "encode": 1, "memory": 1},
    "OP": {"tensile": 2, "store": 1, "pump": 3, "photo": 1, "crystallize": 1, "synthesis": 2,
           "drift": 1, "thermo_taxis": 1},
    "OK": {"rigid": 1, "compress": 3, "cleavage": 2, "encrust": 2, "camo": 1, "acid": 2,
           "memory": 1, "presso": 1},
    "PK": {"tough": 2, "joint": 3, "store": 2, "osmosis": 2, "crawl": 1,
           "thermoe": 1, "fluor": 1, "buoy": 1},
    "OPK": {"differentiate": 3, "encode": 2, "symbiosis": 2, "pump": 1, "emit": 1,
            "receive": 1, "swarm": 1, "memory": 1},
}

CAT_ORDER = [k for (k, zh, c, d) in CATS]


SIGNATURE = {"O": ("laminate", "crystallize"), "P": ("store", "jerk"), "K": ("differentiate", "regenerate"),
             "OP": ("pump", "tensile"), "OK": ("compress", "cleavage"), "PK": ("joint", "tough"),
             "OPK": ("differentiate", "encode")}


def levels(counts, bonus=None):
    """元素计数 → 能力等级（1~3）：按元素占比算强度（区分度高），家族签名再加强。"""
    out = {}
    bonus = dict(bonus or {})
    tot = float(sum(counts.values())) or 1.0
    for key, info in ABIL.items():
        s = 0.0
        for el, w in info["elems"].items():
            c = counts.get(el, 0)
            if c:
                s += w * (c / tot) * 2.0
        s += bonus.get(key, 0)
        if s >= 2.4:
            out[key] = 3
        elif s >= 1.2:
            out[key] = 2
        elif s >= 0.5:
            out[key] = 1
    return out


def family_of_block(atoms):
    ks = [a for a in atoms if a in ("O", "P", "K")]
    s = set(ks)
    if len(s) >= 3:
        return "OPK"
    if s == {"O", "P"}:
        return "OP"
    if s == {"O", "K"}:
        return "OK"
    if s == {"P", "K"}:
        return "PK"
    if s == {"O"}:
        return "O"
    if s == {"P"}:
        return "P"
    if s == {"K"}:
        return "K"
    return "OPK"


def block_ability(counts):
    fam = family_of_block([e for e, c in counts.items() for _ in range(c)])
    ab = levels(counts, FAMILY_BONUS.get(fam, {}))
    return fam, ab
