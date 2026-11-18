"""T77 涌现机制：分子 → 组装体 → 器官 → 生命（可运行原型）。

本模块按 ``intake/emergence_spec.md`` 实现四层涌现管线，纯标准库、无 numpy：

* **L1 分子**：从目录记录实例化分子，提取界面位点（cap/hull/bridge），
  位点强度 σ 来自 ``ability.scores`` 的九项次级能力值（tier → 0.35/0.70/1.00）。
* **L2 组装体**：世界为 L×L 六边形环面，分子是"骨架块骨牌"；相邻分子对按
  ``w = κ0·σ_i·σ_j·M_eff·K·Φ·Ψ`` 计算界面能，用 ``p_on/p_off`` 做可逆结合，
  再按"连通 + 总界面能 + 内聚度 + 寿命"四条判据登记组装体，并按六类形态分类。
* **L3 器官**：器官是组装体内的功能子图，由**通量阈值**识别（九种原型），
  不做配方查表；模块度 Q 与持续时长 τ_org 共同决定是否登记。
* **L4 生命**：``life_report()`` 纯读取观测窗口事件，输出 B/M/R/I/H(+A) 判据向量，
  四档分类只由布尔判据向量 + 回路闭合 + 可育子代决定。

公理 A0（无生命标志）：本模块任何代码路径都不写 ``alive`` / ``is_life`` 之类状态；
``life_report`` 只读 ``ObsBuffer`` 与器官/系统的只读快照。删除 ``life_report_all``
后世界演化逐位不变（tests/test_emergence.py 校验）。

与规范的已知简化（均在 docstring / 注释中标注，不改语义）：
- 位点几何做了**骨牌压缩**：每个骨架块占 1 格，位点取其所属骨架块的格子；
  接触判定用骨牌边/顶点相邻代替逐原子距离（§4.1 允许的块级近似）。
- 每对分子最多保留 **1 条界面键**（位点仍满足"每位点至多 1 键"），
  这是性能取舍；键能 w 按最优位点对计算。
- 信号用"跳数衰减的脉冲"近似 §5.1 的脉冲对象；信息量用事件比近似经验互信息。
- 器官通量用本文件记录的事件计数器（ObsBuffer）近似 §5.1 定义，
  其中部分通量（运输/催化）缺少可靠的局域观测量，用吸附/切割事件代理。
- 复制只做"单代"：复制器官活跃时按模板复制一个子分子（元素替换突变 μ），
  子代可育性在窗口末检查其是否进入 ≥2 器官的组装体。

CLI::

    python -m alchemy.emergence --sample 6000 --steps 1200 --seed 20261119 --out out.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field as dc_field
from pathlib import Path

from . import ability as AB
from . import attrs as ATTR
from . import ops as OPS
from .core import elements as ELEM
from .core.catalog import get_catalog

__all__ = [
    # 参数与矩阵
    "DEFAULT_PARAMS", "default_params", "load_params", "build_matrices", "render_matrix",
    # 数据结构
    "ElemSite", "MoleculeInst", "InterfaceBond", "Assemblage", "Organ",
    "OrganSystem", "LifeReport", "Env", "ObsBuffer", "World",
    # L1
    "extract_sites", "make_molecule",
    # L2
    "interface_energy", "candidate_sites", "p_on", "p_off", "rebuild_assemblies",
    "classify_shape", "neighbor_pairs",
    # L3
    "organ_flux", "classify_organs", "update_systems",
    # L4
    "life_report", "life_report_all", "tier_from_criteria",
    # 动力学 / 实验
    "init_world", "step_world", "run_world", "sample_records",
    "run_experiment", "project_blocks", "legacy_life_score", "main",
]

# ---------------------------------------------------------------------------
# 常量与参数
# ---------------------------------------------------------------------------

TWO_PI = 2.0 * math.pi

#: 九项次级能力的固定顺序（与 ops.py 一致）
OP_ORDER: tuple[str, ...] = tuple(OPS.OP_KEYS)
_OP_INDEX = {k: i for i, k in enumerate(OP_ORDER)}
_OP_OF_ELEMENT = dict(OPS.OP_OF_ELEMENT)
_ELEMENT_OF_OP = dict(OPS.OP_ELEMENT)
#: 元素 → ability.scores 的三轴键（poly/scatter/move）
_ELEM_AXIS = {"O": "poly", "X": "poly", "C": "poly",
              "K": "scatter", "A": "scatter", "F": "scatter",
              "P": "move", "W": "move", "L": "move"}

#: 能力档位 → 位点强度系数（§3.3）
TIER_SCORE = {"低": 0.35, "中": 0.70, "高": 1.00}
#: 位点类型 → 暴露系数（§3.2）
EXPOSURE = {"cap": 1.00, "hull": 0.55, "bridge": 0.70}

#: 键型兼容核 K（§3.5）
BOND_K = {
    "S": {"S": 1.00, "C": 0.85, "L": 0.55},
    "C": {"S": 0.85, "C": 0.75, "L": 0.60},
    "L": {"S": 0.55, "C": 0.60, "L": 0.45},
}

#: 位点几何相互作用的 Ψ（§3.6）
PSI = {
    ("hull", "hull"): 1.00,
    ("cap", "cap"): 1.00,
    ("cap", "hull"): 0.90,
    ("hull", "cap"): 0.90,
    ("bridge", "bridge"): 0.80,
    ("bridge", "cap"): 0.80,
    ("cap", "bridge"): 0.80,
    ("bridge", "hull"): 0.80,
    ("hull", "bridge"): 0.80,
}

#: M_dir 的"谁作用于谁"先验（§3.4；在 M 上叠加，允许为负）
M_DIR_PRIOR = {
    ("clv", "sup"): 0.15, ("clv", "rig"): 0.15,
    ("sup", "clv"): -0.10, ("rig", "clv"): -0.10,
    ("sup", "ads"): 0.12, ("ads", "sup"): 0.02,
    ("sto", "mov"): 0.15, ("mov", "sto"): 0.02,
    ("sig", "dif"): 0.10, ("dif", "sig"): 0.02,
    ("sig", "sto"): 0.08, ("sto", "sig"): 0.02,
    ("ads", "clv"): 0.08, ("clv", "ads"): 0.04,
}

#: 九类器官原型：kind → (中文名, 必需能力, 阈值 θ, 是否需保真度)
ORGAN_PROTOTYPES = {
    "sup": ("支撑器官", ("sup", "rig"), 0.30, False),
    "bnd": ("边界器官", ("adh", "ads"), 0.45, False),
    "nrg": ("能量器官", ("sto", "mov"), 0.35, False),
    "trn": ("运输器官", ("mov", "sto"), 0.30, False),
    "sen": ("传感器官", ("sig", "ads"), 0.25, False),
    "int": ("信息器官", ("sig", "dif"), 0.35, False),
    "def": ("防御器官", ("clv", "rig"), 0.30, False),
    "cat": ("催化器官", ("ads", "clv"), 0.25, False),
    "rep": ("复制器官", ("dif", "sup", "adh"), 0.25, True),
}

ORGAN_NAMES = {k: v[0] for k, v in ORGAN_PROTOTYPES.items()}

SHAPE_NAMES = ("壳", "骨架网络", "膜", "链", "簇", "团")

#: 默认参数（§7.4 + §5.2）。JSON 参数文件只覆盖同名字段。
DEFAULT_PARAMS: dict = {
    # 规模
    "N": 6000, "L": 160, "steps": 1200, "T_obs": 600, "t_warm": 300,
    # 界面能
    "kappa0": 2.5, "M_MIN": 0.25, "W_MIN": 0.15, "E_min": 2.5, "c_min": 0.50,
    "tau_min": 30, "w_ref": 0.8,
    # 动力学
    "k_on0": 0.05, "k_off0": 0.05, "beta": 1.8, "W0": 0.30, "lam_s": 1.0,
    "delta_t": 1,
    # 物性核
    "sigma_s": 8.0, "sigma_T": 6.0, "lam_d": 0.5, "rho_max": 40.0,
    # 环境
    "D_E": 0.15, "eta": 0.8, "d0": 0.01, "e_rep": 1.0, "mu": 0.02,
    "p_move": 0.6, "beta_m": 1.0, "field_every": 5, "rupture_p": 0.05,
    # 器官
    "Q_min": 0.60, "tau_org": 60, "tau_asm": 10, "tau_sys": 50,
    "theta_keep_ratio": 0.8, "min_organ_mols": 2,
    # 适应
    "s0": 0.10, "s_T": 0.02,
    # 能量（§7.1 S3：成键耗 1、断键释 0.8；S1 的局域能量输入 I_E=ρ_E·η 由
    # i_e_scale 标定——ρ_E 场在本原型中近似均匀为 1，故用 0.3 使其刚好抵消成键耗散）
    "energy_init": 2.0, "bond_cost": 1.0, "bond_release": 0.8, "bond_damp": 1.0,
    "move_cost": 0.02, "charge_rate": 0.05, "i_e_scale": 0.3,
    # 位点
    "max_sites": 12, "affinity": 1.0,
    # 标定（task-10 的 `calibration` 段可覆盖；默认值与 task-8 行为一致）
    # contacts_per_pair：同一分子对在未用位点上的界面接触上限（1 = 每对一条键）
    "contacts_per_pair": 1,
    # 每分子接触上限 = min(n_sites, contact_base + natoms // contact_div)
    "contact_base": 3, "contact_div": 8,
    # 器官：θ 的整体缩放（<1 更易形成）、每个分子最多登记器官数
    "theta_scale": 1.0, "max_organs_per_mol": 2,
    # M 判据的维持消耗率（每分子每 tick 的 E_maint；用于把 harvest−dissip 归一化）
    "maint_rate": 0.4,
}

#: 参数的 "JSON 化" 边界：矩阵不写进 JSON（由 LINKAGE 派生）
_PARAM_JSON_KEYS = tuple(DEFAULT_PARAMS.keys())


def default_params(**overrides) -> dict:
    """返回完整参数 dict（含派生矩阵）；overrides 覆盖默认值。"""
    P = dict(DEFAULT_PARAMS)
    P.update(overrides)
    P["affinity"] = dict(P.get("affinity") or {}) if isinstance(P.get("affinity"), dict) else {}
    P.setdefault("theta", {k: v[2] for k, v in ORGAN_PROTOTYPES.items()})
    P["K"] = BOND_K
    P["psi"] = PSI
    return P


def load_params(path: str | os.PathLike | None = None) -> dict:
    """加载 ``alchemy/data/emergence_params.json``（可被 path 覆盖）并派生矩阵。

    JSON 支持两种写法：

    * 顶层直接放参数键（task-8 的写法，作为默认配置）；
    * ``"calibration": {...}``——参数标定段，覆盖顶层同名键（task-10）。
      只接受 ``DEFAULT_PARAMS`` 里的标量键以及 ``theta``（九类器官阈值），
      矩阵一律由 ``ops.LINKAGE`` 派生，不写进 JSON。
    """
    if path is None:
        path = Path(__file__).resolve().parent / "data" / "emergence_params.json"
    raw = {}
    if path and Path(path).is_file():
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    overrides = {k: v for k, v in raw.items() if k in _PARAM_JSON_KEYS}
    cal = raw.get("calibration") or {}
    if not isinstance(cal, dict):
        raise ValueError("`calibration` 必须是 JSON 对象")
    overrides.update({k: v for k, v in cal.items() if k in _PARAM_JSON_KEYS})
    P = default_params(**overrides)
    if "theta" in raw:
        P["theta"].update(raw["theta"])
    if isinstance(cal.get("theta"), dict):
        P["theta"].update(cal["theta"])
    P["M"], P["M_eff"], P["M_dir"] = build_matrices()
    return P


def build_matrices() -> tuple[list, list, list]:
    """由 ``ops.LINKAGE`` 派生 9×9 联动矩阵（task-8 指定公式）。

    映射 ``Λ → M``（保留 spec 的负值排斥语义，因为 ability_spec 的 Λ 全为 0.2~1.5）：

    * ``Λ ≥ 0.9``  → ``M = Λ``（强协同，最高 1.5）
    * ``0.6 ≤ Λ < 0.9`` → ``M = Λ - 0.35``（弱协同，0.25~0.55）
    * ``Λ < 0.6`` → ``M = 1.2·Λ - 0.72``（Λ=0.6 → 0，Λ=0.5 → -0.12，Λ=0.2 → -0.48，
      产生负值以驱动排斥项，防止"万物互粘"）
    * 对角 = 1.0（同类能力自聚：粘-粘、支-支、信-信…）
    * ``M_eff = (M + Mᵀ)/2``（L2 用，规范要求 M 对称；这里同时保证显式对称化）
    * ``M_dir = M + A``（L3 用，A 是"谁作用于谁"的先验，见 ``M_DIR_PRIOR``）
    """
    n = len(OP_ORDER)
    M = [[0.0] * n for _ in range(n)]
    for i in range(n):
        M[i][i] = 1.0
    for (ka, kb), (coef, _typ, _why) in OPS.LINKAGE.items():
        i, j = _OP_INDEX[ka], _OP_INDEX[kb]
        if coef >= 0.9:
            v = coef
        elif coef >= 0.6:
            v = coef - 0.35
        else:
            v = 1.2 * coef - 0.72
        v = max(-1.0, min(1.0, v))
        M[i][j] = M[j][i] = v
    M_eff = [[(M[i][j] + M[j][i]) / 2.0 for j in range(n)] for i in range(n)]
    A = [[0.0] * n for _ in range(n)]
    for (ka, kb), v in M_DIR_PRIOR.items():
        A[_OP_INDEX[ka]][_OP_INDEX[kb]] = v
    M_dir = [[max(-1.0, min(1.0, M[i][j] + A[i][j])) for j in range(n)] for i in range(n)]
    return M, M_eff, M_dir


def render_matrix(mat: list, labels: tuple = OP_ORDER) -> str:
    """把 9×9 矩阵渲染成可读文本（调试/报告用）。"""
    head = "      " + " ".join(f"{lbl:>5}" for lbl in labels)
    lines = [head]
    for i, lbl in enumerate(labels):
        lines.append(f"{lbl:>5} " + " ".join(f"{mat[i][j]:>5.2f}" for j in range(len(labels))))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 数据结构（§10.1）
# ---------------------------------------------------------------------------


@dataclass
class ElemSite:
    element: str
    ability: str
    sigma: float
    bond_type: str
    cell: tuple
    kind: str


@dataclass
class MoleculeInst:
    uid: int
    formula: str
    atoms: list
    edges: list
    cells: list
    sites: list
    profile: dict
    attrs: dict
    units: list
    pos: tuple = (0, 0)
    rot: int = 0
    energy: float = 2.0
    age: int = 0
    elem_vec: list = dc_field(default_factory=list)
    rec: dict = dc_field(default_factory=dict)  # 目录记录（复制模板用，只读）
    ops: dict = dc_field(default_factory=dict)  # ops 九项能力值（只读，L3 用）
    max_contacts: int = 3
    parent: int = -1


@dataclass
class InterfaceBond:
    a: int
    b: int
    site_a: int
    site_b: int
    w: float
    pair: tuple
    born: int
    loop: float = 0.0
    #: 该界面上的多个位点接触：[(sa, sb, w_contact), ...]。``w`` 为它们的和。
    #: 规范允许同一对分子在未用位点上形成多条界面键；本实现在一个无向对上
    #: 聚合成一条 ``InterfaceBond``（site_a/site_b 记最强接触），以控制计算量。
    contacts: list = dc_field(default_factory=list)


@dataclass
class Assemblage:
    aid: int
    mols: list
    bonds: list
    shape: str = "团"
    E: float = 0.0
    cohesion: float = 0.0
    born: int = 0
    organ_ids: list = dc_field(default_factory=list)
    dmg: int = 0
    rep: int = 0
    cells: list = dc_field(default_factory=list)


@dataclass
class Organ:
    oid: int
    aid: int
    kind: str
    mols: list
    bond_ids: list
    F: dict = dc_field(default_factory=dict)
    Q: float = 0.0
    born: int = 0
    active: bool = True
    degraded: int = 0
    sustained: int = 0


@dataclass
class OrganSystem:
    sid: int
    organs: list
    coupling: dict = dc_field(default_factory=dict)
    cycle_rank: int = 0
    tier: str = ""


@dataclass
class LifeReport:
    sid: int
    tier: str
    criteria: dict
    values: dict
    window: tuple


@dataclass
class Env:
    L: int
    rho_E: list
    temp: list
    shear: float = 0.2
    t: int = 0

    def rho_at(self, cell) -> float:
        return self.rho_E[cell[0] % self.L][cell[1] % self.L]

    def temp_at(self, cell) -> float:
        return self.temp[cell[0] % self.L][cell[1] % self.L]

    def diffuse(self, D_E: float) -> None:
        """六边形 5 点差分一拍的恒素扩散（半隐式、环面）。"""
        L = self.L
        src = self.rho_E
        dst = [[0.0] * L for _ in range(L)]
        for q in range(L):
            col = src[q]
            qm, qp = (q - 1) % L, (q + 1) % L
            for r in range(L):
                rm, rp = (r - 1) % L, (r + 1) % L
                nb = (src[qm][r] + src[qp][r] + src[q][rm] + src[q][rp]
                      + src[qm][rp] + src[qp][rm]) / 6.0
                v = col[r] + D_E * (nb - col[r])
                dst[q][r] = 0.0 if v < 0.0 else v
        self.rho_E = dst


@dataclass
class ObsBuffer:
    """观测窗口环形缓冲。**只写观测量，绝不写生命状态**（A0）。"""

    maxlen: int = 60
    samples: deque = dc_field(default_factory=lambda: deque(maxlen=60))
    counters: dict = dc_field(default_factory=lambda: defaultdict(float))
    asm_counters: dict = dc_field(default_factory=lambda: defaultdict(lambda: defaultdict(float)))
    # 分子级事件计数：组装体 id 会随并查集重排，故通量按分子归属再聚合（避免计数错位）
    mol_counters: dict = dc_field(default_factory=lambda: defaultdict(lambda: defaultdict(float)))
    asm_samples: dict = dc_field(default_factory=lambda: defaultdict(lambda: deque(maxlen=60)))
    global_hist: dict = dc_field(default_factory=lambda: defaultdict(list))
    t0: int = 0

    def bump(self, key: str, value: float = 1.0, aid: int | None = None) -> None:
        self.counters[key] += value
        if aid is not None:
            self.asm_counters[aid][key] += value

    def bump_mol(self, uid: int, key: str, value: float = 1.0) -> None:
        """按分子累加事件；器官/系统通量在聚合时对该器官的分子求和。"""
        self.counters[key] += value
        self.mol_counters[uid][key] += value

    def record_sample(self, aid: int, sample: dict) -> None:
        buf = self.asm_samples.get(aid)
        if buf is None or buf.maxlen != self.maxlen:
            buf = deque(buf or (), maxlen=self.maxlen)
            self.asm_samples[aid] = buf
        buf.append(sample)

    def window(self, aid: int | None = None, n: int | None = None) -> dict:
        """聚合最近 n 个采样的统计（纯读取）。"""
        out: dict = {}
        if aid is None:
            bufs = list(self.asm_samples.values())
        else:
            bufs = [self.asm_samples.get(aid, deque())]
        pts = []
        for buf in bufs:
            pts.extend(list(buf)[-(n or self.maxlen):])
        if not pts:
            return out
        keys = set()
        for p in pts:
            keys |= set(p.keys())
        for k in keys:
            # 采样里可能混有分类标签（如 shape 字符串），这里只聚合数值键。
            vals = [p.get(k) for p in pts]
            vals = [v for v in vals if isinstance(v, (int, float))]
            if not vals:
                continue
            out[k] = sum(vals) / len(vals)
            out[k + "_last"] = vals[-1]
            out[k + "_first"] = vals[0]
        return out


@dataclass
class World:
    t: int
    env: Env
    molecules: dict
    bonds: dict
    assemblies: dict
    organs: dict
    systems: dict
    pool: list
    rng: random.Random
    params: dict
    obs: ObsBuffer
    occupancy: dict = dc_field(default_factory=dict)
    site_use: dict = dc_field(default_factory=dict)
    next_uid: int = 0
    next_aid: int = 0
    next_oid: int = 0
    next_sid: int = 0
    stats: dict = dc_field(default_factory=dict)
    perturb: dict = dc_field(default_factory=dict)


# ---------------------------------------------------------------------------
# 小工具：六边形几何
# ---------------------------------------------------------------------------

_HEX_EDGE = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
#: 边相邻（<1,0> 类）+ 顶点相邻（<1,1> 类），共 12 个
_NEIGH12 = _HEX_EDGE + ((1, 1), (1, -2), (-1, 2), (-2, 1), (-1, -1), (2, -1))


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _rot(cell, rot):
    """六边形轴向坐标 60° 旋转（rot 次）。"""
    q, r = cell
    for _ in range(rot % 6):
        q, r = -r, q + r
    return (q, r)


def _hex_dist(a, b) -> int:
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def _cells_touch(ca, cb, L: int) -> bool:
    """两分子的骨牌格是否接触（边相邻或顶点相邻），对环面做 wrap。

    注意不能用 ``_hex_dist`` 直接比较世界格坐标：位于环面接缝两侧的两个格
    在坐标上相差 L-1，但实际相邻。这是 §4.1 接触判定的正确实现。
    """
    sb = set(cb)
    for c in ca:
        for off in _NEIGH12:
            if _wrap(_add(c, off), L) in sb:
                return True
    return False


def _unwrap_cells(cells, L: int) -> list:
    """把环面格集合展开到以首格为原点的连续坐标系（用于形态几何）。"""
    if not cells:
        return []
    q0, r0 = cells[0]
    out = []
    for q, r in cells:
        dq = ((q - q0 + L // 2) % L) - L // 2
        dr = ((r - r0 + L // 2) % L) - L // 2
        out.append((q0 + dq, r0 + dr))
    return out


def _wrap(cell, L):
    return (cell[0] % L, cell[1] % L)


def _convex_hull(points):
    """轴向坐标的凸包（轴向坐标是笛卡尔坐标的线性变换，凸包保持）。"""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _mode_bond_type(adj_row) -> str:
    if not adj_row:
        return "C"
    cnt = {"S": 0, "C": 0, "L": 0}
    for _j, bt in adj_row:
        cnt[bt] = cnt.get(bt, 0) + 1
    best = max(cnt.values())
    for k in ("S", "C", "L"):
        if cnt[k] == best and best:
            return k
    return "C"


def _sub_threshold(element: str):
    """取 ability.SUB_ABILITIES 中该元素的 (t1, t2) 阈值。"""
    for _cat, _label, subs in AB.SUB_ABILITIES:
        for elem, _name, th in subs:
            if elem == element:
                return th
    return (1.0, 2.0)


def _element_ability(element: str) -> str:
    return _OP_OF_ELEMENT.get(element, "sup")


def _cosine(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# ---------------------------------------------------------------------------
# L1：分子实例化与位点
# ---------------------------------------------------------------------------


def _structure(rec):
    """返回 (n, atoms, adj, pos, is_tri, is_div, tri_comp, div_comp, role, welded,
    cluster_touch, cluster_in_edges, hull_set, bridge_set)。

    结构口径与 ``ops.py`` 一致：骨架 = 三价连通块；二价角色按 DIV-only 簇判定。
    """
    atoms = list(rec.get("atoms") or [])
    edges = list(rec.get("edges") or [])
    place = rec.get("place") or {}
    n = len(atoms)
    pos = {int(k): (int(v[0]), int(v[1])) for k, v in place.items()}
    adj = [[] for _ in range(n)]
    for e in edges:
        i, j = int(e[0]), int(e[1])
        mult = e[2] if len(e) > 2 else 1
        if i >= n or j >= n:
            continue
        delta = (pos[j][0] - pos[i][0], pos[j][1] - pos[i][1])
        bt = ELEM.classify_offset(delta) or "C"
        adj[i].append((j, bt))
        adj[j].append((i, bt))
    is_tri = [atoms[i] in ELEM.TRI for i in range(n)]
    is_div = [atoms[i] in ELEM.DIV for i in range(n)]

    tri_comp = [-1] * n
    nc = 0
    for s in range(n):
        if not is_tri[s] or tri_comp[s] != -1:
            continue
        tri_comp[s] = nc
        stack = [s]
        while stack:
            u = stack.pop()
            for v, _bt in adj[u]:
                if is_tri[v] and tri_comp[v] == -1:
                    tri_comp[v] = nc
                    stack.append(v)
        nc += 1

    div_comp = [-1] * n
    role = ["free"] * n
    welded = [False] * n
    cluster_touch: list[set] = []
    cluster_in_edges: list[int] = []
    cluster_welded: list[bool] = []
    cid = 0
    for s in range(n):
        if not is_div[s] or div_comp[s] != -1:
            continue
        div_comp[s] = cid
        stack = [s]
        touch, in_edges, welded_c = set(), 0, False
        while stack:
            u = stack.pop()
            for v, bt in adj[u]:
                if is_tri[v]:
                    touch.add(tri_comp[v])
                    in_edges += 1
                    welded_c = welded_c or bt == "S"
                elif is_div[v] and div_comp[v] == -1:
                    div_comp[v] = cid
                    stack.append(v)
        cluster_touch.append(touch)
        cluster_in_edges.append(in_edges)
        cluster_welded.append(welded_c)
        cid += 1
    for i in range(n):
        if not is_div[i]:
            continue
        c = div_comp[i]
        k = len(cluster_touch[c])
        if k >= 2:
            role[i] = "bridge"
        elif k == 1 and cluster_in_edges[c] >= 2:
            role[i] = "intra"
        elif k == 1:
            role[i] = "arm"
        welded[i] = cluster_welded[c]

    hull_set = set(_convex_hull([pos[i] for i in range(n)]))
    bridge_set = set()
    try:
        for unit in ATTR.skeleton_units(atoms, edges):
            bridge_set |= {int(x) for x in unit.get("bridge_members") or []}
    except Exception:
        pass
    bridge_set |= {i for i in range(n) if role[i] == "bridge"}
    return (n, atoms, adj, pos, is_tri, is_div, tri_comp, div_comp, role,
            welded, cluster_touch, cluster_in_edges, hull_set, bridge_set)


def extract_sites(rec: dict, params: dict) -> list[ElemSite]:
    """§3.2 位点提取：cap（度 1）、hull（凸包骨架面）、bridge（桥端）。

    σ = tier_score[tier]·exposure[kind]·affinity[element]，tier 由该元素的
    能力值套 ``ability.SUB_ABILITIES`` 阈值（0 归低）。每分子最多 12 个位点。
    """
    if not rec or not rec.get("atoms") or not rec.get("place"):
        return []
    try:
        (n, atoms, adj, pos, _is_tri, _is_div, _tri_comp, _div_comp, role,
         _welded, _ct, _cie, hull_set, bridge_set) = _structure(rec)
    except Exception:
        return []
    if n == 0:
        return []
    formula = rec.get("formula")
    if not formula:
        formula = ELEM.formula_of(atoms)
    try:
        sc = AB.scores(formula)
        axes = sc.get("axes", {})
    except Exception:
        axes = {}
    elem_ability = {}
    elem_tier = {}
    # ability.scores 的三轴键是 poly/scatter/move；元素→轴 映射固定（9 元素 3 组）
    for e in set(atoms):
        axis_key = _ELEM_AXIS.get(e)
        try:
            val = float(axes.get(axis_key, {}).get("by_element", {}).get(e, 0.0))
        except Exception:
            val = 0.0
        elem_ability[e] = _element_ability(e)
        elem_tier[e] = AB.sub_tier(val, _sub_threshold(e))
    affinity = params.get("affinity") or {}
    max_sites = int(params.get("max_sites", 12))
    sites: list[ElemSite] = []
    for i in range(n):
        deg = len(adj[i])
        candidates = []
        if deg == 1:
            candidates.append(("cap", EXPOSURE["cap"]))
        if i in hull_set:
            if atoms[i] in ELEM.TRI or any(atoms[j] in ELEM.TRI for j, _ in adj[i]):
                candidates.append(("hull", EXPOSURE["hull"]))
            if atoms[i] in ELEM.DIV and (i in bridge_set or role[i] == "bridge"):
                candidates.append(("bridge", EXPOSURE["bridge"]))
        for kind, exposure in candidates:
            aff = float(affinity.get(atoms[i], 1.0) if isinstance(affinity, dict) else 1.0)
            sigma = TIER_SCORE.get(elem_tier[atoms[i]], 0.35) * exposure * aff
            bt = _mode_bond_type(adj[i])
            sites.append(ElemSite(atoms[i], elem_ability[atoms[i]], round(sigma, 6),
                                  bt, pos[i], kind))
    sites.sort(key=lambda s: (EXPOSURE.get(s.kind, 0.5) * s.sigma), reverse=True)
    return sites[:max_sites]


def _local_cells(units) -> list:
    """骨牌局部格（未旋转）：每个骨架块取质心格，无骨架块取 (0,0)。"""
    local = []
    if units:
        for u in units:
            c = u.get("cell")
            if c is not None:
                local.append((int(c[0]), int(c[1])))
    if not local:
        local = [(0, 0)]
    # 去重，保持顺序
    seen = set()
    out = []
    for c in local:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _footprint_cells(units, pos, rot) -> list:
    """分子骨牌的世界格集合：每个骨架块 1 格（凸包压缩），无骨架块取质心 1 格。"""
    local = _local_cells(units)
    out = []
    for c in local:
        wc = _wrap(_add(_rot(c, rot), pos), (1 << 30))  # 仅做平移/旋转，调用方再 wrap
        if wc not in out:
            out.append(wc)
    return out


def make_molecule(rec: dict, uid: int, params: dict, parent: int = -1) -> MoleculeInst:
    """§3.1 分子实例化（位点/能力/物性/摆放/骨牌）。"""
    atoms = list(rec.get("atoms") or [])
    edges = list(rec.get("edges") or [])
    formula = rec.get("formula") or ELEM.formula_of(atoms)
    try:
        sattrs = ATTR.molecule_attrs(atoms, edges)
    except Exception:
        sattrs = {"natoms": len(atoms), "density": 0.0, "stickiness": 0.0, "temperature": 0.0}
    try:
        units = ATTR.skeleton_units(atoms, edges)
    except Exception:
        units = []
    for u in units:
        if u.get("cell") is None:
            members = u.get("members") or []
            place = rec.get("place") or {}
            cells = []
            for m in members:
                p = place.get(str(m))
                if p is not None:
                    cells.append((int(p[0]), int(p[1])))
            if cells:
                u["cell"] = (int(round(sum(c[0] for c in cells) / len(cells))),
                             int(round(sum(c[1] for c in cells) / len(cells))))
    sites = extract_sites(rec, params)
    try:
        profile = AB.scores(formula)
    except Exception:
        profile = {}
    # 注：L3 器官识别只用界面键与通量事件，不依赖 ops 的 9 项操作值；
    # 为避免对 6000 个分子重复做结构分析（约 15~20s），mol.ops 置空。
    ops = {}
    site_counts: dict[str, int] = {}
    for s in sites:
        site_counts[s.ability] = site_counts.get(s.ability, 0) + 1
    vec = [0] * 9
    for a in atoms:
        vec[ELEM.ORDER.index(a)] += 1
    natoms = len(atoms)
    max_contacts = min(len(sites),
                       int(params.get("contact_base", 3)) + natoms // int(params.get("contact_div", 8)))
    mol = MoleculeInst(
        uid=uid, formula=formula, atoms=atoms, edges=edges, cells=[],
        sites=sites, profile=profile, attrs=sattrs, units=units,
        energy=float(params.get("energy_init", 2.0)),
        elem_vec=vec, rec=rec, ops=ops, max_contacts=max_contacts, parent=parent,
    )
    mol.site_counts = site_counts
    mol.local_cells = _local_cells(units)
    mol.body_cells = []  # 放置时按 rot 旋转后填充
    return mol


# ---------------------------------------------------------------------------
# L2：界面能、结合/断裂、组装体
# ---------------------------------------------------------------------------


def interface_energy(a: MoleculeInst, b: MoleculeInst, sa: ElemSite, sb: ElemSite,
                     env: Env, P: dict) -> float:
    """§3.6：w = κ0·σ_i·σ_j·M_eff·K·Φ·Ψ（可为负 → 排斥）。"""
    try:
        dS = abs(float(a.attrs.get("stickiness", 0.0)) - float(b.attrs.get("stickiness", 0.0)))
        dT = abs(float(a.attrs.get("temperature", 0.0)) - float(b.attrs.get("temperature", 0.0)))
        dD = abs(float(a.attrs.get("density", 0.0)) - float(b.attrs.get("density", 0.0)))
    except Exception:
        dS = dT = dD = 0.0
    phi = (math.exp(-dS / float(P.get("sigma_s", 8.0)))
           * math.exp(-dT / float(P.get("sigma_T", 6.0)))
           * max(0.0, 1.0 - float(P.get("lam_d", 0.5)) * dD / float(P.get("rho_max", 40.0))))
    meff = P.get("M_eff")
    if meff is None:
        meff = build_matrices()[1]
    kk = P.get("K") or BOND_K
    psi = P.get("psi") or PSI
    i, j = _OP_INDEX.get(sa.ability, 0), _OP_INDEX.get(sb.ability, 0)
    m = meff[i][j]
    k = kk.get(sa.bond_type, BOND_K["C"]).get(sb.bond_type, 0.6)
    p = psi.get((sa.kind, sb.kind), 0.8)
    return float(P.get("kappa0", 2.5)) * sa.sigma * sb.sigma * m * k * phi * p


def p_on(w: float, P: dict) -> float:
    """p_on = 1 - exp(-k_on0·exp(β(w-W0)))（§4.2）。"""
    rate = float(P.get("k_on0", 0.05)) * math.exp(float(P.get("beta", 1.8))
                                                 * (w - float(P.get("W0", 0.30))))
    return 1.0 - math.exp(-max(0.0, rate) * float(P.get("delta_t", 1)))


def p_off(w: float, shear: float, P: dict) -> float:
    """p_off = 1 - exp(-k_off0·exp(-β(w-W0) + β·λ_s·s))（§4.2）。"""
    expo = (-float(P.get("beta", 1.8)) * (w - float(P.get("W0", 0.30)))
            + float(P.get("beta", 1.8)) * float(P.get("lam_s", 1.0)) * shear)
    rate = float(P.get("k_off0", 0.05)) * math.exp(min(50.0, expo))
    return 1.0 - math.exp(-max(0.0, rate) * float(P.get("delta_t", 1)))


def candidate_sites(a: MoleculeInst, b: MoleculeInst, P: dict) -> list[tuple]:
    """返回可配对的 (site_idx_a, site_idx_b) 列表（跳过已用位点）。"""
    use = P.get("_site_use") or {}
    free_a = [i for i in range(len(a.sites)) if (a.uid, i) not in use]
    free_b = [i for i in range(len(b.sites)) if (b.uid, i) not in use]
    if not free_a or not free_b:
        return []
    free_a.sort(key=lambda i: a.sites[i].sigma, reverse=True)
    free_b.sort(key=lambda i: b.sites[i].sigma, reverse=True)
    out = []
    for i in free_a[:2]:
        for j in free_b[:2]:
            out.append((i, j))
    return out


def _max_contacts(mol: MoleculeInst) -> int:
    return max(1, int(getattr(mol, "max_contacts", 3)))


def _mol_cell_uids(world: World, cell) -> set:
    return world.occupancy.get(cell) or set()


def neighbor_pairs(world: World, d_cut: int = 1):
    """§4.1 接触判定：骨牌边相邻（距离 1）或顶点相邻（距离 1,1），用空间哈希。

    世界 = 六边形环面；对每个分子只检查其骨牌格周围 12 邻域，且报告 (a<b, 距离)。
    """
    seen = set()
    pairs = []
    L = world.env.L
    occ = world.occupancy
    for uid, mol in world.molecules.items():
        cells = world_mol_cells(world, mol)
        for c in cells:
            for off in _NEIGH12 + ((0, 0),):
                nb = _wrap(_add(c, off), L)
                for other in occ.get(nb, ()):
                    if other == uid:
                        continue
                    key = (uid, other) if uid < other else (other, uid)
                    if key in seen:
                        continue
                    seen.add(key)
                    pairs.append(key)
    return pairs


def world_mol_cells(world: World, mol: MoleculeInst) -> list:
    """分子当前世界格集合（body_cells 缓存旋转后的局部格，移动只做平移+wrap）。"""
    cells = getattr(mol, "body_cells", None)
    if not cells:
        return _wrap_cells_mol(world, mol, mol.pos, mol.rot)
    L = world.env.L
    px, py = mol.pos
    return [((px + c[0]) % L, (py + c[1]) % L) for c in cells]


def _bond_key(a: int, b: int):
    return (a, b) if a < b else (b, a)


def _asm_cells(world: World, asm: Assemblage) -> list:
    if asm.cells:
        return asm.cells
    out = []
    for uid in asm.mols:
        m = world.molecules.get(uid)
        if m is not None:
            out.extend(world_mol_cells(world, m))
    asm.cells = out
    return out


def shell_subgraph(cells, L: int | None = None) -> tuple[bool, int]:
    """检测闭合外层子图；返回 (是否闭合壳子图, 内部格数)。纯几何，O(n)。

    §6.2 的 B 判据要求"存在壳/膜子图"——注意是**子图**，不是整个组装体的
    §4.4 形态：紧凑组装体的外表层本身就是把内外隔开的一圈闭合边界（细胞
    膜的原型）。判定：取有边相邻空格的外层格，若内部格 ≥1 且外层格在边邻接
    图上连通、每格至少有 2 个外层邻格（成环），则存在壳子图。
    """
    cs = list(cells or [])
    if L:
        cs = _unwrap_cells(cs, L)
    occ = set(cs)
    if len(occ) < 7:
        return False, 0
    boundary = set()
    for c in occ:
        for off in _HEX_EDGE:
            if (c[0] + off[0], c[1] + off[1]) not in occ:
                boundary.add(c)
                break
    interior = occ - boundary
    if not interior or len(boundary) < 6:
        return False, len(interior)
    # 外层格在边邻接图上的连通性 + 每格度数 ≥2（闭合环）
    deg = {}
    for c in boundary:
        d = 0
        for off in _HEX_EDGE:
            if (c[0] + off[0], c[1] + off[1]) in boundary:
                d += 1
        deg[c] = d
    if min(deg.values()) < 2:
        return False, len(interior)
    start = next(iter(boundary))
    seen = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for off in _HEX_EDGE:
            v = (u[0] + off[0], u[1] + off[1])
            if v in boundary and v not in seen:
                seen.add(v)
                stack.append(v)
    return (len(seen) == len(boundary)), len(interior)


def classify_shape(mols, bonds, cells, L: int | None = None) -> str:
    """§4.4 六类形态判定（按顺序首个命中）。cells: mol→格集合 或 扁平格列表。

    ``L`` 给定时把环面坐标展开成连续坐标再算几何量（否则跨接缝的组装体
    包围盒会被算成 L×L 的假大团）。
    """
    n = len(mols)
    if n <= 1:
        return "簇" if n == 1 else "团"
    idx = {m: i for i, m in enumerate(mols)}
    m_edges = 0
    degrees = [0] * n
    graph = [[] for _ in range(n)]
    for b in bonds:
        try:
            a0, b0 = b[0], b[1]
        except Exception:
            a0, b0 = b.a, b.b
        if a0 not in idx or b0 not in idx:
            continue
        i, j = idx[a0], idx[b0]
        graph[i].append(j)
        graph[j].append(i)
        degrees[i] += 1
        degrees[j] += 1
        m_edges += 1
    beta0 = m_edges - n + 1
    deg_max = max(degrees) if degrees else 0
    # 直径：小图精确 BFS；大图（n>120）用 2√n 近似，避免 O(n²) 拖慢重建
    if n > 120:
        diam = int(2 * math.sqrt(n))
    else:
        diam = 0
        for s in range(n):
            dist = [-1] * n
            dist[s] = 0
            dq = deque([s])
            while dq:
                u = dq.popleft()
                for v in graph[u]:
                    if dist[v] == -1:
                        dist[v] = dist[u] + 1
                        dq.append(v)
            diam = max(diam, max(dist))
    # 顶点连通度 κ（n 小，暴力：割点近似用最小度）
    kappa = 0
    if n >= 2:
        kappa = min(degrees) if degrees else 0
    # 格子几何
    if cells and isinstance(cells, dict):
        cs = []
        for v in cells.values():
            cs.extend(v)
    else:
        cs = list(cells or [])
    if cs and L:
        cs = _unwrap_cells(cs, L)
    if not cs:
        occ_area = n
        width_q = width_r = width_s = 1
    else:
        qs = [c[0] for c in cs]
        rs = [c[1] for c in cs]
        ss = [c[0] + c[1] for c in cs]
        width_q = max(qs) - min(qs) + 1
        width_r = max(rs) - min(rs) + 1
        width_s = max(ss) - min(ss) + 1
        occ_area = len(set(cs))
        bbox = set()
        for q in range(min(qs), max(qs) + 1):
            for r in range(min(rs), max(rs) + 1):
                bbox.add((q, r))
        occupied = set(cs)
        hole = any(c in bbox and c not in occupied for c in bbox)
    R = width_q * width_r
    t = min(width_q, width_r, width_s)
    if not cs:
        hole = False
    if beta0 >= 1 and hole and n >= 6 and t <= 2:
        return "壳"
    if beta0 >= 2 and kappa >= 2 and deg_max >= 3 and n >= 8:
        return "骨架网络"
    if n >= 6 and t <= 2 and (R / float(n)) >= 1.6 and not hole:
        return "膜"
    if beta0 == 0 and deg_max <= 2 and diam == n - 1 and n >= 4:
        return "链"
    if n <= 4 and diam <= 2:
        return "簇"
    if n >= 5 and (R / float(n)) <= 1.30 and beta0 <= 1 and diam <= 2 * math.sqrt(n):
        return "团"
    return "团"


def rebuild_assemblies(world: World) -> None:
    """§4.3：并查集重建组装体（连通 + E + 内聚度 + 寿命），保留稳定 aid 与 born。"""
    P = world.params
    parent = {}
    rank = {}

    def find(x):
        parent.setdefault(x, x)
        rank.setdefault(x, 0)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    for uid in world.molecules:
        find(uid)
    for (a, b) in world.bonds:
        if a in world.molecules and b in world.molecules:
            union(a, b)
    groups: dict[int, list[int]] = defaultdict(list)
    root_of = {}
    for uid in world.molecules:
        r = find(uid)
        root_of[uid] = r
        groups[r].append(uid)
    # 一次遍历界面键，按连通分量归组（避免 O(bonds × groups)）
    bonds_by_root: dict[int, list] = defaultdict(list)
    for (a, b), bd in world.bonds.items():
        if a in world.molecules and b in world.molecules:
            bonds_by_root[root_of[a]].append(bd)
    old = {}
    for _aid, asm in world.assemblies.items():
        old[frozenset(asm.mols)] = asm
    new_assemblies: dict[int, Assemblage] = {}
    mol_asm: dict[int, int] = {}
    for root, mols in groups.items():
        if len(mols) < 2:
            continue
        bonds = bonds_by_root.get(root)
        if not bonds:
            continue
        E = sum(bd.w for bd in bonds if bd.w > 0)
        c = E / (len(mols) * float(P.get("w_ref", 0.8))) if mols else 0.0
        if E < float(P.get("E_min", 2.5)) or c < float(P.get("c_min", 0.50)):
            continue
        fs = frozenset(mols)
        prev = old.get(fs)
        if prev is not None:
            asm = prev
            asm.bonds = bonds
            asm.E = E
            asm.cohesion = c
            asm.organ_ids = []
        else:
            asm = Assemblage(aid=world.next_aid, mols=sorted(mols), bonds=bonds,
                             E=E, cohesion=c, born=world.t)
            world.next_aid += 1
        new_assemblies[asm.aid] = asm
        for uid in mols:
            mol_asm[uid] = asm.aid
    world.assemblies = new_assemblies
    world.mol_asm = mol_asm
    for asm in world.assemblies.values():
        asm.cells = []
        asm.shape = classify_shape(asm.mols, asm.bonds, _asm_cells(world, asm), L=world.env.L)
        if world.t - asm.born >= int(P.get("tau_min", 30)):
            asm.mature = True


def _reachable_cells(cells, L):
    return {_wrap(c, L) for c in cells}


# ---------------------------------------------------------------------------
# L3：器官通量、器官识别、器官系统
# ---------------------------------------------------------------------------

#: 器官通量代理：把可观测事件计数映射到 §5.2 的功能输出（0~1 附近）
def organ_flux(asm: Assemblage, world: World, window: tuple) -> dict:
    """§5.1/§5.2：用观测窗口内的事件计数近似九种功能通量 F_k。

    window: (t_start, t_end)；实际取 ObsBuffer 中该 aid 的最近采样窗口。
    """
    P = world.params
    # 事件按分子记账；聚合到该组装体当前分子集合（见 ObsBuffer.bump_mol 的注释）
    cnt: dict = defaultdict(float)
    for uid in asm.mols:
        mc = world.obs.mol_counters.get(uid)
        if mc:
            for k, v in mc.items():
                cnt[k] += v
    n = max(1, len(asm.mols))
    kappa0 = float(P.get("kappa0", 2.5))
    eps = 1e-9
    F: dict[str, float] = {}
    # 支撑：界面能密度
    F["sup"] = min(1.0, (asm.E / (n * kappa0 * 0.5)) if n else 0.0)
    # 边界：闭合率 × (1 - 泄漏/入流)
    if asm.shape in ("壳", "膜"):
        closure = 1.0
    else:
        closed, _n_in = shell_subgraph(_asm_cells(world, asm), world.env.L)
        closure = 1.0 if closed else 0.0
    leak_in = cnt.get("leak_in", 0.0)
    leak_out = cnt.get("leak_out", 0.0)
    F["bnd"] = max(0.0, min(1.0, closure * (1.0 - leak_out / (leak_in + eps)))) if closure else 0.0
    # 能量：捕获/释放比
    e_in = cnt.get("nrg_in", 0.0)
    e_out = cnt.get("nrg_out", 0.0)
    F["nrg"] = max(0.0, min(1.0, e_in / (e_in + e_out + eps))) if (e_in + e_out) else 0.0
    # 运输：到达/发出
    adm = cnt.get("ads_in", 0.0)
    F["trn"] = max(0.0, min(1.0, adm / (adm + 3.0 + eps)))
    # 传感：响应/刺激
    stim = cnt.get("stim", 0.0)
    resp = cnt.get("resp", 0.0)
    F["sen"] = max(0.0, min(1.0, resp / (stim + eps))) if stim else 0.0
    # 信息：输出/输入
    i_in = cnt.get("info_in", 0.0)
    i_out = cnt.get("info_out", 0.0)
    F["int"] = max(0.0, min(1.0, i_out / (i_in + eps))) if i_in else 0.0
    # 防御：1 - 被切/切割
    cut_in = cnt.get("cut_in", 0.0)
    cut_out = cnt.get("cut_out", 0.0)
    F["def"] = max(0.0, min(1.0, 1.0 - cut_in / (cut_out + 3.0 + eps)))
    # 催化：切割产物/吸附底物
    F["cat"] = max(0.0, min(1.0, cut_out / (adm + 3.0 + eps)))
    # 复制：事件 × 保真度
    rep = cnt.get("rep", 0.0)
    fid = cnt.get("rep_fid_sum", 0.0) / max(rep, 1.0) if rep else 0.0
    F["rep"] = max(0.0, min(1.0, (rep / 4.0) * fid if rep else 0.0))
    return F


def _bond_ability_pairs(bd: InterfaceBond, ma: MoleculeInst, mb: MoleculeInst) -> list[tuple]:
    """界面键上的能力对（每个接触一对）；兼容没有 contacts 的旧键。"""
    if bd.contacts:
        return [(ma.sites[si].ability, mb.sites[sj].ability)
                for si, sj, _wi in bd.contacts
                if si < len(ma.sites) and sj < len(mb.sites)]
    if bd.site_a < len(ma.sites) and bd.site_b < len(mb.sites):
        return [(ma.sites[bd.site_a].ability, mb.sites[bd.site_b].ability)]
    return []


def _organ_bond_ids(asm: Assemblage, world: World, kind: str) -> list[int]:
    """候选边：两端位点能力覆盖原型必需集合、且 M_dir 对应项 ≥ 0.4。"""
    P = world.params
    proto = ORGAN_PROTOTYPES[kind]
    need = set(proto[1])
    M_dir = P.get("M_dir") or build_matrices()[2]
    out = []
    for i, bd in enumerate(asm.bonds):
        ma = world.molecules.get(bd.a)
        mb = world.molecules.get(bd.b)
        if ma is None or mb is None:
            continue
        pairs = [pr for pr in _bond_ability_pairs(bd, ma, mb) if ({pr[0], pr[1]} & need)]
        if not pairs:
            continue
        dir_val = 0.0
        for ab_a, ab_b in pairs:
            i1 = _OP_INDEX.get(ab_a, 0)
            i2 = _OP_INDEX.get(ab_b, 0)
            dir_val = max(dir_val, abs(M_dir[i1][i2]), abs(M_dir[i2][i1]))
        if dir_val >= 0.4:
            out.append(i)
    return out


def classify_organs(world: World) -> None:
    """§5.3：按通量阈值识别九类器官（滞回：形成难、维持易）。"""
    P = world.params
    theta = P.get("theta") or {k: v[2] for k, v in ORGAN_PROTOTYPES.items()}
    keep_ratio = float(P.get("theta_keep_ratio", 0.8))
    tau_org = int(P.get("tau_org", 60))
    Q_min = float(P.get("Q_min", 0.6))
    theta_scale = float(P.get("theta_scale", 1.0))
    max_org_per_mol = int(P.get("max_organs_per_mol", 2))
    new_organs: dict[int, Organ] = {}
    old_by_key = {(o.aid, o.kind): o for o in world.organs.values()}
    for asm in world.assemblies.values():
        if len(asm.mols) < int(P.get("min_organ_mols", 2)):
            continue
        F = organ_flux(asm, world, (world.t - tau_org, world.t))
        for kind, (name, need, th, need_fid) in ORGAN_PROTOTYPES.items():
            bond_ids = _organ_bond_ids(asm, world, kind)
            if not bond_ids:
                continue
            Fk = F.get(kind, 0.0)
            if need_fid and F.get("rep", 0.0) < 0.85:
                Fk = 0.0
            w_in = sum(asm.bonds[i].w for i in bond_ids if asm.bonds[i].w > 0)
            # 内聚度 Q：器官子图的界面能密度（每分子平均键能 / w_ref），限幅 1。
            # 注：不用"占组装体总键能比例"——否则一个组装体只能容纳一个器官，
            # 与 §8.3 预注册"器官数/组装体 1.8±0.9"矛盾。
            sub_mols = {asm.bonds[i].a for i in bond_ids} | {asm.bonds[i].b for i in bond_ids}
            Q = min(1.0, w_in / (max(1, len(sub_mols)) * float(P.get("w_ref", 0.8))))
            prev = old_by_key.get((asm.aid, kind))
            born = prev.born if prev else world.t
            sustained = world.t - born
            active = prev.active if prev else False
            degraded = prev.degraded if prev else 0
            threshold = (keep_ratio * th if active else th) * theta_scale
            if Fk >= threshold and Q >= Q_min:
                active = True
                degraded = 0
            else:
                if active:
                    degraded += 1
                if degraded >= 30:
                    active = False
                    degraded = 0
            if not active:
                continue
            oid = prev.oid if prev else world.next_oid
            if prev is None:
                world.next_oid += 1
            mols = sorted({asm.bonds[i].a for i in bond_ids} |
                          {asm.bonds[i].b for i in bond_ids})
            organ = Organ(oid=oid, aid=asm.aid, kind=kind, mols=mols,
                          bond_ids=bond_ids, F={kind: Fk}, Q=Q, born=born,
                          active=True, degraded=degraded, sustained=sustained)
            new_organs[oid] = organ
            asm.organ_ids.append(oid) if oid not in asm.organ_ids else None
        # 每个分子最多登记 2 个器官（防重复计数）
        per_mol: dict[int, int] = defaultdict(int)
        for o in new_organs.values():
            if o.aid != asm.aid:
                continue
            for m_uid in o.mols:
                per_mol[m_uid] += 1
        for o in list(new_organs.values()):
            if o.aid != asm.aid:
                continue
            if any(per_mol[u] > max_org_per_mol for u in o.mols):
                new_organs.pop(o.oid, None)
        # 同一组装体内共享 >70% 边的同类器官合并（保留 Q 高者）
        by_kind: dict[str, list[Organ]] = defaultdict(list)
        for o in new_organs.values():
            if o.aid == asm.aid:
                by_kind[o.kind].append(o)
        for kind, orgs in by_kind.items():
            if len(orgs) <= 1:
                continue
            keep = max(orgs, key=lambda o: o.Q)
            for o in orgs:
                if o is not keep:
                    new_organs.pop(o.oid, None)
    # 清理：旧器官若本轮未出现，保留但标为不活跃（避免反复重建 id）
    for old in old_by_key.values():
        if old.oid not in new_organs:
            old.active = False
            old.sustained = max(old.sustained, world.t - old.born)
            new_organs[old.oid] = old
    world.organs = new_organs


def update_systems(world: World) -> None:
    """§5.4：器官耦合图 + 连通分量 → 器官系统（|organs|≥3 且有回路）。"""
    P = world.params
    M_dir = P.get("M_dir") or build_matrices()[2]
    active = [o for o in world.organs.values() if o.active]
    aids = {o.aid for o in active}
    # 器官间耦合：跨器官界面键 w·|M_dir|
    coupling: dict[tuple, float] = defaultdict(float)
    for asm in world.assemblies.values():
        if asm.aid not in aids:
            continue
        mol_to_organs = defaultdict(list)
        for o in active:
            if o.aid != asm.aid:
                continue
            for m in o.mols:
                mol_to_organs[m].append(o)
        for (a, b), bd in world.bonds.items():
            oa = mol_to_organs.get(a)
            ob = mol_to_organs.get(b)
            if not oa or not ob:
                continue
            ma, mb = world.molecules.get(a), world.molecules.get(b)
            if ma is None or mb is None:
                continue
            pairs = _bond_ability_pairs(bd, ma, mb)
            if not pairs:
                continue
            md = max(abs(M_dir[_OP_INDEX.get(ab_a, 0)][_OP_INDEX.get(ab_b, 0)])
                     for ab_a, ab_b in pairs)
            for o1 in oa:
                for o2 in ob:
                    if o1.oid == o2.oid:
                        continue
                    key = (min(o1.oid, o2.oid), max(o1.oid, o2.oid))
                    coupling[key] += bd.w * md
    # 系统 = 连通分量（仅保留 |organs|≥3 且回路数≥1）
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    ids = sorted({o.oid for o in active})
    for oid in ids:
        find(oid)
    for (a, b), c in coupling.items():
        if c >= 0.5:
            union(a, b)
    groups = defaultdict(list)
    for oid in ids:
        groups[find(oid)].append(oid)
    new_systems = {}
    old_by_organs = {frozenset(s.organs): s for s in world.systems.values()}
    for _root, org_ids in groups.items():
        if len(org_ids) < 3:
            continue
        sub = {k: v for k, v in coupling.items() if k[0] in org_ids and k[1] in org_ids}
        m_edges = sum(1 for v in sub.values() if v >= 0.5)
        cycle_rank = max(0, m_edges - len(org_ids) + 1)
        if cycle_rank < 1:
            continue
        fs = frozenset(org_ids)
        prev = old_by_organs.get(fs)
        sid = prev.sid if prev else world.next_sid
        if prev is None:
            world.next_sid += 1
        system = OrganSystem(sid=sid, organs=sorted(org_ids),
                             coupling={f"{k[0]}-{k[1]}": round(v, 4) for k, v in sub.items()},
                             cycle_rank=cycle_rank)
        new_systems[sid] = system
    world.systems = new_systems


# ---------------------------------------------------------------------------
# L4：生命判据（纯读取）与四档
# ---------------------------------------------------------------------------

B_TH, M_TH, R_TH, I_TH, H_FID, H_H = 0.55, 0.25, 0.80, 0.45, 0.85, 0.80


def _sys_obs(world: World, system: OrganSystem, window: tuple) -> dict:
    """汇总系统内所有器官所含组装体分子的观测事件（纯读取，按分子去重）。"""
    cnt: dict[str, float] = defaultdict(float)
    uids: set[int] = set()
    for oid in system.organs:
        org = world.organs.get(oid)
        if org is None:
            continue
        asm = world.assemblies.get(org.aid)
        if asm is not None:
            uids.update(asm.mols)
        else:
            uids.update(org.mols)
    for uid in uids:
        mc = world.obs.mol_counters.get(uid)
        if mc:
            for k, v in mc.items():
                cnt[k] += v
    return dict(cnt)


def _criteria_from_counts(world: World, cnt: dict, organs: list, aids) -> tuple[dict, dict]:
    """由窗口事件计数算 B/M/R/I/H(+A) 判据（纯读取；系统级与组装体级共用）。"""
    values: dict[str, float] = {}
    criteria = {"B": False, "M": False, "R": False, "I": False, "H": False, "A": False}
    aids = list(dict.fromkeys(aids))
    # 窗口内的组装体采样：能量/键数变化
    first_last = {}
    for aid in aids:
        first_last[aid] = world.obs.window(aid, n=world.obs.maxlen)
    E_last = sum(v.get("E_last", 0.0) for v in first_last.values())
    E_first = sum(v.get("E_first", 0.0) for v in first_last.values())
    # 边界维持 B
    leak_in = cnt.get("leak_in", 0.0)
    leak_out = cnt.get("leak_out", 0.0)
    has_shell = any(o.kind == "bnd" for o in organs)
    if not has_shell:
        for aid in aids:
            asm = world.assemblies.get(aid)
            if asm is None:
                continue
            if asm.shape in ("壳", "膜") or shell_subgraph(
                    _asm_cells(world, asm), world.env.L)[0]:
                has_shell = True
                break
    B = (1.0 - leak_out / (leak_in + 1e-9)) if (leak_in > 0) else 0.0
    B = max(0.0, min(1.0, B)) if has_shell else 0.0
    values["B"] = round(B, 4)
    criteria["B"] = bool(B >= B_TH)
    # 代谢 M：harvest=环境能量捕获(含 ads)，dissip=运动/成键耗散；E_maint=基础维持消耗
    harvest = cnt.get("nrg_in", 0.0)
    dissip = cnt.get("nrg_out", 0.0)
    n_mols = 0
    for aid in aids:
        asm = world.assemblies.get(aid)
        if asm is not None:
            n_mols += len(asm.mols)
    n_mols = max(1, n_mols)
    maint_rate = float(world.params.get("maint_rate", 0.4))
    maint = maint_rate * n_mols * float(world.params.get("T_obs", 600))
    M = (harvest - dissip) / (maint + 1e-9)
    values["M"] = round(M, 4)
    values["energy_ratio"] = round(E_last / (E_first + 1e-9), 4) if E_first > 0 else 0.0
    crit_energy = values["energy_ratio"] >= 0.5 if E_first > 0 else False
    criteria["M"] = bool(M >= M_TH and crit_energy)
    # 修复 R
    dmg = cnt.get("dmg", 0.0)
    repair = cnt.get("repair", 0.0)
    R = repair / (dmg + 1e-9) if dmg > 0 else 0.0
    recovered = world.obs.counters.get("perturb_recovered", 0.0) > 0
    values["R"] = round(R, 4)
    values["J_dmg"] = dmg
    values["perturb_recovered"] = float(recovered)
    criteria["R"] = bool(R >= R_TH and dmg >= 3 and recovered)
    # 信息 I（≥2 跳：sig_hops 记录最大跳数）
    i_in = cnt.get("info_in", 0.0)
    i_out = cnt.get("info_out", 0.0)
    hops = cnt.get("sig_hops", 0.0)
    I = min(1.0, i_out / (i_in + 1e-9)) if i_in > 0 else 0.0
    values["I"] = round(I, 4)
    values["sig_hops"] = hops
    criteria["I"] = bool(I >= I_TH and hops >= 2)
    # 复制 H
    rep = cnt.get("rep", 0.0)
    fid = cnt.get("rep_fid_sum", 0.0) / rep if rep > 0 else 0.0
    fertile = cnt.get("rep_fertile", 0.0)
    h = max(0.0, 1.0 - cnt.get("rep_var_sum", 0.0) / max(rep, 1.0))
    values["H_events"] = rep
    values["H_fidelity"] = round(fid, 4)
    values["H_h"] = round(h, 4)
    values["H_fertile"] = fertile
    criteria["H"] = bool(rep >= 1 and fid >= H_FID and h >= H_H and fertile >= 1)
    # 适应 A（可选，三次重复刺激响应斜率 > 0；本原型无刺激器 → 恒 False）
    values["A"] = 0.0
    criteria["A"] = False
    values["n_organs"] = float(len(organs))
    values["organ_kinds"] = float(len({o.kind for o in organs}))
    return values, criteria


def life_report(world: World, sid: int, window: tuple) -> LifeReport:
    """§6.2：只读观测窗口，输出 B/M/R/I/H(+A) 判据向量。**不写任何世界状态**（A0）。"""
    system = world.systems.get(sid)
    criteria = {"B": False, "M": False, "R": False, "I": False, "H": False, "A": False}
    if system is None:
        return LifeReport(sid=sid, tier="无机晶体", criteria=criteria,
                          values={}, window=window)
    organs = [world.organs[o] for o in system.organs if o in world.organs]
    cnt = _sys_obs(world, system, window)
    values, criteria = _criteria_from_counts(world, cnt, organs,
                                            {o.aid for o in organs})
    values["cycle_rank"] = float(system.cycle_rank)
    rep_obj = LifeReport(sid=sid, tier="", criteria=criteria, values=values, window=window)
    rep_obj.tier = tier_from_criteria(rep_obj, world)
    return rep_obj


def assembly_life_report(world: World, aid: int, window: tuple) -> LifeReport:
    """组装体级（无器官系统）的只读判据：§6.3 的"活性无机"档需要它。

    规范里「无机晶体 / 活性无机」按“有无器官”区分，不要求器官系统；
    只有「拟生命 / 有机生命」才要求系统连通。故四档统计同时覆盖系统与
    含器官但尚未成系统的组装体。sid 用 ``-(aid+1)`` 表示组装体级报告。
    """
    asm = world.assemblies.get(aid)
    criteria = {"B": False, "M": False, "R": False, "I": False, "H": False, "A": False}
    sid = -(aid + 1)
    if asm is None:
        return LifeReport(sid=sid, tier="无机晶体", criteria=criteria, values={}, window=window)
    organs = [o for o in world.organs.values() if o.aid == aid and o.active]
    cnt: dict = defaultdict(float)
    for uid in asm.mols:
        mc = world.obs.mol_counters.get(uid)
        if mc:
            for k, v in mc.items():
                cnt[k] += v
    values, criteria = _criteria_from_counts(world, dict(cnt), organs, [aid])
    values["cycle_rank"] = 0.0
    values["aid"] = float(aid)
    rep_obj = LifeReport(sid=sid, tier="", criteria=criteria, values=values, window=window)
    rep_obj.tier = tier_from_criteria(rep_obj, world)
    return rep_obj


def tier_from_criteria(rep: LifeReport, world: World) -> str:
    """§6.3 四档分类：只由布尔判据向量 + 回路闭合 + 可育子代决定。"""
    crit = rep.criteria
    vals = rep.values
    n_organs = int(vals.get("n_organs", 0))
    cycle = int(vals.get("cycle_rank", 0))
    fertile = int(vals.get("H_fertile", 0))
    passed = sum(1 for k in ("B", "M", "R", "I", "H") if crit.get(k))
    if n_organs <= 0:
        return "无机晶体"
    system = world.systems.get(rep.sid) if rep.sid >= 0 else None
    kinds = set()
    if system:
        for oid in system.organs:
            o = world.organs.get(oid)
            if o:
                kinds.add(o.kind)
    if system is not None and crit.get("B") and crit.get("M") and crit.get("R") and crit.get("I") and crit.get("H"):
        # 至少 3 类器官，且含边界/能量/信息中的 2 类
        trio = {"bnd", "nrg", "int"}
        if cycle >= 1 and fertile >= 1 and len(kinds) >= 3 and len(kinds & trio) >= 2:
            return "有机生命"
    # 「拟生命」要求系统连通（§6.3）；组装体级最多到「活性无机」
    if system is not None and n_organs >= 2 and crit.get("B") and crit.get("M") \
            and 1 <= (passed - 2) <= 2:
        return "拟生命"
    if n_organs >= 1:
        return "活性无机"
    return "无机晶体"


def life_report_all(world: World, P: dict | None = None) -> list[LifeReport]:
    """对每个器官系统 + 含器官但未成系统的组装体输出 LifeReport（world 只读）。"""
    P = P or world.params
    T_obs = int(P.get("T_obs", 600))
    window = (world.t - T_obs, world.t)
    reports = []
    covered: set[int] = set()
    for sid in sorted(world.systems):
        reports.append(life_report(world, sid, window))
        for oid in world.systems[sid].organs:
            org = world.organs.get(oid)
            if org is not None:
                covered.add(org.aid)
    for aid in sorted(world.assemblies):
        if aid in covered:
            continue
        if not any(o.aid == aid and o.active for o in world.organs.values()):
            continue
        reports.append(assembly_life_report(world, aid, window))
    return reports


# ---------------------------------------------------------------------------
# 动力学 S1–S8
# ---------------------------------------------------------------------------


def _grid_cells(world: World, mol: MoleculeInst):
    return [_wrap(c, world.env.L) for c in world_mol_cells(world, mol)]


def _can_place(world: World, cells, uid) -> bool:
    for c in cells:
        occ = world.occupancy.get(c)
        if occ and any(u != uid for u in occ):
            return False
    return True


def _occupy(world: World, mol: MoleculeInst) -> None:
    for c in _grid_cells(world, mol):
        world.occupancy.setdefault(c, set()).add(mol.uid)


def _release(world: World, mol: MoleculeInst) -> None:
    for c in _grid_cells(world, mol):
        s = world.occupancy.get(c)
        if s:
            s.discard(mol.uid)
            if not s:
                world.occupancy.pop(c, None)


def _bonds_of(world: World, uid: int):
    """该分子当前界面键（用 uid→键 的邻接索引，避免全表扫描）。"""
    idx = getattr(world, "mol_bonds", None)
    if idx is None:
        world.mol_bonds = idx = defaultdict(set)
        for key in world.bonds:
            idx[key[0]].add(key)
            idx[key[1]].add(key)
    return [world.bonds[k] for k in idx.get(uid, ()) if k in world.bonds]


def _aid_of(world: World, uid: int) -> int | None:
    return (getattr(world, "mol_asm", None) or {}).get(uid)


def _bump_uid(world: World, uid: int, key: str, value: float = 1.0) -> None:
    """把事件记到分子上（纯观测，A0 无关）；器官通量聚合时按器官分子求和。

    注：组装体 aid 每 τ_asm tick 由并查集重排，直接按 aid 记账会把事件记到已消失的
    旧组装体上（实测导致多数新组装体通量恒为 0），故改为分子级归属。
    """
    world.obs.bump_mol(uid, key, value)


def _move_molecule(world: World, mol: MoleculeInst) -> None:
    P = world.params
    # 有界面键的分子被邻居牵制，有效移动概率降低
    nb = len(_bonds_of(world, mol.uid))
    p_move = float(P.get("p_move", 0.6)) / (1.0 + float(P.get("bond_damp", 0.6)) * nb)
    if world.rng.random() > p_move:
        return
    L = world.env.L
    prof = mol.profile or {}
    try:
        w_val = float(prof["axes"]["move"]["by_element"].get("W", 0.0))
    except Exception:
        w_val = 0.0
    beta_m = float(P.get("beta_m", 1.0))
    body = getattr(mol, "body_cells", None) or [(0, 0)]
    cells = world_mol_cells(world, mol)
    base = sum(world.env.rho_at(c) for c in cells) / max(1, len(cells))
    px, py = mol.pos
    nb_uid = mol.uid
    bond_keys = _bonds_of(world, nb_uid) if nb else ()
    # 内聚约束（task-10 标定）：已键合分子移动时优先朝键合邻居质心收敛——
    # 要求移动后到所有键合邻居的六角距离之和不劣于移动前，否则组装体在随机
    # 行走下会退化成松散随机链（R/n 随 tick 增长），壳/膜子图不可能出现。
    bonded_pos = []
    if bond_keys:
        for bd in bond_keys:
            other = bd.b if bd.a == nb_uid else bd.a
            om = world.molecules.get(other)
            if om is not None:
                bonded_pos.append(om.pos)

    def _neighbor_dsum(p):
        tot = 0.0
        for op in bonded_pos:
            dq = ((p[0] - op[0] + L // 2) % L) - L // 2
            dr = ((p[1] - op[1] + L // 2) % L) - L // 2
            tot += (abs(dq) + abs(dr) + abs(dq + dr)) * 0.5
        return tot

    metric0 = _neighbor_dsum(mol.pos) if bonded_pos else 0.0
    best, best_w = None, -1e9
    for dx, dy in _HEX_EDGE:
        npos = ((px + dx) % L, (py + dy) % L)
        new_cells = [((npos[0] + c[0]) % L, (npos[1] + c[1]) % L) for c in body]
        if not _can_place(world, new_cells, mol.uid):
            continue
        # 界面键的物理约束：移动后必须仍与所有已键合邻居保持几何接触，
        # 否则组装体会被分子随机行走拉成散开的随机链（无法形成壳/膜结构）。
        keep = True
        if bond_keys:
            for bd in bond_keys:
                other = bd.b if bd.a == nb_uid else bd.a
                om = world.molecules.get(other)
                if om is None:
                    continue
                if not _cells_touch(new_cells, world_mol_cells(world, om), L):
                    keep = False
                    break
        if not keep:
            continue
        # 严格收缩：只接受使到键合邻居距离和严格下降的候选，链会卷成紧凑团
        if bonded_pos and _neighbor_dsum(npos) >= metric0 - 1e-9:
            continue
        val = sum(world.env.rho_at(c) for c in new_cells) / max(1, len(new_cells))
        score = math.exp(beta_m * w_val * (val - base))
        if score > best_w:
            best_w, best = score, (npos, new_cells)
    if best is None:
        return
    _release(world, mol)
    mol.pos, cells_new = best
    mol.cells = cells_new
    _occupy(world, mol)
    mol.energy = max(0.0, mol.energy - float(P.get("move_cost", 0.02)))
    world.obs.bump_mol(mol.uid, "nrg_out", float(P.get("move_cost", 0.02)))
    # 移动后界面键可能被拉断（简化：距离过远的断键在 S3 处理）


def _push_apart(world: World, a: MoleculeInst, b: MoleculeInst) -> None:
    L = world.env.L
    dq = ((b.pos[0] - a.pos[0] + L // 2) % L) - L // 2
    dr = ((b.pos[1] - a.pos[1] + L // 2) % L) - L // 2
    d = (dq, dr)
    steps = _HEX_EDGE
    best = None
    bestd = -1
    for s in steps:
        dot = s[0] * d[0] + s[1] * d[1]
        if dot > bestd:
            bestd, best = dot, s
    npos = _add(b.pos, best)
    new_cells = _wrap_cells_mol(world, b, npos, b.rot)
    if _can_place(world, new_cells, b.uid):
        _release(world, b)
        b.pos = npos
        b.cells = new_cells
        _occupy(world, b)


def _wrap_cells_mol(world: World, mol: MoleculeInst, pos, rot):
    L = world.env.L
    local = getattr(mol, "local_cells", None)
    if not local:
        local = [(int(u["cell"][0]), int(u["cell"][1])) for u in mol.units if u.get("cell")] or [(0, 0)]
    return [_wrap(_add(_rot(c, rot), pos), L) for c in local]


def _add_bond(world: World, a: MoleculeInst, b: MoleculeInst, sa: int, sb: int, w: float,
              contacts: list | None = None) -> bool:
    """建立一条无向界面键；``contacts`` 给出 [(a 侧位点, b 侧位点, w_i), ...]。

    ``w`` 是各接触的界面能之和（一个 InterfaceBond 可含多个位点接触）。
    能量按接触数计费（每个接触 ``bond_cost``）。
    """
    key = _bond_key(a.uid, b.uid)
    if key in world.bonds:
        return False
    if len(_bonds_of(world, a.uid)) >= _max_contacts(a):
        return False
    if len(_bonds_of(world, b.uid)) >= _max_contacts(b):
        return False
    # 规范里 InterfaceBond 以 (a,b) 为无向对；这里固定 a<b，同时把 site 索引
    # 对齐到 (site_a ↔ a, site_b ↔ b)，避免两个方向的索引错位。
    if a.uid < b.uid:
        ua, ub, ia, ib = a.uid, b.uid, sa, sb
        cl = [(si, sj, wi) for si, sj, wi in (contacts or [(sa, sb, w)])]
    else:
        ua, ub, ia, ib = b.uid, a.uid, sb, sa
        cl = [(sj, si, wi) for si, sj, wi in (contacts or [(sa, sb, w)])]
    for si, sj, _wi in cl:
        if (ua, si) in world.site_use or (ub, sj) in world.site_use:
            return False
    cost = float(world.params.get("bond_cost", 1.0)) * len(cl)
    if a.energy < cost or b.energy < cost:
        return False
    a.energy -= cost
    b.energy -= cost
    world.obs.bump_mol(a.uid, "nrg_out", cost)
    world.obs.bump_mol(b.uid, "nrg_out", cost)
    bond = InterfaceBond(a=ua, b=ub, site_a=ia, site_b=ib, w=w,
                         pair=(sa, sb), born=world.t, contacts=cl)
    world.bonds[key] = bond
    for si, sj, _wi in cl:
        world.site_use[(ua, si)] = key
        world.site_use[(ub, sj)] = key
    idx = getattr(world, "mol_bonds", None)
    if idx is None:
        world.mol_bonds = idx = defaultdict(set)
    idx[a.uid].add(key)
    idx[b.uid].add(key)
    world.obs.bump_mol(a.uid, "bind", 1.0)
    world.obs.bump_mol(b.uid, "bind", 1.0)
    world.obs.bump_mol(a.uid, "leak_in", 1.0)
    world.obs.bump_mol(b.uid, "leak_in", 1.0)
    return True


def _remove_bond(world: World, key, reason: str = "break") -> None:
    bond = world.bonds.pop(key, None)
    if bond is None:
        return
    if bond.contacts:
        for si, sj, _wi in bond.contacts:
            world.site_use.pop((bond.a, si), None)
            world.site_use.pop((bond.b, sj), None)
    else:  # pragma: no cover - 兼容旧数据
        world.site_use.pop((bond.a, bond.site_a), None)
        world.site_use.pop((bond.b, bond.site_b), None)
    idx = getattr(world, "mol_bonds", None)
    if idx is not None:
        idx[bond.a].discard(key)
        idx[bond.b].discard(key)
    ma = world.molecules.get(bond.a)
    mb = world.molecules.get(bond.b)
    rel = float(world.params.get("bond_release", 0.8))
    if ma is not None:
        ma.energy = min(10.0, ma.energy + rel * 0.5)
    if mb is not None:
        mb.energy = min(10.0, mb.energy + rel * 0.5)
    world.obs.bump_mol(bond.a, "brk", 1.0)
    world.obs.bump_mol(bond.b, "brk", 1.0)
    world.obs.bump_mol(bond.a, "leak_out", 1.0)
    world.obs.bump_mol(bond.b, "leak_out", 1.0)
    if reason == "damage":
        world.obs.bump_mol(bond.a, "dmg", 1.0)
        world.obs.bump_mol(bond.b, "dmg", 1.0)
    elif reason == "cut":
        # cut_out 由切割方（F 位点所属分子）在 _exchange 记录；这里记被切断一侧
        world.obs.bump_mol(bond.a, "cut_in", 1.0)
        world.obs.bump_mol(bond.b, "cut_in", 1.0)
        world.obs.bump_mol(bond.a, "cut", 1.0)
        world.obs.bump_mol(bond.b, "cut", 1.0)


def _diffuse_env(world: World) -> None:
    P = world.params
    if world.t % int(P.get("field_every", 5)) != 0:
        return
    env = world.env
    env.diffuse(float(P.get("D_E", 0.15)))
    # 温度场：分子所在格的物性温度 + 轻微扩散
    L = env.L
    temp = env.temp
    for mol in world.molecules.values():
        try:
            tval = float(mol.attrs.get("temperature", 0.0)) / 40.0
        except Exception:
            tval = 0.0
        for c in _grid_cells(world, mol):
            temp[c[0]][c[1]] = 0.7 * temp[c[0]][c[1]] + 0.3 * tval
    mean_t = sum(sum(row) for row in temp) / (L * L)
    env.shear = float(P.get("s0", 0.1)) + float(P.get("s_T", 0.02)) * mean_t


def _rupture(world: World) -> None:
    """§4.2 几何断裂：界面键两端的骨牌不再接触（距离>1）时按概率断开。"""
    rng = world.rng
    if not world.bonds:
        return
    for key, bd in list(world.bonds.items()):
        ma = world.molecules.get(bd.a)
        mb = world.molecules.get(bd.b)
        if ma is None or mb is None:
            _remove_bond(world, key, "break")
            continue
        ca = world_mol_cells(world, ma)
        cb = world_mol_cells(world, mb)
        near = _cells_touch(ca, cb, world.env.L)
        if not near and rng.random() < float(world.params.get("rupture_p", 0.2)):
            _remove_bond(world, key, "break")


def step_world(world: World) -> None:
    """一拍 S1–S8（§7.1/§7.3）。S8 只写观测缓冲，不写生命状态（A0）。"""
    P = world.params
    rng = world.rng
    world.t += 1
    # S1 环境场（扩散 + 温度 + 剪切）
    _diffuse_env(world)
    # S2 分子扩散
    for mol in list(world.molecules.values()):
        _move_molecule(world, mol)
        mol.age += 1
    # S2.5 几何断裂（移动后失去接触的界面键）
    _rupture(world)
    # S3 界面动力学
    pairs = neighbor_pairs(world)
    pair_cap = max(1, int(P.get("contacts_per_pair", 1)))
    W_MIN = float(P.get("W_MIN", 0.15))
    for (ua, ub) in pairs:
        a = world.molecules.get(ua)
        b = world.molecules.get(ub)
        if a is None or b is None:
            continue
        # pairs 列表是在本 tick 开头算的；S3 内的排斥可能已经把 b 推开若干格，
        # 因此成键前必须重新确认几何接触（否则会造出远距离的假界面键）。
        if not _cells_touch(world_mol_cells(world, a), world_mol_cells(world, b), world.env.L):
            continue
        key = _bond_key(ua, ub)
        shear = world.env.shear
        bond = world.bonds.get(key)
        if bond is not None:
            if rng.random() < p_off(bond.w, shear, P):
                _remove_bond(world, key, "break")
            continue
        if len(_bonds_of(world, a.uid)) >= _max_contacts(a):
            continue
        if len(_bonds_of(world, b.uid)) >= _max_contacts(b):
            continue
        P["_site_use"] = world.site_use
        cands = candidate_sites(a, b, P)
        if not cands:
            continue
        # 逐候选位点对算界面能；w<0 的候选对先触发排斥
        ws = [(interface_energy(a, b, a.sites[si], b.sites[sj], world.env, P), si, sj)
              for si, sj in cands]
        if max(t[0] for t in ws) < 0.0:
            _push_apart(world, a, b)
            world.obs.bump("repulse", 1.0)
            continue
        # 一对分子可在多个未用位点上同时接触（§3.2 每位点 1 键），
        # 聚合为一条 InterfaceBond；同一键内位点不得重复（同一位点 1 条键）。
        chosen_all = sorted((t for t in ws if t[0] >= W_MIN),
                            key=lambda t: t[0], reverse=True)
        chosen = []
        used_a: set = set()
        used_b: set = set()
        for wi, si, sj in chosen_all:
            if si in used_a or sj in used_b:
                continue
            used_a.add(si)
            used_b.add(sj)
            chosen.append((wi, si, sj))
            if len(chosen) >= pair_cap:
                break
        if not chosen:
            continue
        w_sum = sum(t[0] for t in chosen)
        contacts = [(si, sj, wi) for wi, si, sj in chosen]
        if rng.random() < p_on(w_sum, P):
            _add_bond(world, a, b, chosen[0][1], chosen[0][2], w_sum, contacts=contacts)
    P.pop("_site_use", None)
    # S4 物质交换：吸附/切割/充能
    _exchange(world)
    # S5 信号脉冲
    _signals(world)
    # S6 损伤与修复
    _damage_repair(world)
    # S7 复制
    _replicate(world)
    # S8 观测识别（只读生命状态）
    if world.t % int(P.get("tau_asm", 10)) == 0:
        rebuild_assemblies(world)
    if world.t % int(P.get("tau_org", 20)) == 0:
        classify_organs(world)
    if world.t % int(P.get("tau_sys", 50)) == 0:
        update_systems(world)
    _record_observables(world)


def _exchange(world: World) -> None:
    """S4：A 位点捕获、F 位点切割释放、P 位点充能（保守、能量化）。

    性能：按 ``mol.site_counts`` 的位点计数成批处理，避免逐位点 12 次循环。
    """
    P = world.params
    rng = world.rng
    charge = float(P.get("charge_rate", 0.05))
    eta = float(P.get("eta", 0.8))
    ie_scale = float(P.get("i_e_scale", 0.3))
    W_MIN = float(P.get("W_MIN", 0.15))
    for mol in world.molecules.values():
        counts = getattr(mol, "site_counts", None) or {}
        # S1 的局域能量输入 I_E = ρ_E·η（按格点注入；i_e_scale 为时间步标定系数）
        rho = world.env.rho_at(mol.pos)
        intake = eta * rho * ie_scale
        mol.energy = min(10.0, mol.energy + intake)
        world.obs.bump_mol(mol.uid, "nrg_in", intake)
        if not counts:
            continue
        na = counts.get("ads", 0)
        if na:
            gained = 0.02 * na * rho
            mol.energy = min(10.0, mol.energy + gained)
            world.obs.bump_mol(mol.uid, "nrg_in", gained)
            world.obs.bump_mol(mol.uid, "ads_in", float(na))
        ns = counts.get("sto", 0)
        if ns and rho > 0.2:
            mol.energy = min(10.0, mol.energy + charge * ns)
        nm = counts.get("mov", 0)
        if nm:
            spent = 0.002 * nm
            mol.energy = max(0.0, mol.energy - spent)
            world.obs.bump_mol(mol.uid, "nrg_out", spent)
        nd = counts.get("dif", 0)
        if nd:
            world.obs.bump_mol(mol.uid, "resp", 0.2 * nd)
        # 切割：每个 clv 位点 1%/tick 概率断开一条界面键
        nclv = counts.get("clv", 0)
        if nclv and rng.random() < 0.01 * nclv:
            for bd in list(_bonds_of(world, mol.uid)):
                if bd.w > W_MIN and rng.random() < 0.5:
                    world.obs.bump_mol(mol.uid, "cut_out", 1.0)
                    _remove_bond(world, (bd.a, bd.b), "cut")
                    break


def _signals(world: World) -> None:
    """S5：L 位点发脉冲，沿 M_dir≥0.3 的界面键传播，衰减 0.7/跳（最多 3 跳）。"""
    P = world.params
    M_dir = P.get("M_dir") or build_matrices()[2]
    rng = world.rng
    pulses = world.stats.setdefault("pulses", [])
    # 发射：只有含 sig 位点的分子
    for mol in world.molecules.values():
        if not (getattr(mol, "site_counts", None) or {}).get("sig"):
            continue
        if rng.random() < 0.02 and _bonds_of(world, mol.uid):
            pulses.append({"from": mol.uid, "strength": 1.0, "hops": 0, "age": 0,
                           "seen": {mol.uid}})
            world.obs.bump_mol(mol.uid, "stim", 1.0)
            world.obs.bump_mol(mol.uid, "info_in", 1.0)
    surviving = []
    for p in pulses:
        p["age"] += 1
        if p["age"] > 3:
            continue
        src = p["from"]
        nxt = None
        for bd in _bonds_of(world, src):
            other = bd.b if bd.a == src else bd.a
            if other in p["seen"]:
                continue
            ma = world.molecules.get(src)
            mb = world.molecules.get(other)
            if ma is None or mb is None:
                continue
            if bd.site_a >= len(ma.sites) or bd.site_b >= len(mb.sites):
                continue
            ab_a = ma.sites[bd.site_a].ability
            ab_b = mb.sites[bd.site_b].ability
            if abs(M_dir[_OP_INDEX.get(ab_a, 0)][_OP_INDEX.get(ab_b, 0)]) >= 0.3:
                nxt = other
                break
        if nxt is None:
            continue
        p["hops"] += 1
        p["strength"] *= 0.7
        p["from"] = nxt
        p["seen"].add(nxt)
        if p["strength"] < 0.08:
            continue
        world.obs.bump_mol(nxt, "info_out", 0.1)
        world.obs.bump_mol(nxt, "sig_hops", 1.0)
        surviving.append(p)
    world.stats["pulses"] = surviving[-200:]


def _damage_repair(world: World) -> None:
    """S6：损伤 p_dmg 断键；支/分/粘 位点耗能重连（脉冲可调制）。"""
    P = world.params
    rng = world.rng
    d0 = float(P.get("d0", 0.01))
    for key, bd in list(world.bonds.items()):
        p_dmg = 1.0 - math.exp(-d0 * math.exp(-max(0.0, bd.w) / 2.0))
        if rng.random() < p_dmg:
            _remove_bond(world, key, "damage")
    # 修复：在组装体内寻找"可重连"的分子对（每组装体最多 20 个随机候选对，避免 O(n²)）
    repair_abilities = {"sup", "dif", "adh"}
    for asm in list(world.assemblies.values()):
        mols = [world.molecules.get(u) for u in asm.mols]
        mols = [m for m in mols if m is not None and m.energy >= float(P.get("e_rep", 1.0))
                and getattr(m, "site_counts", None)
                and any(m.site_counts.get(k) for k in repair_abilities)]
        if len(mols) < 2:
            continue
        tries = min(20, len(mols) * (len(mols) - 1) // 2)
        for _ in range(tries):
            a = mols[rng.randrange(len(mols))]
            b = mols[rng.randrange(len(mols))]
            if a.uid == b.uid:
                continue
            if _bond_key(a.uid, b.uid) in world.bonds:
                continue
            if len(_bonds_of(world, a.uid)) >= _max_contacts(a):
                continue
            if len(_bonds_of(world, b.uid)) >= _max_contacts(b):
                continue
            P["_site_use"] = world.site_use
            cands = candidate_sites(a, b, P)
            P.pop("_site_use", None)
            if not cands:
                continue
            si, sj = cands[0]
            w = interface_energy(a, b, a.sites[si], b.sites[sj], world.env, P)
            if w >= float(P.get("W_MIN", 0.15)) and rng.random() < 0.5:
                if _add_bond(world, a, b, si, sj, w):
                    a.energy = max(0.0, a.energy - float(P.get("e_rep", 1.0)))
                    world.obs.bump_mol(a.uid, "repair", 1.0)
                    world.obs.bump_mol(b.uid, "repair", 1.0)


def _replicate(world: World) -> None:
    """S7：复制器官活跃且有模板时复制一个子分子（元素替换突变 μ）。"""
    P = world.params
    rng = world.rng
    mu = float(P.get("mu", 0.02))
    rep_organs = [o for o in world.organs.values()
                  if o.active and o.kind == "rep" and o.bond_ids]
    if not rep_organs:
        return
    for organ in rep_organs:
        if rng.random() > 0.02:
            continue
        asm = world.assemblies.get(organ.aid)
        if asm is None:
            continue
        template = None
        for uid in organ.mols:
            m = world.molecules.get(uid)
            if m is not None and (template is None or len(m.atoms) > len(template.atoms)):
                template = m
        if template is None or len(template.atoms) < 3:
            continue
        # 复制 + 突变（同类别元素替换，保持价数/饱和性）
        atoms = list(template.atoms)
        mutated = 0
        for i, el in enumerate(atoms):
            if rng.random() < mu:
                cat = ELEM.ELEM[el][0]
                alternatives = [e for e in ELEM.ORDER if ELEM.ELEM[e][0] == cat and e != el]
                if alternatives:
                    atoms[i] = rng.choice(alternatives)
                    mutated += 1
        if mutated == 0:
            continue
        new_rec = dict(template.rec)
        new_rec = {**new_rec, "atoms": atoms, "formula": ELEM.formula_of(atoms)}
        child = make_molecule(new_rec, world.next_uid, P, parent=template.uid)
        world.next_uid += 1
        # 放在模板旁边空格
        placed = False
        for d in _HEX_EDGE:
            npos = _add(template.pos, d)
            cells = _wrap_cells_mol(world, child, npos, template.rot)
            if _can_place(world, cells, child.uid):
                child.pos = npos
                child.rot = template.rot
                child.body_cells = [_rot(c, template.rot) for c in child.local_cells]
                child.cells = list(cells)
                world.molecules[child.uid] = child
                _occupy(world, child)
                placed = True
                break
        if not placed:
            continue
        fid = _cosine(child.elem_vec, template.elem_vec)
        var = 1.0 - fid
        world.obs.bump_mol(template.uid, "rep", 1.0)
        world.obs.bump_mol(template.uid, "rep_fid_sum", fid)
        world.obs.bump_mol(template.uid, "rep_var_sum", var)
        world.stats["last_child"] = (organ.aid, child.uid, fid)
        asm.rep += 1


def _record_observables(world: World) -> None:
    """S8 的观测部分：只记录窗口观测量（A0）。"""
    P = world.params
    obs = world.obs
    T_obs = int(P.get("T_obs", 600))
    dt = 10
    if world.t % dt != 0:
        return
    # 组装体级采样
    for asm in world.assemblies.values():
        sample = {
            "E": round(asm.E, 4),
            "bonds": len(asm.bonds),
            "mols": len(asm.mols),
            "shape": asm.shape,
        }
        obs.record_sample(asm.aid, sample)
    obs.counters["t"] = world.t
    # 中段扰动（§6.2 R 判据）：在窗口开始时记录基线与断键
    if "perturb_t" not in world.stats and world.t >= int(P.get("t_warm", 300)) + T_obs // 2:
        world.stats["perturb_t"] = world.t
        n_bonds = len(world.bonds)
        world.stats["perturb_bonds"] = n_bonds
        removed = 0
        for key in list(world.bonds):
            if world.rng.random() < 0.1:
                _remove_bond(world, key, "break")
                removed += 1
        world.stats["perturb_removed"] = removed
    if "perturb_t" in world.stats and "perturb_recovered" not in world.stats:
        if world.t - world.stats["perturb_t"] >= int(0.3 * T_obs):
            base = world.stats.get("perturb_bonds", 1)
            removed = world.stats.get("perturb_removed", 0)
            recovered = len(world.bonds) >= 0.9 * max(1, base - removed)
            world.stats["perturb_recovered"] = bool(recovered)
            obs.counters["perturb_recovered"] = 1.0 if recovered else 0.0


# ---------------------------------------------------------------------------
# 世界初始化与运行
# ---------------------------------------------------------------------------


def init_world(records: list[dict], rng, P: dict) -> World:
    """L1→L2：按骨牌放置 N 个分子（失败则丢弃并计数）。"""
    if "M_eff" not in P:
        P["M"], P["M_eff"], P["M_dir"] = build_matrices()
    L = int(P.get("L", 160))
    P["L"] = L
    env = Env(L=L, rho_E=[[1.0] * L for _ in range(L)],
              temp=[[0.0] * L for _ in range(L)], shear=float(P.get("s0", 0.1)))
    world = World(t=0, env=env, molecules={}, bonds={}, assemblies={}, organs={},
                  systems={}, pool=[], rng=rng, params=P,
                  obs=ObsBuffer(maxlen=max(1, int(P.get("T_obs", 600)) // 10)))
    dropped = 0
    attempts = 0
    for rec in records:
        mol = make_molecule(rec, world.next_uid, P)
        world.next_uid += 1
        placed = False
        for _try in range(8):
            attempts += 1
            rot = rng.randrange(6)
            pos = (rng.randrange(L), rng.randrange(L))
            cells = _wrap_cells_mol(world, mol, pos, rot)
            if _can_place(world, cells, mol.uid):
                mol.pos, mol.rot = pos, rot
                mol.body_cells = [_rot(c, rot) for c in mol.local_cells]
                mol.cells = list(cells)
                world.molecules[mol.uid] = mol
                _occupy(world, mol)
                placed = True
                break
        if not placed:
            dropped += 1
    world.stats["dropped"] = dropped
    world.stats["attempts"] = attempts
    return world


def run_world(records, seed: int, P: dict | None = None):
    """跑满 ``P['steps']`` 拍，返回 (world, life_reports)；同 seed 逐位可复现。"""
    P = P or load_params()
    if "M_eff" not in P:
        P["M"], P["M_eff"], P["M_dir"] = build_matrices()
    P = dict(P)  # 不污染调用方
    P.setdefault("seed", seed)
    rng = random.Random(seed)
    world = init_world(records, rng, P)
    steps = int(P.get("steps", 1200))
    for _ in range(steps):
        step_world(world)
    # 收尾：t=steps 不一定是 τ_asm/τ_org/τ_sys 的公倍数，跑一次 L2→L4 识别，
    # 否则器官会指向已经重排掉的旧 aid，四档统计为空（只重建观测，不改动力学）。
    rebuild_assemblies(world)
    classify_organs(world)
    update_systems(world)
    reports = life_report_all(world, P)
    return world, reports


# ---------------------------------------------------------------------------
# 抽样与实验
# ---------------------------------------------------------------------------


def _valid_records():
    cat = get_catalog()
    return [r for r in cat.records()
            if r.get("place") and r.get("atoms") and r.get("natoms")]


def sample_records(n: int, seed: int = 20261119) -> list[dict]:
    """§8.1 分层抽样：natoms 桶 × 是否多骨架（用 natoms 与 source 代理）。

    规范的分层变量是 ``natoms × n_skeletons × source``；为性能起见这里用
    ``natoms`` 分桶 + ``source`` 分层（对全部 8.4 万条计算 skeleton_units 太慢），
    并在层内按目录真实占比比例分配、层内随机不放回。丢弃无 ``place`` 记录（0.29%）。
    """
    rng = random.Random(seed)
    recs = _valid_records()
    if n >= len(recs):
        out = list(recs)
        rng.shuffle(out)
        return out[:n]
    strata: dict[tuple, list] = defaultdict(list)
    for r in recs:
        nat = int(r.get("natoms") or len(r.get("atoms") or []))
        bucket = min(16, max(9, nat))
        strata[(bucket, r.get("source") or "?")].append(r)
    total = sum(len(v) for v in strata.values())
    alloc = {}
    for key, v in strata.items():
        alloc[key] = int(round(n * len(v) / total))
    diff = n - sum(alloc.values())
    keys = sorted(alloc, key=lambda k: -len(strata[k]))
    i = 0
    while diff != 0 and keys:
        k = keys[i % len(keys)]
        if diff > 0:
            alloc[k] += 1
            diff -= 1
        elif alloc[k] > 0:
            alloc[k] -= 1
            diff += 1
        i += 1
    out = []
    for key, cnt in alloc.items():
        pool_ = strata[key]
        if cnt >= len(pool_):
            out.extend(pool_)
        elif cnt > 0:
            out.extend(rng.sample(pool_, cnt))
    rng.shuffle(out)
    return out[:n]


#: 四档顺序（报告用）
TIERS = ("无机晶体", "活性无机", "拟生命", "有机生命")


def _world_digest(world: World) -> str:
    """世界状态摘要（A0 测试：life_report 前后应逐位一致）。"""
    import hashlib
    h = hashlib.sha256()
    h.update(f"t={world.t};n={len(world.molecules)};b={len(world.bonds)}".encode())
    for uid in sorted(world.molecules):
        m = world.molecules[uid]
        h.update(f"{uid}:{m.formula}:{m.pos}:{m.rot}:{round(m.energy, 6)}".encode())
    for key in sorted(world.bonds):
        bd = world.bonds[key]
        h.update(f"{key}:{round(bd.w, 6)}:{bd.site_a}:{bd.site_b}".encode())
    for aid in sorted(world.assemblies):
        a = world.assemblies[aid]
        h.update(f"{aid}:{a.shape}:{round(a.E, 6)}:{a.mols}".encode())
    for oid in sorted(world.organs):
        o = world.organs[oid]
        h.update(f"{oid}:{o.kind}:{o.active}:{o.aid}".encode())
    return h.hexdigest()


def _summarize(world: World, reports: list[LifeReport], P: dict) -> dict:
    """把一次运行整理成 §8.5 的 JSON 化输出。"""
    n_mols = max(1, len(world.molecules))
    in_asm = sum(len(a.mols) for a in world.assemblies.values())
    sizes = sorted(len(a.mols) for a in world.assemblies.values())
    organs = [o for o in world.organs.values() if o.active]
    n_asm = len(world.assemblies)
    organ_counts = [sum(1 for o in organs if o.aid == a.aid) for a in world.assemblies.values()]
    kinds_hist: dict[str, int] = defaultdict(int)
    for o in organs:
        kinds_hist[ORGAN_NAMES.get(o.kind, o.kind)] += 1
    asm_with_organ = sum(1 for c in organ_counts if c > 0)
    # 器官类型占比（有器官的组装体）
    kind_share = {}
    for k, v in kinds_hist.items():
        kind_share[k] = round(100.0 * v / max(1, len(organs)), 2)
    # 判据通过率（系统级）
    rate = {}
    for c in ("B", "M", "R", "I", "H", "A"):
        if reports:
            rate[c] = round(100.0 * sum(1 for r in reports if r.criteria.get(c)) / len(reports), 2)
        else:
            rate[c] = 0.0
    tiers = {t: 0 for t in TIERS}
    for rep in reports:
        tiers[rep.tier] = tiers.get(rep.tier, 0) + 1
    # 说明：四档统计覆盖「器官系统」与「含器官但未成系统的组装体」两层；
    # 无机晶体/活性无机按有无器官区分（§6.3），拟生命/有机生命要求系统连通。
    tiers_system = {t: 0 for t in TIERS}
    tiers_assembly = {t: 0 for t in TIERS}
    for rep in reports:
        if rep.sid >= 0:
            tiers_system[rep.tier] = tiers_system.get(rep.tier, 0) + 1
        else:
            tiers_assembly[rep.tier] = tiers_assembly.get(rep.tier, 0) + 1
    assemblies = []
    for aid in sorted(world.assemblies)[:50]:
        a = world.assemblies[aid]
        assemblies.append({
            "aid": aid, "n": len(a.mols), "shape": a.shape,
            "E": round(a.E, 4), "c": round(a.cohesion, 4),
            "organs": [{"kind": o.kind, "F": round(list(o.F.values())[0], 4),
                        "Q": round(o.Q, 4)} for o in organs if o.aid == aid],
            "tier": "",
        })
    return {
        "params": {k: v for k, v in P.items()
                   if k not in ("M", "M_eff", "M_dir", "K", "psi", "theta", "affinity")},
        "seed": world.params.get("seed"),
        "t": world.t,
        "molecules": len(world.molecules),
        "dropped": world.stats.get("dropped", 0),
        "assemblies": len(world.assemblies),
        "asm_size": {
            "n": len(sizes),
            "median": sizes[len(sizes) // 2] if sizes else 0,
            "p90": sizes[min(len(sizes) - 1, int(0.9 * len(sizes)))] if sizes else 0,
            "max": max(sizes) if sizes else 0,
            "mean": round(sum(sizes) / len(sizes), 3) if sizes else 0.0,
        },
        "assembly_rate": round(100.0 * in_asm / n_mols, 2),
        "organs": len(organs),
        "organs_per_asm": round(len(organs) / n_asm, 3) if n_asm else 0.0,
        "asm_with_organ": asm_with_organ,
        "organ_kind_share": kind_share,
        "organ_kinds_hist": dict(kinds_hist),
        "systems": len(world.systems),
        "system_cycle_rank": {sid: s.cycle_rank for sid, s in world.systems.items()},
        "rates": rate,
        "tiers": tiers,
        "tiers_system": tiers_system,
        "tiers_assembly": tiers_assembly,
        "reports": [
            {"sid": r.sid, "tier": r.tier, "criteria": r.criteria,
             "values": {k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in r.values.items()}}
            for r in reports
        ],
        "assemblies_detail": assemblies,
        "energy_mean": round(sum(m.energy for m in world.molecules.values()) / n_mols, 4),
        "bond_count": len(world.bonds),
    }


def run_experiment(records, seed: int, P: dict | None = None) -> dict:
    """跑一次实验并返回 §8.5 的 JSON 化结果。"""
    P = P or load_params()
    P = dict(P)
    P["seed"] = seed
    t0 = time.time()
    world, reports = run_world(records, seed, P)
    elapsed = time.time() - t0
    out = _summarize(world, reports, P)
    out["seed"] = seed
    out["elapsed_s"] = round(elapsed, 2)
    out["digest"] = _world_digest(world)
    # 出处/新颖性（§8.4 T6）：分子→组装体→器官→系统 的深度
    depth = 1
    if world.assemblies:
        depth = 2
    if any(o.active for o in world.organs.values()):
        depth = 3
    if world.systems:
        depth = 4
    out["provenance"] = {"depth": depth,
                         "n_molecules": len(world.molecules),
                         "n_assemblies": len(world.assemblies),
                         "n_organs": len([o for o in world.organs.values() if o.active]),
                         "n_systems": len(world.systems)}
    out["novelty"] = {"max_assembly": out["asm_size"]["max"],
                      "max_organs": max((len(a.organ_ids) for a in world.assemblies.values()), default=0)}
    return out


def project_blocks(world: World) -> list[dict]:
    """T75 投影接口：分子→多格骨牌、组装体→相邻骨牌组、器官→描边、生命体→body。"""
    out = []
    for uid in sorted(world.molecules):
        m = world.molecules[uid]
        out.append({
            "uid": uid, "formula": m.formula, "pos": list(m.pos), "rot": m.rot,
            "cells": [list(c) for c in _grid_cells(world, m)],
            "shape": "molecule", "natoms": len(m.atoms),
            "sites": [{"element": s.element, "ability": s.ability, "kind": s.kind}
                      for s in m.sites],
        })
    for aid in sorted(world.assemblies):
        a = world.assemblies[aid]
        org = [o for o in world.organs.values() if o.aid == aid and o.active]
        out.append({"aid": aid, "shape": a.shape, "mols": list(a.mols),
                    "cells": [list(c) for c in _asm_cells(world, a)],
                    "organs": [{"kind": o.kind, "name": ORGAN_NAMES.get(o.kind)} for o in org]})
    for sid in sorted(world.systems):
        s = world.systems[sid]
        out.append({"sid": sid, "organs": list(s.organs), "cycle_rank": s.cycle_rank,
                    "shape": "system"})
    return out


def legacy_life_score(world: World) -> float:
    """T71 旧口径"生命度"只读复算（仅对照，禁止参与判定，§6.5）。"""
    score = 0.0
    if world.assemblies:
        score += 1.0
    organs = [o for o in world.organs.values() if o.active]
    score += min(3.0, len(organs) * 0.5)
    if world.systems:
        score += 1.0
    if any(o.kind == "rep" for o in organs):
        score += 1.0
    score += min(2.0, len(world.bonds) * 0.01)
    return round(score, 3)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="T77 涌现机制原型：分子→组装体→器官→生命")
    parser.add_argument("--sample", type=int, default=6000, help="抽样分子数（默认 6000）")
    parser.add_argument("--steps", type=int, default=1200, help="模拟步数（默认 1200）")
    parser.add_argument("--seed", type=int, default=20261119, help="随机种子")
    parser.add_argument("--L", type=int, default=None, help="世界边长（默认按 N 自动）")
    parser.add_argument("--out", type=str, default=None, help="结果 JSON 输出路径")
    parser.add_argument("--params", type=str, default=None, help="参数 JSON 路径")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    P = load_params(args.params)
    P["N"] = args.sample
    P["steps"] = args.steps
    if args.L:
        P["L"] = args.L
    elif args.sample != DEFAULT_PARAMS["N"]:
        # 保持与规范相同的密度 ρ = N·footprint/L²
        P["L"] = max(32, int(round(160 * math.sqrt(args.sample / DEFAULT_PARAMS["N"]))))
    if not args.quiet:
        print(f"[emergence] sample={args.sample} steps={args.steps} L={P['L']} seed={args.seed}",
              flush=True)
    t0 = time.time()
    records = sample_records(args.sample, args.seed)
    if not args.quiet:
        print(f"[emergence] sampled {len(records)} records in {time.time()-t0:.2f}s", flush=True)
    result = run_experiment(records, args.seed, P)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        if not args.quiet:
            print(f"[emergence] wrote {out}", flush=True)
    if args.quiet:
        print(json.dumps({k: result[k] for k in ("tiers", "assembly_rate", "organs",
                                                 "systems", "elapsed_s")},
                         ensure_ascii=False))
    else:
        print(f"[emergence] elapsed={result['elapsed_s']}s "
              f"asm={result['assemblies']} organs={result['organs']} "
              f"systems={result['systems']} tiers={result['tiers']}", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
