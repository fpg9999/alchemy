# -*- coding: utf-8 -*-
"""t55_kinetic_env.py —— T55：2D 粒子环境中的自然环境反应实验

实验设定（详细推导见 docs/T55_KINETIC_ENV.md）：
* 环境：正方形平面 L×L（反射边界），初始温度 1000°，每分钟 -1°，最低 0°。
* 投料：两批"元素单质"（冰-冰 C2、晶-晶 X2、秩-秩 O2）：
    A 批：元素单质 各 1500 个（共 4500 个分子 / 9000 原子）
    B 批：聚素单质 各 1500 个（共 4500 个分子 / 9000 原子）
  合计 9000 个双原子分子 / 18000 原子。
* 运动：每个分子以极高初速度弹道运动 + 镜面反射；初速度按"前 500 分钟内
  每个单质至少完成 500 次角-对角穿越"设计（对称目标 750 次，留统计余量）。
* 碰撞：稀薄气体动理学蒙特卡洛（DSMC 近似）：
    平均自由程 λ = L² / (2√2 N r)，每个分子碰撞率 ν = v/λ；
    每分钟按泊松采样碰撞事件，再按速度加权选分子、在空间网格邻域选伙伴。
* 衰减：每次分子-分子碰撞后，双方速率 × (1-ε)，ε=0.2%（"衰减一点点"）。
* 化学：每次碰撞调用 natural_engine.resolve(接触集合, T)：
    完全反应 -> pot_v4（规则 1~11）F；不稳定中间体自分解优先；再判不完全反应
    （t28 v2 + 规则 1~11）；都不满足则弹性碰撞。产物继承质量加权平均速度。
* 对照组：关闭化学反应（只做弹性碰撞 + 衰减），验证 500 次穿越要求。

输出：
  t55_kinetic_result.json   主实验（时间序列 / 终态组成 / 快照 / 事件样本 / 统计）
  t55_control_no_chem.json  无化学对照组

用法：
  python t55_kinetic_env.py --quick          # 冒烟
  python t55_kinetic_env.py                  # 主实验（1000 分钟）
  python t55_kinetic_env.py --control        # 对照组（500 分钟）
"""
import argparse
import json
import math
import random
import sys
import time
from bisect import bisect
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import natural_engine as E
import pot_all as P

# ------------------------------------------------------------------ 参数
L = 10000.0                 # 正方形边长（单位）
DIAG = math.sqrt(2.0) * L   # 角-对角距离
RADIUS = 0.2                # 分子碰撞半径（决定平均自由程）
EPS = 0.002                 # 每次碰撞后速率损失比例
T0 = 1000                   # 初始温度
T_END = 0                   # 终温
MINUTES = 1000              # 1000 分钟 -> 1000°C 降到 0°C
TARGET_CROSSINGS = 750      # 前 500 分钟的设计穿越次数（要求 >=500）
N_BATCH = 1500              # 每批每元素单质数量
SPECIES = ["C2", "X2", "O2"]  # 冰-冰、晶-晶、秩-秩（聚素单质）
BATCHES = [("A", "元素单质"), ("B", "聚素单质")]


def default_load_spec(n_batch=N_BATCH):
    """T55 默认投料：两批聚素单质（A 批元素单质 + B 批聚素单质）。"""
    spec = []
    for tag, desc in BATCHES:
        for f in SPECIES:
            spec.append((tag, desc, f, n_batch))
    return spec


def build_templates(load_spec):
    """按投料清单构建分子模板（formula -> Mol）。

    优先使用 substances.json 的权威结构；其余（如散素 K2/A2/F2）用 F(v) 的单分子产物。
    """
    import pot_all as P
    subs = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    byf = {r["formula"]: r for r in subs}
    templates = {}
    for item in load_spec:
        formula = item[2]
        if formula in templates:
            continue
        if formula in byf:
            templates[formula] = E.mol_from_record(byf[formula])
            continue
        vec = P.parse_formula(formula)
        prods = E.complete_products(tuple(vec))
        if not prods:
            raise ValueError("无法为单质 %s 生成结构" % formula)
        mol = next((m for m in prods if m["formula"] == formula), prods[0])
        templates[formula] = mol
    return templates, byf

SNAP_MINUTES = [0, 25, 50, 100, 200, 300, 400, 500,
                600, 700, 800, 900, 950, 980, 995, 1000]
FORMULA_SAMPLE_MINUTES = 5     # 每 5 分钟记录一次完整组成
EVENT_SAMPLE_LIMIT = 20000

DT = 1.0                       # 每分钟一步


def set_geometry(new_L):
    """切换环境边长（T58 等需要更大区域/更稀薄气体时使用）。

    所有函数都从模块全局读取 L / DIAG，因此必须在创建 KineticEnvironment 之前调用。
    """
    global L, DIAG
    L = float(new_L)
    DIAG = math.sqrt(2.0) * L
    return L, DIAG


