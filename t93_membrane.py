# -*- coding: utf-8 -*-
"""T93 动态仿真：热环境中的多分子核心 + C 类低温冷壳保护膜。

问题（用户 m00xxx / task-2）
---------------------------
C 类低温分子（C2K2 / OXC / C2 等，T_deg 低、η 低）能否在多分子核心外围形成
「冰壳」并同时提供两件保护：
  ① 保温：外界 400°C 热浴下内部仍保持低温；
  ② 隔绝：阻挡壳外富 F/O 反应性分子与核心接触，让内部反应继续、外部接触反应不发生。

实验结构（在 t87_env_asym.AsymWorld 上派生，不修改任何既有文件/内核）
--------------------------------------------------------------------
世界 160×110，T_env 恒定（主臂 400°C，冷臂 20°C）。初始四部分：
  * 核心 core：24 个 C3K3F2 紧凑团簇（T90 主体；引擎实际 k=1 格/分子，
    见 docs/T93_SIM.md「与 T90 文档的差异」）；
  * 壳内食物 food：C2K2、CKF2 各 40，位于半径 3.4~7；
  * 冷壳 shell：环带 R=8~12 的低温分子（默认 OXC 220 个，--shell 可换 C2 / X2C2 /
    OXC+OP 双层），初始占满环带；
  * 攻击浴 bath：壳外 R>=14 的富 F/O 反应性分子 360 个
    （F2 / CF / X2AF2 / OP / OK / O2 / OCF2 等份；这些物种均在
    t4_catalog_all_validated.json 中，OF/OP2C/OPC 缺目录故不用）。
核心冻结（同 T90「主体设为固态」）；壳、食物、浴自由运动。

与 T87 的差异
-------------
1) 新增热场 τ（本文件 ThermalField）：粗网格 W//4 × H//4，每格
   η = 该格存活分子 η 的均值（空格 η_env=0.35），
   η=(1-ρ̂)(T_deg+1)/(T_deg+4), ρ̂=(3n_O+2n_K+n_P)/(3N), T_deg=n_L+2n_F；
   κ_ij=0.35·sqrt(η_i η_j)，4 邻居显式差分，dt 取 dt·max Σκ ≤ 0.5；
   边界每拍向 T_env 松弛（λ_b=0.3）。
   τ 只用于度量/展示「内部温度」，**不修改 resolve 的 Tamb**：反应门控仍只由
   ρ_E（恒素场）决定，避免双重计温。
2) 环境恒温（ambient_T 覆盖为常数 T_env），不做 T87 的 1000→10°C 冷却。
3) 重力可配置（--grav）；T87 默认 0.30。OXC mass=3，连续重力会很快把冷壳
   沉离核心，因此主保护组取 G=0（微重力/支撑表面条件），另设 G=0.30（T87 语义）
   与 G=0.03（低重力）对照臂。
4) 反应速率 p_react 取 0.004（低于 T87 的 0.012），原因：本实验观察 700 拍内
   结构演化，若用 T87 速率，壳/核心在 700 拍内会被规则反应完全消耗，无法区分
   「壳的保护」与「化学反应消耗」；该参数在文档中说明。

输出
----
t93_membrane.json（主文件：config + 每臂 summary + 每 10 拍 series + 跨臂表）
t93_<arm>.json（每臂独立文件：含最终分子位置，供 t93_render.py 出图）
t93_run.log（运行日志）
images/t93_*.png（t93_render.py 生成）

只读内核（alchemy.attrs / alchemy.three_su / natural_engine），不修改既有文件。
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import tempfile
import time
import traceback

from alchemy import three_su as TS

import t83_env_axes as T83
import t84_env_skel as T84
import t85_env_resolve as T85
import t86_env_tri as T86
import t87_env_asym as T87
from t83_env_axes import comp_of, catalog_index

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE, "t93_run.log")

# 分子/环境常量 -------------------------------------------------------------
CORE_FORMULA = "C3K3F2"
FOOD1 = "C2K2"
FOOD2 = "CKF2"
SHELL_OXC = "OXC"
SHELL_C2 = "C2"
SHELL_X2C2 = "X2C2"
SHELL_OP = "OP"
BATH_POOL = ["F2", "CF", "X2AF2", "OP", "OK", "O2", "OCF2"]

THERMAL_BLOCK = 2      # τ 网格：W//2 × H//2（Lead 复核：4×4 粗格会把 1~2 格厚的壳稀释掉）
KAPPA0 = 0.35          # κ_ij = KAPPA0 * sqrt(η_i η_j)
ETA_ENV = 0.35         # 空格 η
LAMBDA_B = 0.3         # 边界向 T_env 松弛
T_INIT = 20.0          # 内部初始温度（冷装配后放入热浴）
R_INIT_HOT = 13.0      # τ 初值：距核心 > 13 格的格子初始为 T_env（外部热浴）
                       # 所有臂同一初值剖面，仅冷壳分子不同，便于对照

CORE_CENTER = (55, 80)  # 世界 160×110（居中，上下留出重力坍塌空间）
CORE_ZONE = 8           # 核心判定/冻结区（Chebyshev 距离）
R_INTERIOR = 8.0        # 反应/τ 分区：<8 内部；8~13 壳体带；>13 外部
R_SHELL_ZONE = 13.0
RHO_IN_MAX = 12.0       # ρ_E 内部区域半径
RHO_OUT_MIN, RHO_OUT_MAX = 16.0, 40.0

P_REACT = 0.010        # 本实验观察 700 拍结构演化；T87 默认 0.012，取略低
CAP = 26
SEED = 20261123


# ---------------------------------------------------------------------------
def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with io.open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def atomic_json(path, obj):
    """崩溃安全的 JSON 落盘。"""
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
class ThermalField:
    """τ 粗网格热场（只度量，不参与反应门控）。"""

    def __init__(self, W, H, T_env, block=THERMAL_BLOCK, T_init=T_INIT,
                 eta_env=ETA_ENV, kappa0=KAPPA0, lam_b=LAMBDA_B,
                 r_init_hot=R_INIT_HOT, core_center=CORE_CENTER):
        self.block = block
        self.bw = max(2, W // block)
        self.bh = max(2, H // block)
        self.T_env = float(T_env)
        self.eta_env = float(eta_env)
        self.kappa0 = float(kappa0)
        self.lam_b = float(lam_b)
        self.eta = [[eta_env] * self.bw for _ in range(self.bh)]
        # 初值：外部热浴区 T_env，内部（R<=r_init_hot）冷 T_init
        cr, cc = core_center
        self.tau = []
        for i in range(self.bh):
            row = []
            wr = (i + 0.5) * block
            for j in range(self.bw):
                wc = (j + 0.5) * block
                d = math.hypot(wr - cr, wc - cc)
                row.append(self.T_env if d > r_init_hot else T_init)
            self.tau.append(row)

    # -- η -----------------------------------------------------------------
    @staticmethod
    def eta_of(typeinfo):
        comp = typeinfo["comp"]
        N = max(1, typeinfo["natoms"])
        rho_hat = (3.0 * comp.get("O", 0) + 2.0 * comp.get("K", 0)
                   + comp.get("P", 0)) / (3.0 * N)
        T_deg = comp.get("L", 0) + 2.0 * comp.get("F", 0)
        eta = (1.0 - rho_hat) * (T_deg + 1.0) / (T_deg + 4.0)
        return min(1.0, max(0.0, eta))

    def update_eta(self, world):
        bh, bw = self.bh, self.bw
        acc = [[0.0] * bw for _ in range(bh)]
        cnt = [[0] * bw for _ in range(bh)]
        for m in world.live_mols():
            t = world.types[m["f"]]
            i = min(bh - 1, max(0, m["r"] // self.block))
            j = min(bw - 1, max(0, m["c"] // self.block))
            acc[i][j] += self.eta_of(t)
            cnt[i][j] += 1
        for i in range(bh):
            for j in range(bw):
                self.eta[i][j] = (acc[i][j] / cnt[i][j]) if cnt[i][j] else self.eta_env

    # -- 一步显式差分 -------------------------------------------------------
    def step(self, world):
        self.update_eta(world)
        bh, bw = self.bh, self.bw
        k0 = self.kappa0
        eta = self.eta
        # κ_ij = k0·sqrt(η_i η_j) = k0·s_i·s_j，先预计算 sqrt(η) 与边系数
        s = [[math.sqrt(max(1e-9, eta[i][j])) for j in range(bw)]
             for i in range(bh)]
        kx = [[k0 * s[i][j] * s[i][j + 1] for j in range(bw - 1)]
              for i in range(bh)]
        ky = [[k0 * s[i][j] * s[i + 1][j] for j in range(bw)]
              for i in range(bh - 1)]
        maxsum = 1e-9
        for i in range(bh):
            for j in range(bw):
                v = 0.0
                if j > 0:
                    v += kx[i][j - 1]
                if j < bw - 1:
                    v += kx[i][j]
                if i > 0:
                    v += ky[i - 1][j]
                if i < bh - 1:
                    v += ky[i][j]
                if v > maxsum:
                    maxsum = v
        dt = 0.5 / maxsum
        tau = self.tau
        new = [row[:] for row in tau]
        for i in range(bh):
            tr = tau[i]
            nr = new[i]
            ku = ky[i - 1] if i > 0 else None
            tu = tau[i - 1] if i > 0 else None
            kd = ky[i] if i < bh - 1 else None
            td = tau[i + 1] if i < bh - 1 else None
            for j in range(bw):
                t0 = tr[j]
                v = 0.0
                if j > 0:
                    v += kx[i][j - 1] * (tr[j - 1] - t0)
                if j < bw - 1:
                    v += kx[i][j] * (tr[j + 1] - t0)
                if ku is not None:
                    v += ku[j] * (tu[j] - t0)
                if kd is not None:
                    v += kd[j] * (td[j] - t0)
                x = t0 + dt * v
                if i == 0 or i == bh - 1 or j == 0 or j == bw - 1:
                    x += self.lam_b * (self.T_env - t0)
                if x < -100.0:
                    x = -100.0
                elif x > 2000.0:
                    x = 2000.0
                nr[j] = x
        self.tau = new

    # -- 采样 ---------------------------------------------------------------
    def _cell_center(self, i, j):
        return ((i + 0.5) * self.block, (j + 0.5) * self.block)

    def sample(self, core_center):
        """按世界距离分桶：core(≤3) / in(3~7) / shell环带(7~12.5) / out(12.5~32) / edge。"""
        cr, cc = core_center
        buckets = {"core": [], "in": [], "shell": [], "out": [], "edge": []}
        for i in range(self.bh):
            for j in range(self.bw):
                wr, wc = self._cell_center(i, j)
                d = math.hypot(wr - cr, wc - cc)
                if d <= 3.0:
                    buckets["core"].append(self.tau[i][j])
                elif d <= 7.0:
                    buckets["in"].append(self.tau[i][j])
                elif d <= 12.5:
                    buckets["shell"].append(self.tau[i][j])
                elif d <= 32.0:
                    buckets["out"].append(self.tau[i][j])
                if i in (0, self.bh - 1) or j in (0, self.bw - 1):
                    buckets["edge"].append(self.tau[i][j])
        return {k: (round(sum(v) / len(v), 2) if v else None)
                for k, v in buckets.items()}


# ---------------------------------------------------------------------------
class MembraneWorld(T87.AsymWorld):
    """热浴 + 核心 + 冷壳 + 攻击浴 三段结构世界。"""

    def __init__(self, W=160, H=110, seed=SEED, T_env=400.0, grav=0.0,
                 ticks=700, core_center=CORE_CENTER, core_n=24,
                 food1=40, food2=40, shell=SHELL_OXC, shell_n=300,
                 shell_rin=8.2, shell_rout=12.4, double=False,
                 outer=SHELL_OP, outer_n=90, outer_rin=12.6, outer_rout=15.6,
                 bath=True, bath_n=360, bath_pool=None,
                 p_react=P_REACT, **kw):
        # 先存参数，再 super().__init__（它会调 _place_feed，feed 传空）
        self.T_env = float(T_env)
        self.grav = float(grav)
        self.ticks_total = int(ticks)
        self.core_center = tuple(core_center)
        self.core_n_target = int(core_n)
        self.double = bool(double)
        self.shell_formula = shell
        self.outer_formula = outer if double else None
        self.shell_ids = set()
        self.shell_inner_ids = set()
        self.shell_outer_ids = set()
        self.bath_ids = set()
        self.food_ids = set()
        self.core_ids = set()
        self.contacts_fc = 0        # 外来-核心 相邻对（累计，逐拍）
        self.contacts_fs = 0        # 外来-壳   相邻对（累计，逐拍）
        self.react_in = 0           # 反应质心 R<=8
        self.react_shell = 0        # 8<R<=13
        self.react_out = 0          # R>13
        self.react_core = 0         # 含核心分子的反应
        self.react_shell_involved = 0
        self.react_core_attack = 0  # 核心 + 外来（浴系）反应 = 核心被侵蚀
        self.react_shell_bath = 0   # 壳 + 外来（浴系）反应 = 壳被消耗
        self.n_grown_core = 0       # 内部食物缩合生成的新核心单元（T90 生长）
        self.bath_lineage = set()   # 初始攻击浴 + 其后代产物 id
        self.measure_every = 10
        self._spawn_min_r = 0.0     # 产物生成的最小半径（防止产物瞬移穿膜）

        e_cells = (max(4, W // 8), max(4, H // 8))
        super().__init__(W, H, seed, [], catalog_index(),
                         cap=CAP, p_react=p_react, force_r=2,
                         lock_r=2, lock_w=1.0, e_cells=e_cells,
                         t0=1000.0, t_end=10.0, cool_k=10.0, cool_ticks=10,
                         track_every=0, **kw)
        self.thermal = ThermalField(W, H, self.T_env, core_center=self.core_center)
        self.food_pool = [FOOD1] * int(food1) + [FOOD2] * int(food2)
        self.bath_pool = list(bath_pool or BATH_POOL)
        self.shell_n_target = int(shell_n) if shell else 0
        self.outer_n_target = int(outer_n) if double else 0
        self.bath_n_target = int(bath_n) if bath else 0
        self.shell_rin = float(shell_rin)
        self.shell_rout = float(shell_rout)
        self.outer_rin = float(outer_rin)
        self.outer_rout = float(outer_rout)
        self._place_all()
        self.bath_lineage = set(self.bath_ids)
        self.thermal.update_eta(self)

    # -- 放置 ---------------------------------------------------------------
    def _cells_for(self, formula, r, c):
        t = self.ensure_type(formula)
        cells = [(r + dr, c + dc) for dr, dc in t["shape"]]
        if any(not (0 <= x < self.H and 0 <= y < self.W) for x, y in cells):
            return None
        if any((x, y) in self.cell for x, y in cells):
            return None
        return cells

    def _place_at(self, formula, r, c, role):
        cells = self._cells_for(formula, r, c)
        if cells is None:
            return None
        mid = self.add_mol(formula, r, c, cells=cells)
        if mid is None:
            return None
        if role == "core":
            self.core_ids.add(mid)
        elif role == "food":
            self.food_ids.add(mid)
        elif role == "shell":
            self.shell_ids.add(mid)
            self.shell_inner_ids.add(mid)
        elif role == "outer":
            self.shell_ids.add(mid)
            self.shell_outer_ids.add(mid)
        elif role == "bath":
            self.bath_ids.add(mid)
        return mid

    def _place_ring(self, formula, n, rin, rout, role, tries_per=600):
        cr, cc = self.core_center
        placed = 0
        for k in range(n):
            ok = False
            for _ in range(tries_per):
                ang = self.rng.random() * 2.0 * math.pi
                rad = rin + (rout - rin) * self.rng.random()
                r = int(round(cr + rad * math.sin(ang)))
                c = int(round(cc + rad * math.cos(ang)))
                if self._cells_for(formula, r, c) is not None:
                    self._place_at(formula, r, c, role)
                    placed += 1
                    ok = True
                    break
            if not ok:
                break
        return placed

    def _place_compact_core(self, n):
        cr, cc = self.core_center
        offs = []
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                offs.append((dr * dr + dc * dc, abs(dr) + abs(dc), dr, dc))
        offs.sort()
        # 5×5 内取 n 个最靠中心的格子（n<=24 时最外角放弃）
        placed = 0
        for _, _, dr, dc in offs:
            if placed >= n:
                break
            if self._place_at(CORE_FORMULA, cr + dr, cc + dc, "core") is not None:
                placed += 1
        return placed

    def _place_food(self, n, rin=4.2, rout=7.2, tries_per=3000):
        cr, cc = self.core_center
        placed = 0
        pool = self.food_pool[:]
        self.rng.shuffle(pool)
        for formula in pool:
            if placed >= n:
                break
            for _ in range(tries_per):
                ang = self.rng.random() * 2.0 * math.pi
                rad = rin + (rout - rin) * self.rng.random()
                r = int(round(cr + rad * math.sin(ang)))
                c = int(round(cc + rad * math.cos(ang)))
                if self._cells_for(formula, r, c) is not None:
                    self._place_at(formula, r, c, "food")
                    placed += 1
                    break
        return placed

    def _place_bath(self, n, rmin=13.5, rmax=26.0):
        """攻击浴放在壳外环带（高密度包围），不足时退化为全区域随机。"""
        cr, cc = self.core_center
        placed = 0
        pool = self.bath_pool
        for k in range(n):
            formula = pool[k % len(pool)]
            ok = False
            for attempt in range(600):
                if attempt < 500:
                    ang = self.rng.random() * 2.0 * math.pi
                    rad = rmin + (rmax - rmin) * self.rng.random()
                    r = int(round(cr + rad * math.sin(ang)))
                    c = int(round(cc + rad * math.cos(ang)))
                else:
                    r = self.rng.randrange(self.H)
                    c = self.rng.randrange(self.W)
                    if math.hypot(r - cr, c - cc) < rmin:
                        continue
                if not (0 <= r < self.H and 0 <= c < self.W):
                    continue
                if self._cells_for(formula, r, c) is not None:
                    self._place_at(formula, r, c, "bath")
                    placed += 1
                    ok = True
                    break
            if not ok:
                break
        return placed

    def _place_all(self):
        nc = self._place_compact_core(self.core_n_target)
        nf1 = len([f for f in self.food_pool if f == FOOD1])
        nf2 = len([f for f in self.food_pool if f == FOOD2])
        nf = self._place_food(nf1 + nf2)
        if self.shell_formula:
            self._place_ring(self.shell_formula, self.shell_n_target,
                             self.shell_rin, self.shell_rout, "shell")
        if self.double:
            self._place_ring(self.outer_formula, self.outer_n_target,
                             self.outer_rin, self.outer_rout, "outer")
        # 攻击浴的位置：有壳时在壳外；无壳对照组中，浴分子占据「壳体本应所在的
        # 环带」（R>=9 起），两组初始体积占用一致，唯一差别是有无那一层冷壳。
        if self.double:
            bath_rmin = 17.5
        elif self.shell_formula:
            bath_rmin = 13.5
        else:
            bath_rmin = 9.0
        if self.bath_n_target:
            self._place_bath(self.bath_n_target, rmin=bath_rmin,
                             rmax=bath_rmin + 12.0)
        log("placed core=%d food=%d/%s shell_inner=%d outer=%d bath=%d live=%d"
            % (nc, nf, (nf1, nf2), len(self.shell_inner_ids),
               len(self.shell_outer_ids), self._live_role_count("bath"),
               len(self.live_mols())))

    def _live_role_count(self, role):
        s = {"core": self.core_ids, "food": self.food_ids,
             "shell": self.shell_ids, "bath": self.bath_ids}[role]
        return sum(1 for mid in s if not self.mols[mid]["dead"])

    # -- 基本判定 -----------------------------------------------------------
    def _is_core_mol(self, m):
        if m["dead"] or m["f"] != CORE_FORMULA:
            return False
        dr = abs(m["r"] - self.core_center[0])
        dc = abs(m["c"] - self.core_center[1])
        return max(dr, dc) <= CORE_ZONE

    def _is_frozen(self, m):
        # 核心设为固态（同 T90 主体），不参与移动/重力
        return self._is_core_mol(m)

    def _role_of(self, m):
        """core / food / shell / foreign / other。

        foreign = 攻击浴初始分子及其反应后代（bath_lineage）；
        other   = 内部反应产物等，不参与「外来攻击」统计。
        """
        if self._is_core_mol(m):
            return "core"
        if m["f"] in (FOOD1, FOOD2):
            return "food"
        mid = m["id"]
        if mid in self.shell_inner_ids or mid in self.shell_outer_ids:
            return "shell"
        if mid in self.bath_lineage:
            return "foreign"
        return "other"

    def ambient_T(self, t):
        return self.T_env

    # -- 逐拍接触统计 -------------------------------------------------------
    def _tick_contacts(self):
        fwd = ((0, 1), (1, 0), (1, 1), (1, -1))
        nfc = nfs = 0
        H, W = self.H, self.W
        for (r, c), mid in self.cell.items():
            m = self.mols[mid]
            c1 = self._role_of(m)
            for dr, dc in fwd:
                nr, nc = r + dr, c + dc
                if nr < 0 or nr >= H or nc < 0 or nc >= W:
                    continue
                nb = self.cell.get((nr, nc))
                if nb is None:
                    continue
                c2 = self._role_of(self.mols[nb])
                if c1 == c2:
                    continue
                pair = {c1, c2}
                if pair == {"core", "foreign"}:
                    nfc += 1
                elif pair == {"shell", "foreign"}:
                    nfs += 1
        self.contacts_fc += nfc
        self.contacts_fs += nfs

    # -- 反应政策 + 分类钩子 ------------------------------------------------
    def _try_react_group(self, group):
        """T90 主体假设：核心是惰性固态催化表面。

        核心只在与「外来攻击分子」（bath_lineage）接触时被侵蚀；核心与内部
        食物/内部产物之间的反应被抑制——否则 C3K3F2+C2K2→[C2K2F2,C3K3] 会
        让核心被自己的食物迅速溶解，与 T90「主体稳定、食物-食物缩合生长」的
        设定矛盾（见 docs/T93_SIM.md 建模假设）。
        """
        has_core = any(self._is_core_mol(self.mols[j]) for j in group)
        if has_core:
            has_foreign = any(self.mols[j]["id"] in self.bath_lineage
                              for j in group)
            if not has_foreign:
                return False
        return super()._try_react_group(group)

    def _apply_group(self, prods, group, formulas):
        cells_all = []
        for j in group:
            cells_all.extend(self.mols[j]["cells"])
        cr = sum(r for r, c in cells_all) / len(cells_all)
        cc = sum(c for r, c in cells_all) / len(cells_all)
        d = math.hypot(cr - self.core_center[0], cc - self.core_center[1])
        has_core = any(self._is_core_mol(self.mols[j]) for j in group)
        has_shell = any(self.mols[j]["id"] in self.shell_inner_ids
                        or self.mols[j]["id"] in self.shell_outer_ids
                        for j in group)
        has_foreign = any(self.mols[j]["id"] in self.bath_lineage
                          for j in group)
        pre_n = len(self.mols)
        # 壳外反应：产物只允许生成在膜外一侧，避免「产物瞬移穿膜」的假象
        self._spawn_min_r = R_INTERIOR if d > R_INTERIOR else 0.0
        ok = super()._apply_group(prods, group, formulas)
        self._spawn_min_r = 0.0
        if ok:
            new_ids = list(range(pre_n, len(self.mols)))
            if has_foreign:
                self.bath_lineage.update(new_ids)
            for nid in new_ids:
                if (self.mols[nid]["f"] == CORE_FORMULA
                        and self._is_core_mol(self.mols[nid])):
                    self.n_grown_core += 1
            if d <= R_INTERIOR:
                self.react_in += 1
            elif d <= R_SHELL_ZONE:
                self.react_shell += 1
            else:
                self.react_out += 1
            if has_core:
                self.react_core += 1
            if has_shell:
                self.react_shell_involved += 1
            if has_core and has_foreign:
                self.react_core_attack += 1
            if has_shell and has_foreign:
                self.react_shell_bath += 1
        return ok

    def _find_footprint(self, center, formula, reserved):
        """同 T85，但当反应质心在膜外时禁止把产物生成到膜内。

        T85 的产物放置是在质心 ±10 格内扫描第一个空位，反应发生在壳上时
        会随机把产物放到底膜内侧，形成「产物瞬移穿膜」的假象。这里加一个
        最小半径约束：膜外反应的产物只能落在膜外一侧。
        """
        t = self.ensure_type(formula)
        shp = t["shape"]
        r0, r1 = max(0, center[0] - 10), min(self.H, center[0] + 11)
        c0, c1 = max(0, center[1] - 10), min(self.W, center[1] + 11)
        cr, cc = self.core_center
        minr = self._spawn_min_r
        for rr in range(r0, r1):
            for cj in range(c0, c1):
                if minr > 0.0 and math.hypot(rr - cr, cj - cc) < minr:
                    continue
                cells = [(rr + dr, cj + dc) for dr, dc in shp]
                if not all(0 <= x < self.H and 0 <= y < self.W
                           for x, y in cells):
                    continue
                if any((x, y) in self.cell or (x, y) in reserved
                       for x, y in cells):
                    continue
                return cells
        return None

    # -- 一拍 ---------------------------------------------------------------
    def step(self):
        self.Tamb = self.T_env
        self.update_rho()
        ids = [i for i in range(len(self.mols)) if not self.mols[i]["dead"]]
        self.rng.shuffle(ids)
        for mid in ids:
            m = self.mols[mid]
            if m["dead"]:
                continue
            if self._is_frozen(m):
                continue
            t = self.types[m["f"]]
            st = t["tiers"]["state"]
            # 1) 连续重力
            gacc = m.get("gacc", 0.0) + self.grav * t["mass"]
            gsteps = int(gacc)
            m["gacc"] = gacc - gsteps
            for _ in range(min(gsteps, 3)):
                if not self._gravity_step(mid):
                    break
            # 2) 非对称三素力
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
        self.react_phase()
        self.rebuild_locks()
        self._tick_contacts()
        self.thermal.step(self)

    # -- 度量 ---------------------------------------------------------------
    def _rho_region(self, dmin, dmax):
        cr, cc = self.core_center
        vals = []
        for i in range(self.EH):
            for j in range(self.EW):
                wr = (i + 0.5) * self.H / self.EH
                wc = (j + 0.5) * self.W / self.EW
                d = math.hypot(wr - cr, wc - cc)
                if dmin <= d <= dmax:
                    vals.append(self.rho[i][j])
        return (sum(vals) / len(vals)) if vals else None

    def _coverage(self, core_cells, shell_ids_alive):
        H, W = self.H, self.W
        shell_cells = set()
        for mid in shell_ids_alive:
            for cell in self.mols[mid]["cells"]:
                shell_cells.add(cell)

        def covered(cell, dirs):
            for dr, dc in dirs:
                rr, cc2 = cell[0] + dr, cell[1] + dc
                if (rr, cc2) in shell_cells:
                    return True
            return False

        d4 = ((0, 0), (0, 1), (0, -1), (1, 0), (-1, 0))
        d8 = d4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))
        boundary = set()
        for (r, c) in core_cells:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc2 = r + dr, c + dc
                    if not (0 <= rr < H and 0 <= cc2 < W):
                        continue
                    if (rr, cc2) in core_cells:
                        continue
                    boundary.add((rr, cc2))
        if not boundary:
            return 0.0, 0.0, 0
        c4 = sum(1 for b in boundary if covered(b, d4)) / float(len(boundary))
        c8 = sum(1 for b in boundary if covered(b, d8)) / float(len(boundary))
        return round(c4, 4), round(c8, 4), len(boundary)

    def _angular_coverage(self, shell_ids_alive, nbins=36, rmin=5.0, rmax=18.0):
        cr, cc = self.core_center
        hit = [False] * nbins
        for mid in shell_ids_alive:
            m = self.mols[mid]
            dr, dc = m["r"] - cr, m["c"] - cc
            d = math.hypot(dr, dc)
            if d < rmin or d > rmax:
                continue
            ang = (math.atan2(dr, dc) + math.pi) / (2.0 * math.pi)
            hit[min(nbins - 1, int(ang * nbins))] = True
        return round(sum(hit) / float(nbins), 4)

    def _foreign_within(self, radius):
        cr, cc = self.core_center
        H, W = self.H, self.W
        dil = set()
        # 核心附近区域（不需要 core_cells 精确：用 CORE_ZONE 内的 A 分子单元格）
        core_cells = set()
        for m in self.live_mols():
            if self._is_core_mol(m):
                for cell in m["cells"]:
                    core_cells.add(cell)
        for (r, c) in core_cells:
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    rr, cc2 = r + dr, c + dc
                    if 0 <= rr < H and 0 <= cc2 < W:
                        dil.add((rr, cc2))
        n2 = 0
        for m in self.live_mols():
            if self._role_of(m) != "foreign":
                continue
            if any(cell in dil for cell in m["cells"]):
                n2 += 1
        return n2

    def measure(self, t):
        live = self.live_mols()
        core_mols = [m for m in live if self._is_core_mol(m)]
        core_cells = set()
        core_by_el = {}
        for m in core_mols:
            for cell in m["cells"]:
                core_cells.add(cell)
            for e, n in self.types[m["f"]]["comp"].items():
                core_by_el[e] = core_by_el.get(e, 0) + n
        shell_alive = [mid for mid in self.shell_ids if not self.mols[mid]["dead"]]
        shell_inner_alive = [mid for mid in self.shell_inner_ids
                             if not self.mols[mid]["dead"]]
        shell_outer_alive = [mid for mid in self.shell_outer_ids
                             if not self.mols[mid]["dead"]]
        shell_formulas = tuple(f for f in (self.shell_formula, self.outer_formula) if f)
        shell_formula_n = sum(1 for m in live if m["f"] in shell_formulas)
        cov4, cov8, n_bound = self._coverage(core_cells, shell_alive)
        cov_ang = self._angular_coverage(shell_alive) if shell_alive else 0.0
        # 「当前屏障」口径：按分子式统计（反应会替换分子 id，但壳物质可能仍在），
        # 且只统计位于环带附近（5~18 格）的该类分子，避免别处同式产物污染覆盖率。
        shell_fmols = [m for m in live if m["f"] in shell_formulas
                       and 5.0 <= math.hypot(m["r"] - self.core_center[0],
                                             m["c"] - self.core_center[1]) <= 18.0]
        f_ids = [m["id"] for m in shell_fmols]
        cov4f, cov8f, _ = self._coverage(core_cells, f_ids)
        cov_ang_f = self._angular_coverage(f_ids) if f_ids else 0.0

        # 壳质心与竖直分布（重力诊断，Lead 要求）
        sy = []
        for mid in shell_alive:
            m = self.mols[mid]
            sy.append(m["r"])
        if sy:
            shell_cy = round(sum(sy) / float(len(sy)), 2)
            hist = [0] * 11
            for r in sy:
                hist[min(10, r * 11 // self.H)] += 1
        else:
            shell_cy = None
            hist = [0] * 11

        # 壳的死亡/逃逸
        shell_loss = len(self.shell_ids) - len(shell_alive)
        shell_escape = sum(1 for mid in shell_alive
                           if math.hypot(self.mols[mid]["r"] - self.core_center[0],
                                         self.mols[mid]["c"] - self.core_center[1]) > 24.0)

        # τ 与 ρ_E
        taus = self.thermal.sample(self.core_center)
        rho_in = self._rho_region(0.0, RHO_IN_MAX)
        rho_out = self._rho_region(RHO_OUT_MIN, RHO_OUT_MAX)

        food1_n = sum(1 for m in live if m["f"] == FOOD1)
        food2_n = sum(1 for m in live if m["f"] == FOOD2)

        # 外来攻击分子（浴系）统计
        foreign_mols = [m for m in live if self._role_of(m) == "foreign"]
        foreign_min_r = None
        if foreign_mols:
            foreign_min_r = round(min(math.hypot(m["r"] - self.core_center[0],
                                                 m["c"] - self.core_center[1])
                                      for m in foreign_mols), 2)

        return {
            "t": t,
            "T_env": self.T_env,
            "n": len(live),
            "cells_used": self.n_cells_used,
            "core_n": len(core_mols),
            "core_by_element": {k: core_by_el[k] for k in sorted(core_by_el)},
            "core_cy": (round(sum(m["r"] for m in core_mols) / len(core_mols), 2)
                        if core_mols else None),
            "food1_n": food1_n,
            "food2_n": food2_n,
            "food_n": food1_n + food2_n,
            "shell_formula_n": shell_formula_n,
            "shell_alive": len(shell_alive),
            "shell_inner_alive": len(shell_inner_alive),
            "shell_outer_alive": len(shell_outer_alive),
            "shell_loss": shell_loss,
            "shell_escape": shell_escape,
            "shell_cy": shell_cy,
            "shell_y_hist": hist,
            "coverage4": cov4,
            "coverage8": cov8,
            "cov_angular": cov_ang,
            "coverage4_f": cov4f,
            "coverage8_f": cov8f,
            "cov_angular_f": cov_ang_f,
            "n_boundary": n_bound,
            "foreign_within2": self._foreign_within(2),
            "foreign_alive": len(foreign_mols),
            "foreign_min_r": foreign_min_r,
            "contacts_foreign_core_cum": self.contacts_fc,
            "contacts_foreign_shell_cum": self.contacts_fs,
            "core_involved_react_cum": self.react_core,
            "core_attack_react_cum": self.react_core_attack,
            "shell_bath_react_cum": self.react_shell_bath,
            "grown_core_cum": self.n_grown_core,
            "react_in_cum": self.react_in,
            "react_shellzone_cum": self.react_shell,
            "react_out_cum": self.react_out,
            "react_shellinvolved_cum": self.react_shell_involved,
            "rho_in": round(rho_in, 4) if rho_in is not None else None,
            "rho_out": round(rho_out, 4) if rho_out is not None else None,
            "gate_in": round(0.15 + 0.85 * rho_in, 4) if rho_in is not None else None,
            "gate_out": round(0.15 + 0.85 * rho_out, 4) if rho_out is not None else None,
            "tau_core": taus["core"],
            "tau_in": taus["in"],
            "tau_shell": taus["shell"],
            "tau_out": taus["out"],
            "tau_edge": taus["edge"],
            "n_react_total": self.n_react,
            "n_complete": self.n_complete,
            "n_incomplete": self.n_incomplete,
            "n_none": self.n_none,
            "n_decomp": self.n_decomp,
            "n_react_fail": self.n_react_fail,
            "n_new_species": len(self.new_species),
        }

    # -- 终态 ---------------------------------------------------------------
    def final_state(self):
        mols = []
        for m in self.live_mols():
            role = self._role_of(m)
            if role == "foreign":
                role = "bath" if m["id"] in self.bath_ids else "other"
            mols.append([m["r"], m["c"], m["f"], role])
        return {"mols": mols, "n": len(mols), "cells_used": self.n_cells_used}


# ---------------------------------------------------------------------------
ARMS = [
    # name,                 T_env, grav, shell,  double, bath,  note
    dict(name="no_shell_hot", T_env=400.0, grav=0.0, shell=None, bath=True,
         note="对照：无冷壳，400°C 热浴"),
    dict(name="shell_OXC_hot", T_env=400.0, grav=0.0, shell=SHELL_OXC, bath=True,
         note="主臂：OXC 冷壳（重·固·冷），400°C 热浴，G=0"),
    dict(name="shell_C2_hot", T_env=400.0, grav=0.0, shell=SHELL_C2, bath=True,
         note="C2 低温壳（轻·气档），400°C 热浴，G=0"),
    dict(name="shell_X2C2_hot", T_env=400.0, grav=0.0, shell=SHELL_X2C2, bath=True,
         note="X2C2 轻·固·冷壳，400°C 热浴，G=0"),
    dict(name="shell_OXC_cold", T_env=20.0, grav=0.0, shell=SHELL_OXC, bath=True,
         note="冷环境对照：OXC 壳 + 20°C，G=0"),
    dict(name="double_OXC_OP_hot", T_env=400.0, grav=0.0, shell=SHELL_OXC,
         double=True, bath=True,
         note="双层：内 OXC + 外 OP（高 D 层），400°C 热浴，G=0"),
    dict(name="selfasm_OXC_hot_nobath", T_env=400.0, grav=0.0, shell=SHELL_OXC,
         bath=False, note="无攻击浴：壳能否自发闭合/维持，400°C，G=0"),
    dict(name="shell_OXC_hot_g030", T_env=400.0, grav=0.30, shell=SHELL_OXC,
         bath=True, note="T87 连续重力 G=0.30：重壳重力坍塌对照"),
    dict(name="shell_OXC_hot_g002", T_env=400.0, grav=0.02, shell=SHELL_OXC,
         bath=True, note="低重力 G=0.02：微重力环境对照"),
]


def arm_kwargs(arm, quick=False, ticks_override=None):
    kw = dict(T_env=arm["T_env"], grav=arm["grav"],
              shell=arm["shell"], double=arm.get("double", False),
              bath=arm["bath"])
    if quick:
        kw.update(dict(W=120, H=80, ticks=60, core_center=(52, 60),
                       core_n=12, food1=12, food2=12, shell_n=60,
                       outer_n=30, bath_n=90))
        if not kw["shell"]:
            kw["shell_n"] = 0
        if not kw["double"]:
            kw["outer_n"] = 0
    if ticks_override:
        kw["ticks"] = int(ticks_override)
    return kw


def _nearest(series, target, key):
    """取最接近 target 拍的样本值（series 每 measure_every 拍一条）。"""
    best = None
    bd = None
    for s in series:
        d = abs(s["t"] - target)
        if bd is None or d < bd:
            bd, best = d, s
    return best.get(key) if best else None


def _first_reach(series, key, thresh):
    for s in series:
        v = s.get(key)
        if v is not None and v >= thresh:
            return s["t"]
    return None


def summarize(w, series, cfg, runtime_s):
    first = series[0]
    last = series[-1]
    core0 = first["core_n"]
    coreN = last["core_n"]
    # 只看 0~200 拍（壳尚未被反应大量消耗）的对比窗口
    window = [s for s in series if s["t"] <= 200]
    tau_in_w = (round(sum(s["tau_in"] for s in window) / len(window), 2)
                if window and window[0]["tau_in"] is not None else None)
    summary = {
        "name": cfg["name"],
        "note": cfg.get("note", ""),
        "T_env": cfg["T_env"],
        "grav": cfg["grav"],
        "shell": cfg["shell"],
        "double": cfg.get("double", False),
        "bath": cfg["bath"],
        "runtime_s": round(runtime_s, 2),
        "n0": first["n"],
        "n_final": last["n"],
        "core_n0": core0,
        "core_n_final": coreN,
        "core_retention": round(coreN / max(1, core0), 4),
        "core_by_element_final": last["core_by_element"],
        "food_n0": first["food_n"],
        "food_n_final": last["food_n"],
        "shell_alive0": first["shell_alive"],
        "shell_alive_final": last["shell_alive"],
        "shell_formula_n_final": last["shell_formula_n"],
        "shell_loss": last["shell_loss"],
        "shell_escape_final": last["shell_escape"],
        "shell_cy0": first["shell_cy"],
        "shell_cy_final": last["shell_cy"],
        "coverage4_final": last["coverage4"],
        "coverage8_final": last["coverage8"],
        "cov_angular0": first["cov_angular"],
        "cov_angular_final": last["cov_angular"],
        "coverage4_final_f": last.get("coverage4_f"),
        "coverage8_final_f": last.get("coverage8_f"),
        "cov_angular_final_f": last.get("cov_angular_f"),
        "cov_angular_f_min": min((s.get("cov_angular_f") or 0.0)
                                 for s in series),
        "foreign_within2_final": last["foreign_within2"],
        "foreign_within2_max": max(s["foreign_within2"] for s in series),
        "foreign_alive_final": last["foreign_alive"],
        "foreign_min_r_final": last["foreign_min_r"],
        "contacts_foreign_core_total": last["contacts_foreign_core_cum"],
        "contacts_foreign_shell_total": last["contacts_foreign_shell_cum"],
        "core_involved_react_total": last["core_involved_react_cum"],
        "core_attack_react_total": last["core_attack_react_cum"],
        "shell_bath_react_total": last["shell_bath_react_cum"],
        "grown_core_total": last["grown_core_cum"],
        "react_in_total": last["react_in_cum"],
        "react_shellzone_total": last["react_shellzone_cum"],
        "react_out_total": last["react_out_cum"],
        "react_shellinvolved_total": last["react_shellinvolved_cum"],
        "react_total": last["n_react_total"],
        "rho_in_final": last["rho_in"],
        "rho_out_final": last["rho_out"],
        "gate_in_final": last["gate_in"],
        "gate_out_final": last["gate_out"],
        "tau_in0": first["tau_in"],
        "tau_in_final": last["tau_in"],
        "tau_in_mean_0_200": tau_in_w,
        "tau_shell_final": last["tau_shell"],
        "tau_out_final": last["tau_out"],
        "tau_edge_final": last["tau_edge"],
        "tau_in_minus_env": (round(last["tau_in"] - cfg["T_env"], 1)
                             if last["tau_in"] is not None else None),
        "tau_core0": first.get("tau_core"),
        "tau_core_final": last.get("tau_core"),
        "tau_core_minus_env": (round(last["tau_core"] - cfg["T_env"], 1)
                               if last.get("tau_core") is not None else None),
        "tau_core_in_at": {("t%d" % tt): _nearest(series, tt, "tau_core")
                           for tt in (50, 100, 200, 300, 400, 600)},
        "tau_in_at": {("t%d" % tt): _nearest(series, tt, "tau_in")
                      for tt in (50, 100, 200, 300, 400, 600)},
        "warm_delay_core200": _first_reach(series, "tau_core", 200.0),
        "warm_delay_core300": _first_reach(series, "tau_core", 300.0),
        "warm_delay_core350": _first_reach(series, "tau_core", 350.0),
        "warm_delay_in200": _first_reach(series, "tau_in", 200.0),
        "warm_delay_in300": _first_reach(series, "tau_in", 300.0),
        "warm_delay_in350": _first_reach(series, "tau_in", 350.0),
        "n_react_fail": last["n_react_fail"],
        "n_new_species": last["n_new_species"],
        "elements_final": w.elements(),
    }
    return summary


def run_arm(arm, quick=False, outdir=BASE, seed=SEED, measure_every=10,
            extra=None, ticks_override=None):
    t0 = time.time()
    cfg = dict(arm)
    kw = arm_kwargs(arm, quick=quick, ticks_override=ticks_override)
    if quick:
        kw["W"] = 120
        kw["H"] = 80
    w = MembraneWorld(seed=seed, **kw)
    log("arm %s start: W=%d H=%d T_env=%.0f grav=%.2f shell=%s double=%s bath=%s "
        "live=%d ticks=%d p_react=%.4f"
        % (arm["name"], w.W, w.H, w.T_env, w.grav, w.shell_formula,
           w.double, arm["bath"], len(w.live_mols()), kw["ticks"], w.p_react))
    w.measure_every = measure_every
    el0 = w.elements()
    series = [w.measure(0)]
    for t in range(1, kw["ticks"] + 1):
        w.t = t
        w.step()
        if t % measure_every == 0 or t == kw["ticks"]:
            s = w.measure(t)
            series.append(s)
            if t % (measure_every * 5) == 0 or t == kw["ticks"]:
                log("  %s t=%4d n=%4d core=%3d shell=%3d cov_ang=%.2f "
                    "fw2=%3d fc=%5d fr_in=%4d fr_out=%4d tau_in=%6.1f "
                    "tau_out=%6.1f (%.1fs)"
                    % (arm["name"], t, s["n"], s["core_n"], s["shell_alive"],
                       s["cov_angular"], s["foreign_within2"],
                       s["contacts_foreign_core_cum"], s["react_in_cum"],
                       s["react_out_cum"],
                       -999 if s["tau_in"] is None else s["tau_in"],
                       -999 if s["tau_out"] is None else s["tau_out"],
                       time.time() - t0))
    el1 = w.elements()
    runtime = time.time() - t0
    cfg_full = dict(cfg)
    cfg_full.update({k: v for k, v in kw.items()
                     if k in ("W", "H", "ticks", "core_center", "core_n",
                              "food1", "food2", "shell_n", "outer_n", "bath_n")})
    cfg_full["p_react"] = w.p_react
    cfg_full["cap"] = w.cap
    cfg_full["seed"] = seed
    cfg_full["quick"] = quick
    cfg_full["thermal"] = {
        "block": w.thermal.block, "grid": [w.thermal.bw, w.thermal.bh],
        "kappa0": KAPPA0, "eta_env": ETA_ENV, "lambda_b": LAMBDA_B,
        "T_init": T_INIT, "r_init_hot": R_INIT_HOT,
    }
    summary = summarize(w, series, cfg_full, runtime)
    summary["elements0"] = el0
    summary["elements1"] = el1
    summary["conservation_ok"] = (el0 == el1)
    out = {
        "config": cfg_full,
        "summary": summary,
        "series": series,
        "final_state": w.final_state(),
    }
    path = os.path.join(outdir, "t93_%s.json" % arm["name"])
    atomic_json(path, out)
    log("arm %s done: core %d->%d shell %d->%d fw2=%d fc=%d tau_in=%.1f "
        "tau_out=%.1f react=%d in=%d out=%d runtime=%.1fs -> %s"
        % (arm["name"], summary["core_n0"], summary["core_n_final"],
           summary["shell_alive0"], summary["shell_alive_final"],
           summary["foreign_within2_final"],
           summary["contacts_foreign_core_total"],
           summary["tau_in_final"] or 0, summary["tau_out_final"] or 0,
           summary["react_total"], summary["react_in_total"],
           summary["react_out_total"], runtime, os.path.basename(path)))
    return summary, series, path


def main(argv=None):
    ap = argparse.ArgumentParser(description="T93 冷壳保护膜动态仿真")
    ap.add_argument("--quick", action="store_true", help="小规模快速验证")
    ap.add_argument("--arms", default="", help="逗号分隔臂名，默认全部")
    ap.add_argument("--ticks", type=int, default=None)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--measure-every", type=int, default=10)
    ap.add_argument("--skip-render", action="store_true")
    args = ap.parse_args(argv)

    outdir = args.outdir
    if outdir is None:
        outdir = tempfile.mkdtemp(prefix="t93_quick_") if args.quick else BASE
    os.makedirs(outdir, exist_ok=True)
    log("=== T93 start quick=%s arms=%s outdir=%s pid=%d ==="
        % (args.quick, args.arms or "ALL", outdir, os.getpid()))
    t_all = time.time()
    arms = ARMS
    if args.arms:
        wanted = [x.strip() for x in args.arms.split(",") if x.strip()]
        arms = [a for a in arms if a["name"] in wanted]
        if not arms:
            log("no arm matched %s" % wanted)
            return 2
    if args.ticks:
        log("ticks override=%d" % args.ticks)
    main_obj = {
        "config": {
            "engine": "T93 热环境 + 多分子核心 + C 类低温冷壳保护膜"
                      "（继承 t87_env_asym.AsymWorld）",
            "W": 160, "H": 110, "seed": args.seed,
            "core_formula": CORE_FORMULA, "food": [FOOD1, FOOD2],
            "bath_pool": BATH_POOL, "p_react": P_REACT, "cap": CAP,
            "structure": {"core_n": 24, "food": [40, 40],
                          "shell_n": 300, "shell_rin": 8.2,
                          "shell_rout": 12.4,
                          "outer": [SHELL_OP, 90, 12.6, 15.6],
                          "bath_n": 360},
            "measure_every": args.measure_every,
            "thermal": {"grid": [160 // THERMAL_BLOCK, 110 // THERMAL_BLOCK],
                        "block": THERMAL_BLOCK, "kappa0": KAPPA0,
                        "eta_env": ETA_ENV, "lambda_b": LAMBDA_B,
                        "T_init": T_INIT, "r_init_hot": R_INIT_HOT},
            "gravity_note": "主臂 G=0（微重力/支撑表面）；G=0.30 为 T87 语义；"
                            "G=0.02 为低重力对照",
            "quick": args.quick,
        },
        "arms": [],
        "series": {},
        "runtime_s": None,
    }
    arm_files = {}
    for arm in arms:
        try:
            summary, series, path = run_arm(
                arm, quick=args.quick, outdir=outdir, seed=args.seed,
                measure_every=args.measure_every,
                ticks_override=args.ticks)
        except Exception:
            log("ARM %s FAILED:\n%s" % (arm["name"], traceback.format_exc()))
            summary = {"name": arm["name"], "failed": True,
                       "error": traceback.format_exc()[-2000:]}
            series = []
            path = None
        main_obj["arms"].append(summary)
        main_obj["series"][arm["name"]] = series
        arm_files[arm["name"]] = path
        main_obj["runtime_s"] = round(time.time() - t_all, 2)
        # 逐臂落盘（主文件也每臂更新，崩溃安全）
        atomic_json(os.path.join(outdir, "t93_membrane.json"), main_obj)
        log("main json updated (%d arms, %.1fs total)"
            % (len(main_obj["arms"]), time.time() - t_all))
    log("=== T93 done in %.1fs: %s ==="
        % (time.time() - t_all, os.path.join(outdir, "t93_membrane.json")))
    if args.quick:
        log("quick outdir=%s" % outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
