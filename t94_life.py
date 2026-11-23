# -*- coding: utf-8 -*-
"""T94-B 完美膜 + 自制造/自修复的动态仿真
=========================================
问题（T94 用户指定）
    在「T94 试验场」默认参数下：
      * 初始温度 T0=200°C → 600 拍指数降温到 T_end=0°C 后平台恒温；
      * 接触反应概率 p_react=1.0（条件满足即反应，不再抽样）；
      * 重力 G=0.2、环境耦合 env_coupling=0.5、cap=36；
      * 热值 heat(C,L,F)=(-1,+1,+2)（ChemLab 口径）。
    验证「完美膜」：膜分子高 D（动素 P/W/L 富集）、低 A、w_self<0（自铺展），
    且 d=1 时 K_A·A_body > K_R·D_m（被主体净吸引）；主体取高 A（O/X/C 富集，A≥2）。
    环境不再是固定攻击浴，而是 T88/T92 群系式的**元素丰度**定义 → 从目录按丰度采样
    环境分子池（富动素 / 富 F/O / 九元素均衡 三种）。

实验世界
    W=160 H=110 硬边界、core_center=(55,80)。三段结构：
      主体 core：BODY_N=24 个 O2（A=3.0, D=0, 重·气），冻结不动（T90/T93 的建模假设）；
                 「主体物质」判定 = A≥2、D=0、不含 P/W/L，且距核心中心 ≤9 格。
      膜/壳：  环带 R=7~12，PK（D=3.0, A=0, w_self=-0.5, 质量 1.5）220 个，
                 对照 OXC 300 个（旧冷壳）；另有 W2（D=2, A=0, w_self=-0.33, 质量 0）对照。
      环境：   R>13.5 采样 300 个分子（T88 式 IPF 丰度配平）。
    膜臂对照：无膜（env 同样从 R>13.5 开始，保证体积占用可比）。

物理口径（与 t94_config 一致）
    * 反应判定温度用 ChemLab 局部温度：
        T_local = (Σ_{2 格内分子} heat + ec·T_env) / (n + ec)，heat=wC·nC+wL·nL+wF·nF
      全局 T_env 只作为 local_T 的耦合项，不再直接用 schedule_T 作为 resolve 的 Tamb。
    * p_react=1.0：每个相邻 2~4 分子组都尝试 resolve（不再抽样、无 ρ_E gate）。
    * 重力：gacc += G·mass，整数部分每拍最多下移 4 格；主体冻结、不受重力。
    * 膜对被主体吸引用 T87 非对称力：F_on_m = K_A·A_body·F(d,r_att_body)
      − K_R·D_m·F(d,r_rep_m)；膜对 D>0 环境分子的斥力同样走非对称力（D=0 只能占格阻挡）。

臂（7 个，全部从 t94_config.DEFAULT_PARAMS 取默认值）
    1 no_membrane_dyn        无膜对照 + 富动素环境（G=0.2）
    2 membrane_PK_dyn        PK 完美膜 + 富动素环境（G=0.2）
    3 membrane_PK_FO         PK 完美膜 + 富 F/O 环境（G=0.2）
    4 oxc_shell_FO           旧 OXC 冷壳 + 富 F/O 环境（G=0.2）
    5 membrane_PK_selfrepair PK 膜（初始只 140 个）+ 内部 P2K4 食物 45 个，验证自修复
    6 membrane_PK_dyn_G0     同臂 2 但 G=0（重力对照）
    7 membrane_W2_bal        轻膜 W2（质量 0）+ 九元素均衡环境（G=0.2）

自修复（设计，非内核改动）
    搜索目录反应得到：O2 + P2K4 --(T≈200°C, complete)--> OK + OK + PK + PK。
    即「主体物质 O2 + 食物 P2K4 → 2 个主体物质 OK + 2 个膜分子 PK」：
    主体物质在反应后仍存在（O2 变成 OK，仍是 A=3,D=0 的主体料），同时分泌出膜分子。
    臂 5 用「初始膜少 + 食物多」观察膜被环境消耗后能否由该路径持续补足。
    该反应是 natural_engine.resolve 的**真实输出**，未改内核；但它要求 O2 与 P2K4 接触，
    反应概率受 T_local 控制，所以只在降温前段有效——文档如实说明。

运行
    python t94_life.py --quick        # 小世界快速验证
    python t94_life.py --ticks 600    # 正式 7 臂（逐臂写 JSON，崩溃安全）
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time

import t94_config as CFG
import t87_env_asym as T87
import t83_env_axes as T83
import natural_engine as E
from t83_env_axes import comp_of
from alchemy import three_su as TS
from alchemy.core.elements import ORDER as ELEM_ORDER

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE, "t94_run.log")
IMGDIR = os.path.join(BASE, "images")

ELEMS = list(ELEM_ORDER)          # ['O','X','C','P','W','L','K','A','F']

# ---- 世界与结构 -----------------------------------------------------------
W0, H0 = 160, 110
CORE_CENTER = (55, 80)
R_BODY = 9.0              # 「主体物质」判定半径（Chebyshev）
R_BODY_JOIN = 6.0         # 新生主体物质并入 body 的半径：必须严格在膜环内缘(7)以内，
                          # 否则主体向外生长会穿入膜带、把物理隔离测试污染成「主体-环境相邻」
R_INTERIOR = 9.0          # 内部反应：质心距核心 ≤9
R_SHELL = 13.0            # 壳体带
R_ENV_MIN = 13.5          # 环境分子初始最小距离（膜环外缘 12 + 1.5 格间隙）
MEM_RING = (7.0, 12.0)    # 膜环带半径
FOOD_RING = (3.6, 6.4)    # 内部食物环带

BODY_FORMULA = "O2"       # A=3.0, D=0, 重·气：高 A 主体料
BODY_N = 24
MEM_FORMULA = "PK"        # A=0, D=3.0, w_self=-0.5：高 D 低 A、自铺展
MEM_N = 220
MEM_W2 = "W2"             # 轻膜对照：D=2, 质量 0
MEM_WA2 = "WA2"           # 轻膜 + 化学兼容：D=2, 质量 0, 与 OK/XA3 均无净反应
OXC_FORMULA = "OXC"       # T93 旧冷壳
OXC_N = 300
FOOD_FORMULA = "XA3"       # 惰性食物：O2+XA3 无净变化；XA3+XA3 → A2 + 2 XA2（A≥2,D=0，可并入主体）
FOOD_N = 30
SELFREP_FOOD = "P2K4"      # 自修复食物：O2 + P2K4 → 2 OK + 2 PK
FOOD_N_SELFREP = 45
ENV_N = 300
SEED = CFG.DEFAULT_PARAMS["seed"]
GRAVITY_MAX_STEPS = 4     # t94_config：每拍最多下移 4 格

# 三种环境：元素丰度（T88/T92 群系式定义）
ENV_ABUND = {
    "dyn": {"P": 0.20, "W": 0.20, "L": 0.12, "O": 0.14, "X": 0.08,
            "C": 0.06, "K": 0.06, "A": 0.06, "F": 0.08},
    "fo":  {"O": 0.28, "F": 0.28, "C": 0.12, "X": 0.10, "L": 0.06,
            "K": 0.06, "A": 0.04, "P": 0.03, "W": 0.03},
    "bal": {e: 1.0 / 9.0 for e in ELEMS},
}
ENV_LABEL = {"dyn": "富动素 P/W/L", "fo": "富 F/O 反应性", "bal": "九元素均衡"}


# ---------------------------------------------------------------- 基础工具
def log(msg, fp=None):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        io.open(LOG_FILE, "a", encoding="utf-8").write(line + "\n")
    except OSError:
        pass


def atomic_json(path, obj):
    tmp = path + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        json.dumps(obj, ensure_ascii=False))
    os.replace(tmp, path)


def build_env_feed(abundance, n_mol=300, natoms_max=8, iters=220, damp=0.5):
    """从目录按元素丰度采样环境分子池（IPF 配平；T88 build_feed 的通用版）。

    abundance: {元素: 目标份额}（会归一化），只从「元素集合 ⊆ support」的
    2~natoms_max 原子目录分子中取，保证环境里每种目标元素都有可投放物种。
    """
    recs = T83.catalog_index()
    S = [e for e in ELEMS if abundance.get(e, 0.0) > 0.0]
    Sset = set(S)
    tot_t = sum(abundance[e] for e in S)
    target = {e: abundance[e] / tot_t for e in S}
    cand = []
    for f, r in recs.items():
        at = r["atoms"]
        if not (2 <= len(at) <= natoms_max):
            continue
        if not set(at) <= Sset:
            continue
        cand.append((f, comp_of(f)))
    if not cand:
        raise SystemExit("no env candidates for %r" % (S,))
    comps = [c for _, c in cand]
    w = [1.0] * len(cand)
    for _ in range(iters):
        cur = {e: 0.0 for e in S}
        for wi, comp in zip(w, comps):
            for e, k in comp.items():
                cur[e] += wi * k
        tot = sum(cur.values())
        if tot <= 0:
            break
        fac = {}
        for e in S:
            want = target[e] * tot
            fac[e] = (want / cur[e]) if cur[e] > 1e-12 else 1.0
        new = []
        for wi, comp in zip(w, comps):
            ni = float(sum(comp.values()))
            mult = 1.0
            for e, k in comp.items():
                mult *= fac[e] ** (k / ni)
            new.append(wi * (mult ** damp))
        s = sum(new)
        if s <= 0:
            break
        w = [x * n_mol / s for x in new]
    ints = [int(math.floor(x)) for x in w]
    rem = n_mol - sum(ints)
    order = sorted(range(len(w)), key=lambda i: -(w[i] - ints[i]))
    for i in order[:max(0, rem)]:
        ints[i] += 1
    while sum(ints) > n_mol:
        i = max(range(len(ints)), key=lambda k: ints[k])
        ints[i] -= 1
    feed = []
    for (f, _), c in zip(cand, ints):
        if c > 0:
            feed.extend([f] * c)
    cur = {e: 0.0 for e in S}
    atoms = 0
    for (f, comp), c in zip(cand, ints):
        for e, k in comp.items():
            cur[e] += c * k
        atoms += c * sum(comp.values())
    tot = sum(cur.values())
    share = {e: round(cur[e] / tot, 4) for e in S} if tot else {}
    meta = {"target_n": n_mol, "n_placed": len(feed), "n_species": len(set(feed)),
            "share": share, "atoms_per_mol": round(atoms / max(1, len(feed)), 2)}
    return feed, meta


# ---------------------------------------------------------------- 判定函数
def body_material(m, types):
    """主体物质：A≥2 且 D=0（不含 P/W/L），即 O/X/C(+散素) 富集的高 A 分子。"""
    t = types[m["f"]]
    return t["A"] >= 1.999 and t["R"] == 0.0


def formula_is_body(f, types):
    t = types[f]
    return t["A"] >= 1.999 and t["R"] == 0.0


# ---------------------------------------------------------------- 世界
class LifeWorld(T87.AsymWorld):
    """T94 世界：冻结主体 + 环带膜 + 丰度采样的环境池。"""

    def __init__(self, W=W0, H=H0, seed=SEED, env_feed=None, env_name="dyn",
                 membrane=MEM_FORMULA, n_mem=MEM_N, body_n=BODY_N,
                 food_formula=FOOD_FORMULA, food_n=FOOD_N,
                 grav=0.2, ticks_total=600, brown_p=0.05,
                 center=CORE_CENTER, body_formula=BODY_FORMULA, seed_rng=None):
        recs = T83.catalog_index()
        super().__init__(W, H, seed, [], recs,
                         cap=CFG.DEFAULT_PARAMS["cap"],
                         p_react=CFG.DEFAULT_PARAMS["p_react"],
                         force_r=2, brown_p=brown_p,
                         t0=CFG.DEFAULT_PARAMS["T0"],
                         t_end=CFG.DEFAULT_PARAMS["T_end"],
                         cool_ticks=int(CFG.DEFAULT_PARAMS["cool_ticks"]))
        self.env_name = env_name
        self.env_feed = list(env_feed or [])
        self.membrane = membrane
        self.n_mem = int(n_mem)
        self.body_n_target = int(body_n)
        self.body_formula = body_formula
        self.food_formula = food_formula
        self.food_n = int(food_n)
        self.grav = float(grav)
        self.ticks_total = int(ticks_total)
        self.center = tuple(center)
        self.cool_ticks = int(CFG.DEFAULT_PARAMS["cool_ticks"])
        self.ec = float(CFG.DEFAULT_PARAMS["env_coupling"])

        # 角色 / 血统
        self.body_ids = set()
        self.body_set = set()          # 主体血统：初始 body + 在主体区新生的主体物质
        self.membrane_ids = set()
        self.food_ids = set()
        self.env_ids = set()
        self.env_lineage = set()
        self.food_lineage = set()
        self._comp = {}

        # 计数
        self.c_contacts_env_body = 0
        self.c_contacts_env_mem = 0
        self.c_internal_react = 0
        self.c_shell_react = 0
        self.c_env_react = 0
        self.c_core_env_react = 0
        self.c_mem_env_react = 0
        self.c_body_food_react = 0
        self.c_repair_react = 0
        self.birth_mem = 0
        self.death_mem = 0
        self.body_killed = 0
        self.death_body = 0
        self.body_atoms_lost_mem = 0
        self.body_atoms_lost_env = 0
        self.body_atoms_lost_food = 0
        self.body_atoms_lost_other = 0
        self.body_atoms_gained = 0
        self.react_localT_sum = 0.0
        self.react_localT_n = 0
        self._res_cache = {}
        self._localT_cache = {}
        self._mem_pred = formula_is_body  # placeholder

        self._place_all()
        self.body_n0 = len(self.body_set)
        self.body_atoms0 = sum(self.types[self.mols[i]["f"]]["natoms"]
                               for i in self.body_set)
        self.membrane_n0 = len(self.membrane_ids)
        self.food_n0 = len(self.food_ids)
        self.env_n0 = len(self.env_ids)
        self.elements0 = self.elements()

    # -------------------------------------------------------------- 放置
    def _comp_of(self, f):
        c = self._comp.get(f)
        if c is None:
            c = comp_of(f)
            self._comp[f] = c
        return c

    def _place_cells(self, formula, cells, role):
        mid = self.add_mol(formula, cells[0][0], cells[0][1], cells=cells)
        if mid is None:
            return None
        if role == "body":
            self.body_ids.add(mid)
        elif role == "membrane":
            self.membrane_ids.add(mid)
        elif role == "food":
            self.food_ids.add(mid)
        elif role == "env":
            self.env_ids.add(mid)
        return mid

    def _place_body(self):
        cr, cc = self.center
        offs = [(dr, dc) for dr in range(-3, 4) for dc in range(-3, 4)]
        offs.sort(key=lambda x: (x[0] * x[0] + x[1] * x[1],
                                 abs(x[0]) + abs(x[1]), x[0], x[1]))
        placed = 0
        for dr, dc in offs:
            if placed >= self.body_n_target:
                break
            r, c = cr + dr, cc + dc
            if not (0 <= r < self.H and 0 <= c < self.W):
                continue
            if (r, c) in self.cell:
                continue
            mid = self._place_cells(self.body_formula, [(r, c)], "body")
            if mid is not None:
                placed += 1
        self._body_placed = placed

    def _place_ring(self, formula, n, ring, role, tries_factor=60):
        cr, cc = self.center
        rin, rout = ring
        placed = 0
        tries = max(200, n * tries_factor)
        for _ in range(tries):
            if placed >= n:
                break
            ang = self.rng.random() * 2 * math.pi
            rad = rin + (rout - rin) * (self.rng.random() ** 0.5)
            r = int(round(cr + rad * math.sin(ang)))
            c = int(round(cc + rad * math.cos(ang)))
            if not (0 <= r < self.H and 0 <= c < self.W):
                continue
            if (r, c) in self.cell:
                continue
            if self._place_cells(formula, [(r, c)], role) is not None:
                placed += 1
        return placed

    def _place_env(self):
        placed = 0
        for f in self.env_feed:
            if placed >= len(self.env_feed):
                break
            done = False
            for _ in range(40):
                r = self.rng.randrange(self.H)
                c = self.rng.randrange(self.W)
                d = math.hypot(r - self.center[0], c - self.center[1])
                if d < R_ENV_MIN:
                    continue
                cells = self._free_footprint(r, c, f)
                if not cells:
                    continue
                if self._place_cells(f, cells, "env") is not None:
                    placed += 1
                    done = True
                    break
            if not done:
                continue
        self._env_placed = placed

    def _place_all(self):
        self._place_body()
        self._place_ring(self.food_formula, self.food_n, FOOD_RING, "food")
        if self.membrane:
            self._place_ring(self.membrane, self.n_mem, MEM_RING, "membrane")
        self._place_env()
        self.env_lineage = set(self.env_ids)
        self.food_lineage = set(self.food_ids)
        self.body_set = set(self.body_ids)

    def _find_footprint(self, center, formula, reserved):
        """产物落位：在质心 ±10 格内取**离质心最近**的空 footprint。

        内核 T85 的版本从搜索框左上角开始扫描，会把产物丢到 8~10 格之外
        （T93 记录过的「产物瞬移」）；T94 认为反应产物应就地生成，
        否则「主体生长 / 膜自修复」的空间位置会被系统性高估。
        """
        self.ensure_type(formula)
        shp = self.types[formula]["shape"]
        r0, r1 = max(0, center[0] - 10), min(self.H, center[0] + 11)
        c0, c1 = max(0, center[1] - 10), min(self.W, center[1] + 11)
        cands = []
        for rr in range(r0, r1):
            for cc in range(c0, c1):
                cells = [(rr + dr, cc + dc) for dr, dc in shp]
                if not all(0 <= x < self.H and 0 <= y < self.W
                           for x, y in cells):
                    continue
                if any((x, y) in self.cell or (x, y) in reserved
                       for x, y in cells):
                    continue
                d2 = (rr - center[0]) ** 2 + (cc - center[1]) ** 2
                cands.append((d2, rr, cc, cells))
        if not cands:
            return None
        cands.sort(key=lambda x: (x[0], x[1], x[2]))
        return cands[0][3]

    def _spawn(self, mds, center, free_ids):
        saved = []
        for mid in free_ids:
            for (r, c) in self.mols[mid]["cells"]:
                if self.cell.get((r, c)) == mid:
                    saved.append(((r, c), self.cell.pop((r, c))))
        try:
            reserved = []
            placed = []
            for md in mds:
                cells = self._find_footprint(center, md["formula"], reserved)
                if cells is None:
                    return False
                reserved.extend(cells)
                placed.append((md, cells))
        finally:
            for (r, c), v in saved:
                self.cell[(r, c)] = v
        return placed

    # -------------------------------------------------------------- 温度
    def ambient_T(self, t):
        return CFG.schedule_T(float(t), T0=CFG.DEFAULT_PARAMS["T0"],
                              T_end=CFG.DEFAULT_PARAMS["T_end"],
                              cool_ticks=self.cool_ticks, plateau=True)

    def _heat_of_formula(self, f):
        return CFG.heat_of(self._comp_of(f))

    def _local_T(self, group):
        """ChemLab 局部温度：组内 + 周围 2 格内分子的 heat 与环境耦合。"""
        r0 = c0 = 0
        nc = 0
        for j in group:
            m = self.mols[j]
            r0 += m["r"]
            c0 += m["c"]
            nc += 1
        r0 //= nc
        c0 //= nc
        heats = []
        for rr in range(max(0, r0 - 2), min(self.H, r0 + 3)):
            for cc in range(max(0, c0 - 2), min(self.W, c0 + 3)):
                mid = self.cell.get((rr, cc))
                if mid is None:
                    continue
                heats.append(self._heat_of_formula(self.mols[mid]["f"]))
        if not heats:
            return self.Tamb
        return CFG.local_T(heats, self.Tamb, self.ec)

    # -------------------------------------------------------------- 反应
    def _resolve_cached(self, group):
        key = (tuple(sorted(self.mols[j]["f"] for j in group)),
               int(round(self._local_T(group))))
        res = self._res_cache.get(key)
        if res is None:
            mds = [self._md(self.mols[j]["f"]) for j in sorted(
                group, key=lambda j: self.mols[j]["f"])]
            try:
                res = E.resolve(mds, float(key[1]))
            except Exception:
                res = {"type": "none", "products": None, "state": [],
                       "stages": []}
            self._res_cache[key] = res
        return res, float(key[1])

    def _role_counts(self, group):
        body = mem = food = env = other = 0
        for j in group:
            m = self.mols[j]
            f = m["f"]
            if j in self.body_set:
                body += 1
            elif j in self.env_lineage:
                env += 1
            elif self.membrane and f == self.membrane:
                mem += 1
            elif j in self.food_lineage:
                food += 1
            elif body_material(m, self.types):
                body += 1
            else:
                other += 1
        return body, mem, food, env, other

    def _try_react_group(self, group):
        formulas = [self.mols[j]["f"] for j in group]
        atoms = sum(self.types[f]["natoms"] for f in formulas)
        if atoms > self.cap:
            self.n_react_fail += 1
            return False
        res, Tloc = self._resolve_cached(group)
        typ = res["type"]
        self.react_types[typ] = self.react_types.get(typ, 0) + 1
        self.react_localT_sum += Tloc
        self.react_localT_n += 1
        prods = res.get("products")
        states = res.get("state") or []
        if typ == "none":
            if res.get("stages"):
                new = [s for s in states
                       if s["formula"] not in formulas or len(states) > len(formulas)]
                if len(new) > len(formulas):
                    self.n_decomp += 1
                    return self._apply_group(new, group, formulas)
            self.n_none += 1
            return False
        if typ == "incomplete":
            self.n_incomplete += 1
        else:
            self.n_complete += 1
        if not prods:
            self.n_react_fail += 1
            return False
        if sorted(p["formula"] for p in prods) == sorted(formulas):
            return False
        return self._apply_group(prods, group, formulas)

    def _apply_group(self, prods, group, formulas):
        cells_all = []
        for j in group:
            cells_all.extend(self.mols[j]["cells"])
        cr = sum(r for r, c in cells_all) // len(cells_all)
        cc = sum(c for r, c in cells_all) // len(cells_all)
        d_core = math.hypot(cr - self.center[0], cc - self.center[1])
        body_n, mem_n, food_n, env_n, other_n = self._role_counts(group)
        pre_n = len(self.mols)
        placed = self._spawn(prods, (cr, cc), set(group))
        if not placed:
            self.n_react_fail += 1
            return False
        # 反应前后角色变化
        new_f = [md["formula"] for md, _ in placed]
        n_new_mem = sum(1 for f in new_f if self.membrane and f == self.membrane)
        self.birth_mem += n_new_mem
        self.death_mem += mem_n
        killed_body = 0
        b_atoms = 0
        for j in group:
            if j in self.body_set:
                killed_body += 1
                b_atoms += self.types[self.mols[j]["f"]]["natoms"]
        self.body_killed += killed_body
        if b_atoms:
            if env_n:
                self.body_atoms_lost_env += b_atoms
            elif mem_n:
                self.body_atoms_lost_mem += b_atoms
            elif food_n:
                self.body_atoms_lost_food += b_atoms
            else:
                self.body_atoms_lost_other += b_atoms
        # 反应类型统计
        if body_n and env_n:
            self.c_core_env_react += 1
        if mem_n and env_n:
            self.c_mem_env_react += 1
        if body_n and food_n:
            self.c_body_food_react += 1
        if body_n and n_new_mem:
            self.c_repair_react += 1
        if d_core <= R_INTERIOR:
            self.c_internal_react += 1
        elif d_core > R_SHELL:
            self.c_env_react += 1
        else:
            self.c_shell_react += 1
        # 模板/模式/条带统计（沿用 T86 口径）
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                si = self.types[formulas[a]]["tiers"]["state"]
                sj = self.types[formulas[b]]["tiers"]["state"]
                key = self._mode_key(si, sj)
                self.mode_counts[key] = self.mode_counts.get(key, 0) + 1
        band = 0 if cr > 2 * self.H // 3 else (2 if cr < self.H // 3 else 1)
        self.band_react[band] += 1
        for j in group:
            self._kill(j)
        for md, cells in placed:
            self.md_cache[md["formula"]] = md
            self._add_with(md, cells)
        # 血统：env / food 的后代
        new_ids = set(range(pre_n, len(self.mols)))
        if env_n:
            self.env_lineage |= new_ids
        if food_n:
            self.food_lineage |= new_ids
        # 新生主体物质（主体区、非环境后代）并入主体血统
        for (md, cells), mid in zip(placed, sorted(new_ids)):
            if mid in self.env_lineage:
                continue
            if not body_material(self.mols[mid], self.types):
                continue
            rr = sum(r for r, c in cells) / len(cells)
            cc = sum(c for r, c in cells) / len(cells)
            if math.hypot(rr - self.center[0], cc - self.center[1]) <= R_BODY_JOIN:
                self.body_set.add(mid)
                if body_n == 0 and env_n == 0:
                    self.body_atoms_gained += self.types[self.mols[mid]["f"]]["natoms"]
            elif os.environ.get("T94_DEBUG_JOIN"):
                print("JOINOUT", mid, self.mols[mid]["f"], rr, cc,
                      "d=%.1f" % math.hypot(rr - self.center[0], cc - self.center[1]))
        # 新膜分子也记入膜 id（用于后续接触/覆盖统计）
        for mid in new_ids:
            if self.membrane and self.mols[mid]["f"] == self.membrane:
                self.membrane_ids.add(mid)
        self.n_react += 1
        return True

    def react_phase(self):
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        handled = set()
        for i in ids:
            if i >= len(self.mols) or self.mols[i]["dead"] or i in handled:
                continue
            m = self.mols[i]
            group = [i]
            handled.add(i)
            atoms = self.types[m["f"]]["natoms"]
            cands = []
            for (r, c) in m["cells"]:
                for dr, dc in T83.DIRS[::2]:  # 4 邻接
                    nb = self.cell.get((r + dr, c + dc))
                    if nb is None or nb == i or nb in handled:
                        continue
                    if self.mols[nb]["dead"] or nb in cands:
                        continue
                    cands.append(nb)
            for nb in cands:
                if len(group) >= 4:
                    break
                nat = self.types[self.mols[nb]["f"]]["natoms"]
                if atoms + nat > self.cap:
                    continue
                group.append(nb)
                handled.add(nb)
                atoms += nat
            if len(group) >= 2:
                self._try_react_group(group)

    # -------------------------------------------------------------- 接触
    def _tick_contacts(self):
        body_cells = set()
        mem_cells = set()
        for mid, m in enumerate(self.mols):
            if m["dead"]:
                continue
            if mid in self.body_set:
                for (r, c) in m["cells"]:
                    body_cells.add((r, c))
            elif self.membrane and m["f"] == self.membrane:
                for (r, c) in m["cells"]:
                    mem_cells.add((r, c))
        for mid in self.env_lineage:
            if mid >= len(self.mols):
                continue
            m = self.mols[mid]
            if m["dead"]:
                continue
            for (r, c) in m["cells"]:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        if (r + dr, c + dc) in body_cells:
                            self.c_contacts_env_body += 1
                        if (r + dr, c + dc) in mem_cells:
                            self.c_contacts_env_mem += 1

    # -------------------------------------------------------------- 一拍
    def step(self):
        self.Tamb = self.ambient_T(self.t)
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        for mid in ids:
            if self.mols[mid]["dead"] or mid in self.body_set:
                continue
            m = self.mols[mid]
            t = self.types[m["f"]]
            st = t["tiers"]["state"]
            gacc = m.get("gacc", 0.0) + self.grav * t["mass"]
            gsteps = int(gacc)
            m["gacc"] = gacc - gsteps
            for _ in range(min(gsteps, GRAVITY_MAX_STEPS)):
                if not self._gravity_step(mid):
                    break
            sx, sy = self.force_on(mid)
            norm = math.hypot(sx, sy)
            if norm > 1e-9:
                ang = math.atan2(sy, sx)
                k = int(round(ang / (math.pi / 4.0))) % 8
                dr, dc = T83.DIRS[k]
                p = T83.STATE_MOB[st] * min(1.0, 0.20 + 0.80 * norm)
                if self.rng.random() < p:
                    if self._try_move(mid, dr, dc):
                        self.n_moves += 1
                        continue
            if self.rng.random() < self.brown_p:
                dr, dc = self.rng.choice(T83.DIRS)
                if self._try_move(mid, dr, dc):
                    self.n_moves += 1
                    self.n_brown += 1
        self._tick_contacts()
        self.react_phase()
        self.rebuild_locks()

    # -------------------------------------------------------------- 度量
    def _live(self):
        return [m for m in self.mols if not m["dead"]]

    def _dist_core(self, m):
        return math.hypot(m["r"] - self.center[0], m["c"] - self.center[1])

    def _body_mats(self):
        return [m for m in self._live() if m["id"] in self.body_set]

    def _membrane_mols(self):
        if not self.membrane:
            return []
        return [m for m in self._live() if m["f"] == self.membrane]

    def _angular_coverage(self, mem, rmin=3.0, rmax=15.0, nbins=36):
        if not mem:
            return 0.0
        hit = set()
        for m in mem:
            d = self._dist_core(m)
            if not (rmin <= d <= rmax):
                continue
            dr = m["r"] - self.center[0]
            dc = m["c"] - self.center[1]
            ang = math.atan2(dr, dc)                 # -pi..pi
            b = int((ang + math.pi) / (2 * math.pi) * nbins) % nbins
            hit.add(b)
        return len(hit) / float(nbins)

    def _attached_ratio(self, mem, body):
        if not mem:
            return 0.0
        near = set()
        for m in body:
            for (r, c) in m["cells"]:
                for dr in (-2, -1, 0, 1, 2):
                    for dc in (-2, -1, 0, 1, 2):
                        near.add((r + dr, c + dc))
        cnt = sum(1 for m in mem if any(cell in near for cell in m["cells"]))
        return cnt / float(len(mem))

    def measure(self, t, every=10):
        live = self._live()
        body = self._body_mats()
        mem = self._membrane_mols()
        shell = [m for m in live if self.membrane and m["f"] == self.membrane
                 and 3.0 <= self._dist_core(m) <= 15.0]
        food = [m for m in live
                if m["f"] in (self.food_formula,)]
        env = [m for m in live if m["id"] in self.env_lineage]
        by_el = {}
        body_atoms = 0
        for m in body:
            body_atoms += self.types[m["f"]]["natoms"]
            for e, k in self._comp_of(m["f"]).items():
                by_el[e] = by_el.get(e, 0) + k
        rec = {
            "t": t,
            "T_env": round(self.Tamb, 2),
            "T_react_mean": round(self.react_localT_sum / self.react_localT_n, 2)
            if self.react_localT_n else round(self.Tamb, 2),
            "n": len(live),
            "cells_used": self.n_cells_used,
            "body_n": len(body),
            "body_atoms": body_atoms,
            "body_atoms_lost_mem": self.body_atoms_lost_mem,
            "body_atoms_lost_env": self.body_atoms_lost_env,
            "body_atoms_lost_food": self.body_atoms_lost_food,
            "body_atoms_gained": self.body_atoms_gained,
            "body_by_element": by_el,
            "body_r": round(max([self._dist_core(m) for m in body], default=0.0), 2),
            "membrane_n": len(mem),
            "membrane_ring_n": len(shell),
            "membrane_attached": round(self._attached_ratio(mem, body), 4),
            "coverage_ang": round(self._angular_coverage(mem), 4),
            "food_n": len(food),
            "env_n": len(env),
            "contacts_env_body_cum": self.c_contacts_env_body,
            "contacts_env_mem_cum": self.c_contacts_env_mem,
            "core_env_react_cum": self.c_core_env_react,
            "mem_env_react_cum": self.c_mem_env_react,
            "body_food_react_cum": self.c_body_food_react,
            "repair_react_cum": self.c_repair_react,
            "birth_mem_cum": self.birth_mem,
            "death_mem_cum": self.death_mem,
            "internal_react_cum": self.c_internal_react,
            "shell_react_cum": self.c_shell_react,
            "env_react_cum": self.c_env_react,
            "n_react_total": self.n_react,
            "n_complete": self.n_complete,
            "n_incomplete": self.n_incomplete,
            "n_none": self.n_none,
            "n_decomp": self.n_decomp,
            "n_react_fail": self.n_react_fail,
            "n_moves": self.n_moves,
            "n_blocked": self.n_blocked,
            "react_types": dict(self.react_types),
            "locks": sum(len(v) for v in self.locks.values()),
            "res_cache": len(self._res_cache),
        }
        return rec

    def final_state(self):
        live = self._live()
        return {
            "mols": [[m["r"], m["c"], m["f"],
                      ("body" if m["id"] in self.body_set else
                       "membrane" if (self.membrane and m["f"] == self.membrane) else
                       "food" if m["id"] in self.food_lineage else
                       "env" if m["id"] in self.env_lineage else "other")]
                     for m in live],
            "center": list(self.center),
            "W": self.W, "H": self.H,
        }


# ---------------------------------------------------------------- 臂
ARMS = [
    {"name": "no_membrane_dyn",
     "note": "无膜对照 + 富动素环境（G=0.2）",
     "membrane": None, "n_mem": 0, "env": "dyn", "grav": 0.2, "food_n": FOOD_N},
    {"name": "membrane_PK_dyn",
     "note": "PK 完美膜（D=3,A=0,w_self=-0.5）+ 富动素环境（G=0.2）",
     "membrane": "PK", "n_mem": MEM_N, "env": "dyn", "grav": 0.2, "food_n": FOOD_N},
    {"name": "membrane_PK_FO",
     "note": "PK 完美膜 + 富 F/O 反应性环境（G=0.2）",
     "membrane": "PK", "n_mem": MEM_N, "env": "fo", "grav": 0.2, "food_n": FOOD_N},
    {"name": "oxc_shell_FO",
     "note": "旧 OXC 冷壳（T93）+ 富 F/O 环境（G=0.2）",
     "membrane": "OXC", "n_mem": OXC_N, "env": "fo", "grav": 0.2, "food_n": FOOD_N},
    {"name": "membrane_PK_selfrepair",
     "note": "自修复：PK 膜只放 140 个 + 内部食物 P2K4 45 个（G=0.2, 富动素）",
     "membrane": "PK", "n_mem": 140, "env": "dyn", "grav": 0.2,
     "food": SELFREP_FOOD, "food_n": FOOD_N_SELFREP},
    {"name": "membrane_PK_dyn_G0",
     "note": "PK 完美膜 + 富动素环境，G=0（重力对照）",
     "membrane": "PK", "n_mem": MEM_N, "env": "dyn", "grav": 0.0, "food_n": FOOD_N},
    {"name": "membrane_W2_bal",
     "note": "轻膜 W2（D=2, 质量 0）+ 九元素均衡环境（G=0.2）",
     "membrane": "W2", "n_mem": MEM_N, "env": "bal", "grav": 0.2, "food_n": FOOD_N},
    {"name": "membrane_W2_dyn",
     "note": "轻膜 W2（D=2, 质量 0）+ 富动素环境（G=0.2，与 PK 同环境对照）",
     "membrane": "W2", "n_mem": MEM_N, "env": "dyn", "grav": 0.2, "food_n": FOOD_N},
    {"name": "membrane_WA2_OKbody_dyn",
     "note": "完美膜组合：轻膜 WA2（D=2,质量 0, 与 OK/XA3 无净反应）+ 化学惰性主体 OK + 惰性食物 XA3",
     "body": "OK", "membrane": "WA2", "n_mem": MEM_N, "env": "dyn",
     "grav": 0.2, "food_n": FOOD_N},
    {"name": "membrane_PK_OKbody_dyn",
     "note": "PK 完美膜 + 化学惰性主体 OK（A=3,D=0；OK+PK 无净反应）+ 富动素环境（G=0.2）",
     "body": "OK", "membrane": "PK", "n_mem": MEM_N, "env": "dyn",
     "grav": 0.2, "food_n": FOOD_N},
]


def arm_params(arm, quick=False, ticks_override=None):
    p = dict(arm)
    p.setdefault("body", BODY_FORMULA)
    p.setdefault("food", FOOD_FORMULA)
    ticks = 600 if not quick else 120
    if ticks_override:
        ticks = int(ticks_override)
    if quick:
        p["W"], p["H"] = 120, 80
        p["center"] = (40, 60)
        p["body_n"] = 12
        p["n_mem"] = max(20, int(p["n_mem"] * 0.5))
        p["food_n"] = max(4, int(p["food_n"] * 0.4))
        p["env_n"] = 120
        ticks = min(ticks, 120)
    else:
        p["W"], p["H"] = W0, H0
        p["center"] = CORE_CENTER
        p["body_n"] = BODY_N
        p["env_n"] = ENV_N
    p["ticks"] = ticks
    return p


# ---------------------------------------------------------------- 汇总
def summarize(w, series, cfg, runtime_s):
    s = series[-1] if series else {}
    rec0 = series[0] if series else {}
    return {
        "name": cfg["name"], "note": cfg["note"],
        "env": cfg["env"], "env_label": ENV_LABEL.get(cfg["env"], cfg["env"]),
        "membrane": cfg["membrane"], "n_mem": cfg["n_mem"],
        "grav": cfg["grav"], "ticks": cfg["ticks"],
        "W": w.W, "H": w.H, "seed": SEED,
        "runtime_s": round(runtime_s, 2),
        "n0": rec0.get("n"), "n_final": s.get("n"),
        "body_n0": w.body_n0, "body_n_final": s.get("body_n"),
        "body_formula": w.body_formula,
        "body_atoms0": w.body_atoms0,
        "body_atoms_final": s.get("body_atoms"),
        "body_atoms_lost_mem": s.get("body_atoms_lost_mem"),
        "body_atoms_lost_env": s.get("body_atoms_lost_env"),
        "body_atoms_lost_food": s.get("body_atoms_lost_food"),
        "body_atoms_gained": s.get("body_atoms_gained"),
        "body_retention": round(s.get("body_n", 0) / max(1, w.body_n0), 4),
        "body_by_element_final": s.get("body_by_element"),
        "body_killed_total": w.body_killed,
        "membrane_n0": w.membrane_n0, "membrane_n_final": s.get("membrane_n"),
        "membrane_ring_final": s.get("membrane_ring_n"),
        "membrane_retention": round(s.get("membrane_n", 0) / max(1, w.membrane_n0), 4)
        if w.membrane_n0 else None,
        "coverage_ang_final": s.get("coverage_ang"),
        "membrane_attached_final": s.get("membrane_attached"),
        "food_n0": w.food_n0, "food_n_final": s.get("food_n"),
        "env_n0": w.env_n0, "env_n_final": s.get("env_n"),
        "contacts_env_body_total": s.get("contacts_env_body_cum"),
        "contacts_env_mem_total": s.get("contacts_env_mem_cum"),
        "core_env_react_total": s.get("core_env_react_cum"),
        "mem_env_react_total": s.get("mem_env_react_cum"),
        "repair_react_total": s.get("repair_react_cum"),
        "birth_mem_total": s.get("birth_mem_cum"),
        "death_mem_total": s.get("death_mem_cum"),
        "internal_react_total": s.get("internal_react_cum"),
        "shell_react_total": s.get("shell_react_cum"),
        "env_react_total": s.get("env_react_cum"),
        "n_react_total": s.get("n_react_total"),
        "n_complete": s.get("n_complete"),
        "n_incomplete": s.get("n_incomplete"),
        "n_none": s.get("n_none"),
        "n_decomp": s.get("n_decomp"),
        "n_react_fail": s.get("n_react_fail"),
        "n_moves": s.get("n_moves"), "n_blocked": s.get("n_blocked"),
        "react_types": s.get("react_types"),
        "T_env_final": s.get("T_env"),
        "T_react_mean": s.get("T_react_mean"),
        "body_series": [[r["t"], r["body_n"]] for r in series],
        "membrane_series": [[r["t"], r["membrane_n"]] for r in series],
        "coverage_series": [[r["t"], r["coverage_ang"]] for r in series],
        "contacts_body_series": [[r["t"], r["contacts_env_body_cum"]] for r in series],
        "birth_series": [[r["t"], r["birth_mem_cum"]] for r in series],
        "death_series": [[r["t"], r["death_mem_cum"]] for r in series],
        "elements0": w.elements0,
        "elements_final": w.elements(),
        "conservation_ok": w.elements0 == w.elements(),
    }


def run_arm(arm, quick=False, outdir=BASE, seed=SEED, ticks_override=None,
            measure_every=10, env_cache=None):
    p = arm_params(arm, quick=quick, ticks_override=ticks_override)
    t0 = time.time()
    env_cache = env_cache if env_cache is not None else {}
    env_name = p["env"]
    if env_name not in env_cache:
        feed, meta = build_env_feed(ENV_ABUND[env_name], n_mol=p["env_n"])
        env_cache[env_name] = (feed, meta)
    env_feed, env_meta = env_cache[env_name]
    w = LifeWorld(W=p["W"], H=p["H"], seed=seed, env_feed=env_feed,
                  env_name=env_name, membrane=p["membrane"], n_mem=p["n_mem"],
                  body_n=p["body_n"], food_formula=p["food"],
                  food_n=p["food_n"], grav=p["grav"], ticks_total=p["ticks"],
                  center=p["center"], body_formula=p["body"])
    w.t = 0
    w.Tamb = w.ambient_T(0)
    series = [w.measure(0)]
    log("[%s] 放置: body %d, membrane %d, food %d, env %d | env=%s | G=%.2f | ticks=%d"
        % (p["name"], w.body_n0, w.membrane_n0, w.food_n0, w.env_n0,
           env_name, p["grav"], p["ticks"]))
    for t in range(1, p["ticks"] + 1):
        w.t = t
        w.step()
        if t % measure_every == 0 or t == p["ticks"]:
            series.append(w.measure(t))
            r = series[-1]
            log("  [%s] t=%3d T=%6.1f body=%2d mem=%3d cov=%.2f envC=%d coreEnvR=%d "
                "intR=%d envR=%d"
                % (p["name"], t, r["T_env"], r["body_n"], r["membrane_n"],
                   r["coverage_ang"], r["contacts_env_body_cum"],
                   r["core_env_react_cum"], r["internal_react_cum"],
                   r["env_react_cum"]))
    el1 = w.elements()
    summary = summarize(w, series, p, time.time() - t0)
    summary["env_feed_meta"] = env_meta
    summary["config"] = {
        "engine": "T94 试验场（t94_config 默认参数）",
        "T0": CFG.DEFAULT_PARAMS["T0"], "T_end": CFG.DEFAULT_PARAMS["T_end"],
        "cool_ticks": CFG.DEFAULT_PARAMS["cool_ticks"],
        "p_react": CFG.DEFAULT_PARAMS["p_react"],
        "gravity_G": p["grav"], "env_coupling": CFG.DEFAULT_PARAMS["env_coupling"],
        "cap": CFG.DEFAULT_PARAMS["cap"],
        "heat_w": CFG.DEFAULT_PARAMS["heat_w"],
        "structure": {"body_formula": p["body"], "body_n": p["body_n"],
                      "food_formula": p["food"], "food_n": p["food_n"],
                      "membrane": p["membrane"], "n_mem": p["n_mem"],
                      "mem_ring": MEM_RING, "food_ring": FOOD_RING,
                      "env_name": env_name, "env_label": ENV_LABEL[env_name],
                      "env_n": p["env_n"], "R_env_min": R_ENV_MIN},
        "conservation_ok": el1 == w.elements0,
    }
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "t94_%s.json" % p["name"])
    atomic_json(out, {"summary": summary, "series": series,
                      "final_state": w.final_state()})
    log("[%s] 完成 %.1fs -> %s" % (p["name"], time.time() - t0, out))
    return summary, series, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--arms", default="")
    ap.add_argument("--ticks", type=int, default=0)
    ap.add_argument("--outdir", default=BASE)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--measure-every", type=int, default=10)
    a = ap.parse_args(argv)
    names = [x for x in a.arms.split(",") if x.strip()] if a.arms else None
    arms = [x for x in ARMS if (not names or x["name"] in names)]
    t0 = time.time()
    log("=" * 70)
    log("T94-B 完美膜 + 自制造自修复 | 臂=%d | quick=%s | %s"
        % (len(arms), a.quick, CFG.describe()))
    main_path = os.path.join(a.outdir, "t94_life.json")
    all_sum, all_series = [], {}
    env_cache = {}
    for arm in arms:
        try:
            summary, series, out = run_arm(
                arm, quick=a.quick, outdir=a.outdir, seed=a.seed,
                ticks_override=a.ticks or None,
                measure_every=a.measure_every, env_cache=env_cache)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            log("[%s] 失败: %s" % (arm["name"], ex))
            continue
        all_sum.append(summary)
        all_series[arm["name"]] = series
        atomic_json(main_path, {
            "config": {
                "task": "T94-B 完美膜 + 自制造自修复",
                "params": CFG.DEFAULT_PARAMS,
                "world": {"W0": W0, "H0": H0, "CORE_CENTER": CORE_CENTER},
                "structure": {"body": BODY_FORMULA, "membrane": MEM_FORMULA,
                              "membrane_light": MEM_W2, "oxc": OXC_FORMULA,
                              "food": FOOD_FORMULA,
                              "mem_ring": MEM_RING, "food_ring": FOOD_RING,
                              "R_env_min": R_ENV_MIN},
                "env_abundance": ENV_ABUND,
                "env_label": ENV_LABEL,
                "seed": a.seed, "quick": a.quick,
            },
            "arms": all_sum,
            "series": all_series,
            "runtime_s": round(time.time() - t0, 2),
        })
    log("全部完成: %d 臂, %.1fs -> %s"
        % (len(all_sum), time.time() - t0, main_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