def mean_free_path(n):
    """2D 硬圆平均自由程：λ = L²/(2√2 N r)。"""
    if n <= 1:
        return float("inf")
    return L * L / (2.0 * math.sqrt(2.0) * n * RADIUS)


def design_v0(n_particles, target_crossings=TARGET_CROSSINGS, t_ref=500.0):
    """按 s(t_ref)=target*D 反解初速度：
        s = (λ/ε) ln(1 + ε v0 t / λ)  ->  v0 = λ/(ε t) (e^{ε s/λ} - 1)
    """
    lam = mean_free_path(n_particles)
    s = target_crossings * DIAG
    k = s / lam
    return lam / (EPS * t_ref) * (math.exp(EPS * k) - 1.0)


def radius_for(mol, area_model="uniform"):
    """分子的碰撞半径 / 面积模型。

    uniform : 所有分子半径 = RADIUS（T55/T56 口径）
    count   : 面积 ∝ 原子数（用户 T57 要求"元素数越多面积越大"）：
              A = π R²，R = RADIUS · sqrt(n/2)  =>  A ∝ n，n=2 时 R=RADIUS。
    """
    if area_model == "count":
        return RADIUS * math.sqrt(len(mol["atoms"]) / 2.0)
    return RADIUS


def design_v0_area(radii, target_crossings=TARGET_CROSSINGS, t_ref=500.0):
    """变截面（面积随分子大小变化）时的初速度设计。

    每人碰撞率 ν_i = v_i·√2·N·(R_i+R̄)/L²  =>  λ_i = L²/(√2·N·(R_i+R̄))。
    取最小 λ（最大分子，衰减最快），保证它也能达到 target 次穿越。
    返回 (v0, 设计信息 dict)。
    """
    n = len(radii)
    r_bar = sum(radii) / n
    r_max = max(radii)
    lam_min = L * L / (math.sqrt(2.0) * n * (r_max + r_bar))
    lam_mean = L * L / (math.sqrt(2.0) * n * (r_bar + r_bar))
    s = target_crossings * DIAG
    k_min = s / lam_min
    v0 = lam_min / (EPS * t_ref) * (math.exp(EPS * k_min) - 1.0)
    return v0, {
        "n": n, "r_bar": r_bar, "r_max": r_max,
        "lambda_min": lam_min, "lambda_mean": lam_mean,
        "target_crossings": target_crossings,
        "v0": v0,
    }


def poisson(rng, lam):
    """泊松采样（大均值用正态近似）。"""
    if lam <= 0:
        return 0
    if lam < 30.0:
        Lk = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            p *= rng.random()
            if p <= Lk:
                return k
            k += 1
    v = int(round(rng.gauss(lam, math.sqrt(lam))))
    return max(0, v)


class Particle:
    __slots__ = ("pid", "mol", "x", "y", "vx", "vy", "speed",
                 "path", "origin", "birth_t")

    def __init__(self, pid, mol, x, y, vx, vy, origin, birth_t):
        self.pid = pid
        self.mol = mol
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.speed = math.hypot(vx, vy)
        self.path = 0.0
        self.origin = origin
        self.birth_t = birth_t


def fold_axis(x, d):
    """[0,L] 反射折叠。返回 (新坐标, 是否翻转该轴速度)。"""
    u = x + d
    L2 = 2.0 * L
    r = u - math.floor(u / L2) * L2
    par = math.floor(u / L) - math.floor(x / L)
    nx = r if r <= L else L2 - r
    return nx, (par & 1)


class KineticEnvironment:
    def __init__(self, minutes=MINUTES, n_batch=N_BATCH, seed=20261116,
                 event_limit=EVENT_SAMPLE_LIMIT, snap_minutes=None, t0=T0,
                 load_spec=None, known_formulas=None, color_mode="elementset",
                 area_model="uniform", weighted_partner=False,
                 max_reaction_atoms=None, seed_particles=None):
        self.rng = random.Random(seed)
        self.minutes = minutes
        self.t0 = t0
        self.n_batch = n_batch
        self.load_spec = list(load_spec) if load_spec is not None else default_load_spec(n_batch)
        self.known_override = known_formulas
        self.color_mode = color_mode
        self.area_model = area_model
        self.weighted_partner = weighted_partner
        # 多阶段实验：从上一阶段导出的分子作为初始“底物”（整理后的环境）
        self.seed_particles = list(seed_particles) if seed_particles else None
        # 计算保护：合并后原子数超过上限的碰撞不执行反应（弹性），用于 >16 原子大分子体系
        self.max_reaction_atoms = max_reaction_atoms
        self.event_limit = event_limit
        self.snap_minutes = set(snap_minutes if snap_minutes is not None else SNAP_MINUTES)
        self.seed = seed
        self.particles = {}
        self.next_pid = 0
        self.fcnt = Counter()
        self.atom_count = 0
        self.path_sum = 0.0
        self.time_series = []
        self.formula_series = []
        self.snapshots = []
        self.events = []
        self.events_total = 0
        self.reaction_counts = Counter()
        self.net_change_counts = Counter()
        self.decomp_count = 0
        self.new_substances = {}
        self.initial_deaths = []      # 初始单质在反应前的 path/D
        self.all_particle_paths = []  # 所有粒子寿命 path/D（可能很多，做直方图）
        self.path_hist = Counter()    # path/D 分桶直方图
        self.path_stats = {"n": 0, "sum": 0.0, "min": None, "max": None}
        self.initial_survivors = 0
        self._last_c = 0
        self._last_i = 0
        self._last_n = 0
        self._templates = {}
        self._grid = {}
        self._cell = L / 10.0
        self._init_particles()

    # -------------------------------------------------------------- 初始化
    def _load_templates(self):
        templates, byf = build_templates(self.load_spec)
        self._templates = dict(templates)
        # 已知物质集合：默认 29 聚素；T56 等混合体系可传入 84,225 目录分子式集合
        self.known = set(self.known_override) if self.known_override is not None \
            else set(byf)

    def _init_particles(self):
        self._load_templates()
        rng = self.rng
        # 组织初始投料：seed_particles（上一阶段整理后的分子）+ load_spec（新批次）
        items = []   # (mol, count, origin)
        seed_n = 0
        if self.seed_particles:
            for rec in self.seed_particles:
                mol = rec if isinstance(rec, dict) and "formula" in rec and "label" in rec \
                    else E.make_mol(rec["atoms"], rec["edges"])
                c = int(rec.get("count", 1)) if isinstance(rec, dict) else 1
                items.append((mol, c, None))
                seed_n += c
        for _tag, _desc, f, count in self.load_spec:
            items.append((self._templates[f], int(count), f))
        for mol, _c, _o in items:
            self._templates.setdefault(mol["formula"], mol)
        total = sum(c for _m, c, _o in items)
        if self.area_model == "uniform" and not self.weighted_partner:
            v0 = design_v0(total)
            self.design_info = {"area_model": "uniform", "v0": v0,
                                "lambda": mean_free_path(total)}
        else:
            radii = []
            for mol, c, _o in items:
                radii += [radius_for(mol, self.area_model)] * c
            v0, self.design_info = design_v0_area(radii)
        self.v0 = v0
        self.seed_initial_count = seed_n
        for mol, c, origin in items:
            for _ in range(c):
                ang = rng.random() * 2.0 * math.pi
                x = rng.random() * L
                y = rng.random() * L
                p = Particle(self.next_pid, mol, x, y,
                             v0 * math.cos(ang), v0 * math.sin(ang),
                             origin, 0)
                self.next_pid += 1
                self.particles[p.pid] = p
                self.fcnt[mol["formula"]] += 1
                self.atom_count += len(mol["atoms"])
        self.n0 = len(self.particles)
        self.atoms0 = self.atom_count

    def export_state(self):
        """导出当前环境全部物质（按结构聚合），用于多阶段实验的“整理”。"""
        agg = {}
        for p in self.particles.values():
            key = (p.mol["atoms"], p.mol["edges"])
            rec = agg.get(key)
            if rec is None:
                agg[key] = {"atoms": list(p.mol["atoms"]),
                            "edges": [list(e) for e in p.mol["edges"]],
                            "formula": p.mol["formula"],
                            "count": 1}
            else:
                rec["count"] += 1
        mols = sorted(agg.values(), key=lambda r: (-r["count"], r["formula"]))
        return {"molecules": mols,
                "total_molecules": len(self.particles),
                "total_atoms": self.atom_count,
                "distinct_formulas": len(self.fcnt),
                "distinct_structures": len(mols),
                "t": self.minutes,
                "T": max(T_END, self.t0 - self.minutes)}

    # -------------------------------------------------------------- 运动
    def move_all(self):
        path_sum = 0.0
        speed_sum = 0.0
        for p in self.particles.values():
            p.path += p.speed * DT
            path_sum += p.speed * DT
            speed_sum += p.speed
            p.x, fx = fold_axis(p.x, p.vx * DT)
            p.y, fy = fold_axis(p.y, p.vy * DT)
            if fx:
                p.vx = -p.vx
            if fy:
                p.vy = -p.vy
        self.path_sum += path_sum
        return len(self.particles), speed_sum

    # -------------------------------------------------------------- 空间网格
    def build_grid(self):
        g = {}
        cs = self._cell
        for p in self.particles.values():
            key = (int(p.x // cs), int(p.y // cs))
            lst = g.get(key)
            if lst is None:
                g[key] = [p]
            else:
                lst.append(p)
        self._grid = g
        self._grid_n = int(L // cs) + 2

    def pick_partner(self, p):
        rng = self.rng
        cs = self._cell
        cx = int(p.x // cs)
        cy = int(p.y // cs)
        parts = self.particles
        g = self._grid
        for radius in (1, 2, 3):
            for _try in range(10):
                ox = rng.randint(-radius, radius)
                oy = rng.randint(-radius, radius)
                lst = g.get((cx + ox, cy + oy))
                if not lst:
                    continue
                q = lst[rng.randrange(len(lst))]
                if q is p or q.pid not in parts:
                    continue
                return q
        # 兜底：从全场随机取（极少数情况）
        if len(parts) <= 1:
            return None
        for _ in range(8):
            q = parts[rng.choice(list(parts.keys()))]
            if q is not p:
                return q
        return None

    def pick_partner_weighted(self, p, r_max):
        """按碰撞截面 (r_p + r_q) 加权选伙伴（T57 面积模型）。

        在邻域内随机取候选，按 (r_p+r_q)/(r_p+r_max) 接受（拒绝采样）。
        """
        rng = self.rng
        cs = self._cell
        cx = int(p.x // cs)
        cy = int(p.y // cs)
        parts = self.particles
        g = self._grid
        rp = radius_for(p.mol, self.area_model)
        for radius in (1, 2, 3):
            for _try in range(14):
                ox = rng.randint(-radius, radius)
                oy = rng.randint(-radius, radius)
                lst = g.get((cx + ox, cy + oy))
                if not lst:
                    continue
                q = lst[rng.randrange(len(lst))]
                if q is p or q.pid not in parts:
                    continue
                rq = radius_for(q.mol, self.area_model)
                if rp + r_max <= 0 or rng.random() < (rp + rq) / (rp + r_max):
                    return q
        if len(parts) <= 1:
            return None
        for _ in range(8):
            q = parts[rng.choice(list(parts.keys()))]
            if q is not p:
                return q
        return None

    # -------------------------------------------------------------- 反应/碰撞
    def _record_new(self, f, t, info, mol=None):
        if f not in self.known and f not in self.new_substances:
            rec = {"first_t": t, "event": info}
            if mol is not None:
                rec["label"] = mol["label"]
                rec["atoms"] = list(mol["atoms"])
                rec["edges"] = [list(e) for e in mol["edges"]]
                rec["c"] = mol["c"]
            self.new_substances[f] = rec

    def _record_path(self, p):
        val = p.path / DIAG
        st = self.path_stats
        st["n"] += 1
        st["sum"] += val
        if st["min"] is None or val < st["min"]:
            st["min"] = val
        if st["max"] is None or val > st["max"]:
            st["max"] = val
        b = int(val)
        self.path_hist[b] += 1

    def process_collision(self, p, q, T, t):
        rng = self.rng
        mi = p.mol
        mj = q.mol
        if self.max_reaction_atoms is not None and \
                len(mi["atoms"]) + len(mj["atoms"]) > self.max_reaction_atoms:
            # 计算保护：超大合并体系不做反应，只做弹性碰撞 + 衰减
            self.reaction_counts["capped"] += 1
            for z in (p, q):
                s = z.speed * (1.0 - EPS)
                ang = rng.random() * 2.0 * math.pi
                z.vx = s * math.cos(ang)
                z.vy = s * math.sin(ang)
                z.speed = s
            return
        res = E.resolve([mi, mj], T)
        typ = res["type"]
        state = res["state"]
        self.reaction_counts[typ] += 1
        if res["stages"]:
            self.decomp_count += len(res["stages"])
        in_labels = sorted((mi["label"], mj["label"]))
        out_labels = sorted(m["label"] for m in state)
        changed = in_labels != out_labels
        if not changed:
            # 弹性碰撞（含"完全反应但净结果不变"、自分解产物恰好同构等情况）
            for z in (p, q):
                s = z.speed * (1.0 - EPS)
                ang = rng.random() * 2.0 * math.pi
                z.vx = s * math.cos(ang)
                z.vy = s * math.sin(ang)
                z.speed = s
            return
        # ---- 净变化：替换两个分子为 state ----
        x = 0.5 * (p.x + q.x)
        y = 0.5 * (p.y + q.y)
        m1 = len(mi["atoms"])
        m2 = len(mj["atoms"])
        wmean = (m1 * p.speed + m2 * q.speed) / (m1 + m2) * (1.0 - EPS)
        # 记录寿命路径
        self._record_path(p)
        self._record_path(q)
        if p.origin is not None:
            self.initial_deaths.append(p.path / DIAG)
        if q.origin is not None:
            self.initial_deaths.append(q.path / DIAG)
        # 更新组成计数
        self.fcnt[mi["formula"]] -= 1
        self.fcnt[mj["formula"]] -= 1
        del self.particles[p.pid]
        del self.particles[q.pid]
        info = {
            "t": t, "T": T, "type": typ,
            "inputs": [mi["formula"], mj["formula"]],
            "products": [m["formula"] for m in state],
            "class": list(res["class"]) if res["class"] else None,
            "csum": res["csum"], "isum": res["isum"],
            "x": round(x, 1), "y": round(y, 1),
        }
        for m in state:
            s = wmean * rng.uniform(0.8, 1.2)
            ang = rng.random() * 2.0 * math.pi
            np_ = Particle(self.next_pid, m,
                           min(L, max(0.0, x + rng.uniform(-1.0, 1.0))),
                           min(L, max(0.0, y + rng.uniform(-1.0, 1.0))),
                           s * math.cos(ang), s * math.sin(ang),
                           None, t)
            self.next_pid += 1
            self.particles[np_.pid] = np_
            self.fcnt[m["formula"]] += 1
            self._templates.setdefault(m["formula"], m)
            self._record_new(m["formula"], t, info, m)
        # 事件样本（蓄水池）
        self.events_total += 1
        if len(self.events) < self.event_limit:
            self.events.append(info)
        else:
            j = rng.randrange(self.events_total)
            if j < self.event_limit:
                self.events[j] = info

    # -------------------------------------------------------------- 主循环
    def run(self):
        t_start = time.time()
        log_every = 50
        for t in range(self.minutes):
            T = max(T_END, self.t0 - t)
            n, speed_sum = self.move_all()
            if n <= 1:
                self.time_series.append(self._ts_row(t, T, 0))
                continue
            plist = list(self.particles.values())
            # ---------------- 碰撞率：固定半径（T55/T56 口径）或 面积∝原子数（T57） ----------------
            if self.area_model == "uniform":
                lam = mean_free_path(n)
                r_bar = RADIUS
                r_max = RADIUS
                cum = []
                total = 0.0
                for p in plist:
                    total += p.speed * DT / lam
                    cum.append(total)
            else:
                radii = [radius_for(p.mol, self.area_model) for p in plist]
                r_bar = sum(radii) / n
                r_max = max(radii)
                factor = math.sqrt(2.0) * n / (L * L)
                lam = L * L / (math.sqrt(2.0) * n * (r_bar + r_bar))  # 代表平均自由程
                cum = []
                total = 0.0
                for p, r in zip(plist, radii):
                    total += p.speed * factor * (r + r_bar) * DT
                    cum.append(total)
            self.build_grid()
            k_total = poisson(self.rng, 0.5 * total)
            rng = self.rng
            collisions = 0
            for _ in range(k_total):
                r = rng.random() * total
                i = bisect(cum, r)
                if i >= len(plist):
                    i = len(plist) - 1
                p = plist[i]
                if p.pid not in self.particles:
                    continue
                if self.weighted_partner:
                    q = self.pick_partner_weighted(p, r_max)
                else:
                    q = self.pick_partner(p)
                if q is None:
                    continue
                self.process_collision(p, q, T, t)
                collisions += 1
            # ---------------- 统计记录 ----------------
            speeds = [p.speed for p in self.particles.values()]
            mean_speed = sum(speeds) / len(speeds) if speeds else 0.0
            samp = speeds if len(speeds) <= 600 else rng.sample(speeds, 600)
            samp.sort()
            med = samp[len(samp) // 2] if samp else 0.0
            p90 = samp[int(len(samp) * 0.9)] if samp else 0.0
            max_atoms = max((len(p.mol["atoms"]) for p in self.particles.values()),
                            default=0)
            row = {
                "t": t, "T": T, "N": len(self.particles),
                "capped": self.reaction_counts["capped"],
                "atoms": self.atom_count,
                "mean_atoms": round(self.atom_count / len(self.particles), 3) if self.particles else 0,
                "max_atoms": max_atoms,
                "speed_mean": round(mean_speed, 1),
                "speed_median": round(med, 1),
                "speed_p90": round(p90, 1),
                "free_path": round(lam, 1),
                "r_bar": round(r_bar, 4),
                "collisions": collisions,
                "complete": self.reaction_counts["complete"],
                "incomplete": self.reaction_counts["incomplete"],
                "none": self.reaction_counts["none"],
                "decomp": self.decomp_count,
                "path_D": round(self.path_sum / DIAG, 1),
                "distinct": len(self.fcnt),
                "events_total": self.events_total,
            }
            # 每分钟的类型增量（用差分另存）
            row["d_complete"] = self.reaction_counts["complete"] - getattr(self, "_last_c", 0)
            row["d_incomplete"] = self.reaction_counts["incomplete"] - getattr(self, "_last_i", 0)
            row["d_none"] = self.reaction_counts["none"] - getattr(self, "_last_n", 0)
            row["d_capped"] = self.reaction_counts["capped"] - getattr(self, "_last_capped", 0)
            self._last_c = self.reaction_counts["complete"]
            self._last_i = self.reaction_counts["incomplete"]
            self._last_n = self.reaction_counts["none"]
            self._last_capped = self.reaction_counts["capped"]
            row["top"] = {f: c for f, c in self.fcnt.most_common(8) if c > 0}
            self.time_series.append(row)
            if t % FORMULA_SAMPLE_MINUTES == 0 or t in self.snap_minutes:
                self.formula_series.append({
                    "t": t, "T": T,
                    "counts": {f: c for f, c in self.fcnt.items() if c > 0},
                })
            if t in self.snap_minutes:
                self.snapshots.append(self._snapshot(t))
            if t % log_every == 0:
                print("[t=%4d T=%4d] N=%5d atoms=%5d speed=%.0f coll/min=%5d ev=%d "
                      "comp=%d inc=%d dec=%d path/D=%.0f  (%.0fs)" % (
                          t, T, len(self.particles), self.atom_count, mean_speed,
                          collisions, self.events_total,
                          self.reaction_counts["complete"],
                          self.reaction_counts["incomplete"],
                          self.decomp_count, self.path_sum / DIAG,
                          time.time() - t_start), flush=True)
        # 终态
        self.final_snapshot = self._snapshot(self.minutes)
        self.result = self._build_result(t_start)
        return self.result

    # -------------------------------------------------------------- 统计/输出
    def _ts_row(self, t, T, collisions):
        return {"t": t, "T": T, "N": 0, "atoms": self.atom_count,
                "collisions": collisions}

    def _snapshot(self, t):
        rng = self.rng
        ps = list(self.particles.values())
        if len(ps) > 3000:
            ps = rng.sample(ps, 3000)
        pts = []
        if self.color_mode == "bitmask":
            # 6+ 元素体系：按元素集合的 9 位掩码着色（legend 自动给出元素组合）
            legend = {}
            for p in ps:
                elems = set(p.mol["atoms"])
                code = 0
                for e in elems:
                    code |= 1 << P.ORDER.index(e)
                key = str(code)
                if key not in legend:
                    legend[key] = "+".join(P.CN[e] for e in P.ORDER if e in elems)
                pts.append([round(p.x, 1), round(p.y, 1), code])
            return {"t": t, "points": pts, "legend": legend,
                    "color_mode": "element_bitmask"}
        for p in ps:
            elems = set(p.mol["atoms"])
            if elems == {"O"}:
                col = 0
            elif elems == {"X"}:
                col = 1
            elif elems == {"C"}:
                col = 2
            elif elems == {"O", "X"}:
                col = 3
            elif elems == {"O", "C"}:
                col = 4
            elif elems == {"X", "C"}:
                col = 5
            else:
                col = 6
            pts.append([round(p.x, 1), round(p.y, 1), col])
        return {"t": t, "points": pts,
                "legend": {"0": "O(秩)", "1": "X(晶)", "2": "C(冰)",
                           "3": "O+X", "4": "O+C", "5": "X+C", "6": "O+X+C"}}

    def _build_result(self, t_start):
        # 初始单质路径统计
        init = sorted(self.initial_deaths)
        survivors = 0
        for p in self.particles.values():
            if p.origin is not None:
                survivors += 1
                init.append(p.path / DIAG)
        def pct(a, q):
            if not a:
                return None
            return round(a[min(len(a) - 1, int(q * len(a)))], 1)
        init_stats = {"n": len(init),
                      "min": round(init[0], 1) if init else None,
                      "p1": pct(init, 0.01),
                      "median": pct(init, 0.5),
                      "max": round(init[-1], 1) if init else None,
                      "survivors": survivors}
        # 全部粒子寿命路径分桶
        hist = {str(k): v for k, v in sorted(self.path_hist.items())}
        comp = {}
        for f, c in self.fcnt.items():
            if c <= 0:
                continue
            mol = self._structure(f)
            comp[f] = {"count": c,
                       "atoms": len(mol["atoms"]) if mol else None,
                       "zh": E.formula_zh(f),
                       "known29": f in self.known}
        top = sorted(comp.items(), key=lambda kv: -kv[1]["count"])
        samples = {}
        for f, _ in top[:24]:
            mol = self._structure(f)
            if mol:
                samples[f] = {"label": mol["label"], "atoms": list(mol["atoms"]),
                              "edges": [list(e) for e in mol["edges"]],
                              "c": mol["c"]}
        cfg = {
            "L": L, "diagonal": round(DIAG, 3), "radius": RADIUS, "eps": EPS,
            "T0": self.t0, "T_end": T_END, "minutes": self.minutes,
            "load_spec": [{"tag": tag, "desc": desc, "formula": f, "count": int(c)}
                          for tag, desc, f, c in self.load_spec],
            "initial_particles": self.n0, "initial_atoms": self.atoms0,
            "seed_initial_count": getattr(self, "seed_initial_count", 0),
            "v0": round(self.v0, 1),
            "area_model": self.area_model,
            "weighted_partner": self.weighted_partner,
            "max_reaction_atoms": self.max_reaction_atoms,
            "radius_base": RADIUS,
            "area_formula": ("A = π·RADIUS²·(n_atoms/2)，R = RADIUS·sqrt(n/2)"
                             if self.area_model == "count" else "A = π·RADIUS²（固定）"),
            "design": {k: (round(v, 6) if isinstance(v, float) else v)
                       for k, v in (self.design_info or {}).items()},
            "design_target_crossings": TARGET_CROSSINGS,
            "design_window_minutes": 500,
            "formula_sample_minutes": FORMULA_SAMPLE_MINUTES,
            "snap_minutes": sorted(self.snap_minutes),
            "seed": self.seed,
            "mean_free_path0": round(mean_free_path(self.n0), 2),
        }
        return {
            "config": cfg,
            "summary": {
                "runtime_s": round(time.time() - t_start, 1),
                "final_T": max(T_END, self.t0 - self.minutes),
                "final_N": len(self.particles),
                "final_atoms": self.atom_count,
                "final_path_D": round(self.path_sum / DIAG, 1),
                "events_total": self.events_total,
                "reaction_counts": dict(self.reaction_counts),
                "decomp_events": self.decomp_count,
                "initial_single_path_stats": init_stats,
                "lifetime_path_stats": self.path_stats,
                "lifetime_path_hist": hist,
            },
            "final_composition": comp,
            "final_top_structures": samples,
            "new_substances": self.new_substances,
            "time_series": self.time_series,
            "formula_series": self.formula_series,
            "snapshots": self.snapshots,
            "event_samples": self.events,
        }

    def _structure(self, f):
        mol = self._templates.get(f)
        if mol is not None:
            return mol
        rec = self.new_substances.get(f)
        if rec and "atoms" in rec:
            mol = E.make_mol(rec["atoms"], rec["edges"])
            self._templates[f] = mol
            return mol
        return self._reconstruct_mol(f)

    def _reconstruct_mol(self, f):
        """按分子式重建一个代表结构：优先用 F(v)。"""
        import pot_all as P
        vec = P.parse_formula(f)
        prods = E.complete_products(tuple(vec))
        if prods:
            mol = next((m for m in prods if m["formula"] == f), prods[0])
            self._templates[f] = mol
            return mol
        return None


# ================================================================== 对照组
def run_control(minutes=500, n_batch=N_BATCH, seed=20261116, load_spec=None,
                area_model="uniform"):
    """关闭化学反应的对照：验证 500 次角-对角穿越要求。

    area_model="count" 时按 T57 面积模型变截面：ν_i = v_i·√2·N·(R_i+R̄)/L²。
    每个"碰撞参与事件"衰减一个粒子（与主实验成对事件在每人碰撞次数上等价）。
    """
    rng = random.Random(seed)
    if load_spec is None:
        load_spec = default_load_spec(n_batch)
    templates, _byf = build_templates(load_spec)
    n0 = sum(int(item[3]) for item in load_spec)
    radii = []
    for _tag, _desc, f, count in load_spec:
        radii += [radius_for(templates[f], area_model)] * int(count)
    if area_model == "uniform":
        v0 = design_v0(n0)
        design = {"area_model": "uniform", "lambda": mean_free_path(n0), "v0": v0}
        lam = mean_free_path(n0)
        r_bar = RADIUS
        factor = None
    else:
        v0, design = design_v0_area(radii)
        r_bar = sum(radii) / n0
        lam = L * L / (math.sqrt(2.0) * n0 * (r_bar + r_bar))
        factor = math.sqrt(2.0) * n0 / (L * L)
    particles = []
    for _tag, _desc, f, count in load_spec:
        mol = templates[f]
        for _ in range(int(count)):
            ang = rng.random() * 2.0 * math.pi
            particles.append(Particle(len(particles), mol, rng.random() * L,
                                      rng.random() * L, v0 * math.cos(ang),
                                      v0 * math.sin(ang), f, 0))
    ts = []
    path_sum = 0.0
    t_start = time.time()
    for t in range(minutes):
        sp_sum = 0.0
        for p in particles:
            p.path += p.speed * DT
            path_sum += p.speed * DT
            sp_sum += p.speed
            p.x, fx = fold_axis(p.x, p.vx * DT)
            p.y, fy = fold_axis(p.y, p.vy * DT)
            if fx:
                p.vx = -p.vx
            if fy:
                p.vy = -p.vy
        cum = []
        total = 0.0
        if area_model == "uniform":
            for p in particles:
                total += p.speed * DT / lam
                cum.append(total)
        else:
            for p, r in zip(particles, radii):
                total += p.speed * factor * (r + r_bar) * DT
                cum.append(total)
        k = poisson(rng, total)
        for _ in range(k):
            i = bisect(cum, rng.random() * total)
            p = particles[i]
            ang = rng.random() * 2.0 * math.pi
            s = p.speed * (1.0 - EPS)
            p.vx = s * math.cos(ang)
            p.vy = s * math.sin(ang)
            p.speed = s
        if t % 10 == 0:
            ts.append({"t": t, "path_D_mean": round(path_sum / DIAG / n0, 2),
                       "speed_mean": round(sp_sum / n0, 1)})
        if t % 100 == 0:
            print("[control t=%4d] path/D per particle=%.1f speed=%.0f (%.0fs)" % (
                t, path_sum / DIAG / n0, sp_sum / n0, time.time() - t_start), flush=True)
    cross = sorted(p.path / DIAG for p in particles)
    def pct(a, q):
        return round(a[min(len(a) - 1, int(q * len(a)))], 1)
    stats = {
        "n": len(cross),
        "min": round(cross[0], 1), "p1": pct(cross, 0.01),
        "p5": pct(cross, 0.05), "median": pct(cross, 0.5),
        "p95": pct(cross, 0.95), "max": round(cross[-1], 1),
        "fraction_ge_500": round(sum(1 for c in cross if c >= 500) / len(cross), 4),
        "mean": round(sum(cross) / len(cross), 1),
    }
    # 按初始分子大小分组的穿越统计（T57 用于核对"大分子也 ≥500 次"）
    by_size = {}
    for p in particles:
        n_at = len(p.mol["atoms"])
        by_size.setdefault(str(n_at), []).append(p.path / DIAG)
    by_size_stats = {}
    for k_, arr in sorted(by_size.items(), key=lambda kv: int(kv[0])):
        arr = sorted(arr)
        by_size_stats[k_] = {"n": len(arr), "min": round(arr[0], 1),
                             "median": pct(arr, 0.5), "max": round(arr[-1], 1)}
    return {
        "config": {"minutes": minutes, "n_particles": n0, "v0": round(v0, 1),
                   "radius": RADIUS, "eps": EPS, "L": L, "seed": seed,
                   "chemical_reactions": False,
                   "area_model": area_model,
                   "area_formula": ("A = π·RADIUS²·(n_atoms/2)" if area_model == "count"
                                    else "A = π·RADIUS²（固定）"),
                   "mean_free_path": round(lam, 2),
                   "design": {k: (round(v, 6) if isinstance(v, float) else v)
                              for k, v in design.items()},
                   "load_spec": [{"tag": it[0], "desc": it[1], "formula": it[2],
                                  "count": int(it[3]),
                                  "atoms": len(templates[it[2]]["atoms"])}
                                 for it in load_spec]},
        "stats": stats,
        "by_size": by_size_stats,
        "timeseries": ts,
        "runtime_s": round(time.time() - t_start, 1),
    }


# ================================================================== main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=MINUTES)
    ap.add_argument("--t0", type=float, default=T0, help="初始温度（°C）")
    ap.add_argument("--per-species-batch", type=int, default=N_BATCH)
    ap.add_argument("--seed", type=int, default=20261116)
    ap.add_argument("--out", default=BASE + r"\t55_kinetic_result.json")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)
    if args.control:
        res = run_control(minutes=500 if not args.quick else 60,
                          n_batch=args.per_species_batch,
                          seed=args.seed)
        out = args.out if args.control is not True else BASE + r"\t55_control_no_chem.json"
        if args.out != BASE + r"\t55_kinetic_result.json":
            out = args.out
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("saved", out)
        print(json.dumps(res["stats"], ensure_ascii=False, indent=1))
        return
    env = KineticEnvironment(minutes=args.minutes,
                             n_batch=args.per_species_batch,
                             seed=args.seed,
                             t0=args.t0,
                             snap_minutes=SNAP_MINUTES if not args.quick else [0, 30, 60])
    if args.quick:
        env.minutes = args.minutes
    res = env.run()
    json.dump(res, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", args.out)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:2000])


if __name__ == "__main__":
    main()
