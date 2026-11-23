#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T94-C 环境分支：用元素丰度定义环境族，评估其对生命候选的危险度与生存条件。

设计要点（与 T88/T92/T93/T94 口径一致）：
  * 不修改内核与任何既有文件；只读目录 t4_catalog_all_validated.json（84,225 条）。
  * 放弃"固定攻击浴"：环境 = 一个元素丰度向量，环境分子池按该丰度从目录中
    IPF 配平后加权有放回采样（n_pool 个分子式）得到。
  * 温度一律取 t94_config.DEFAULT_PARAMS：T0=200°C → T_end=0°C，600 拍指数降温，
    env_coupling=0.5；分子对局部温度 T_loc=(h_A+h_B+0.5*T_env)/(2+0.5)。
  * 危险度三指标：环境分子 D>0 占比、pair-w 分布（strong/weak/none/repel）、
    与候选的"反应温度窗口"（resolve 规则 1~11 口径 + 降温窗口内活跃拍数）。
  * 生存矩阵：可存活 / 需膜 / 不可存活（判据写入 docs/T94_ENV.md，属于模型内约定）。

用法：
  python t94_env.py            # 全量（约 60~120s）
  python t94_env.py --quick    # 快速自检（约 10~20s）
产物：
  t94_envmap.json、images/t94_envmap.png（1600×1000，中文标注）
"""
import argparse
import bisect
import json
import math
import os
import random
import statistics
import sys
import time
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import t94_config as CFG  # noqa: E402
from alchemy import three_su as TS  # noqa: E402
from alchemy import attrs as AT  # noqa: E402
import natural_engine as NE  # noqa: E402

CATALOG_FILE = os.path.join(BASE, 't4_catalog_all_validated.json')
JSON_DEFAULT = os.path.join(BASE, 't94_envmap.json')
PNG_DEFAULT = os.path.join(BASE, 'images', 't94_envmap.png')
FONT_PATH = r'C:\Windows\Fonts\msyh.ttc'
FONT_FALLBACK = r'C:\Windows\Fonts\simhei.ttf'

ELEMS = ['O', 'X', 'C', 'P', 'W', 'L', 'K', 'A', 'F']
ELEM_COLORS = {
    'O': (31, 119, 180), 'X': (148, 103, 189), 'C': (140, 86, 75),
    'P': (227, 119, 194), 'W': (127, 127, 127), 'L': (188, 189, 34),
    'K': (23, 190, 207), 'A': (255, 127, 14), 'F': (214, 39, 40),
}
STATUS_COLORS = {
    '可存活': (76, 175, 80),
    '需膜': (255, 193, 7),
    '不可存活': (211, 47, 47),
    '需外源膜': (255, 152, 0),
    '无法判定': (158, 158, 158),
}

# ---------------------------------------------------------------------------
# 环境族定义（元素丰度向量，和为 1）
# ---------------------------------------------------------------------------
ENVS = [
    {'id': 'E1', 'name': '富 F 环境',
     'target': {'O': .20, 'X': .05, 'C': .12, 'P': .03, 'W': .02,
                'L': .08, 'K': .10, 'A': .10, 'F': .30},
     'basis': 'T88 B3_OFL/T91 富 F 方向'},
    {'id': 'E2', 'name': '富 O/X 环境',
     'target': {'O': .35, 'X': .30, 'C': .12, 'K': .08, 'A': .06,
                'F': .05, 'L': .02, 'P': .01, 'W': .01},
     'basis': 'T88 B3_OXC / T92 3 元 OXC 群系'},
    {'id': 'E3', 'name': '富 P/W/L 环境',
     'target': {'O': .20, 'X': .12, 'C': .08, 'P': .16, 'W': .16,
                'L': .16, 'K': .06, 'A': .04, 'F': .02},
     'basis': 'T93 斥力族（P/W/L）富集'},
    {'id': 'E4', 'name': 'O/X/C 均衡环境',
     'target': {'O': 1 / 3, 'X': 1 / 3, 'C': 1 / 3},
     'basis': 'T88 B3_OXC（等丰度）'},
    {'id': 'E5', 'name': '富 K/A 环境',
     'target': {'O': .15, 'X': .10, 'C': .08, 'K': .28, 'A': .28,
                'F': .06, 'L': .03, 'P': .01, 'W': .01},
     'basis': 'T88 B5_OXKAF / T93 冷壳族方向'},
    {'id': 'E6', 'name': '九元素均衡环境',
     'target': {e: 1 / 9 for e in ELEMS},
     'basis': 'T88 B9_all9'},
    {'id': 'E7', 'name': 'O/F/L 均衡环境',
     'target': {'O': 1 / 3, 'F': 1 / 3, 'L': 1 / 3},
     'basis': 'T88 B3_OFL'},
    {'id': 'E8', 'name': 'O/X/K/F 均衡环境',
     'target': {'O': .25, 'X': .25, 'K': .25, 'F': .25},
     'basis': 'T88 B4_OXKF'},
]

# ---------------------------------------------------------------------------
# 生命候选
# ---------------------------------------------------------------------------
CANDS = [
    {'id': 'C3K3F2', 'name': '主体·三素冷壳核', 'role': 'body',
     'note': 'T90 生长主体（8 原子 5 位点）'},
    {'id': 'XK2F4', 'name': '自复制候选·7 原子富 F', 'role': 'replicator',
     'note': 'T91 第 3 组主体'},
    {'id': 'P2W', 'name': '高 D 膜分子', 'role': 'membrane',
     'note': 'P/W 族高 D，D≈2.667（T93 斥力族）'},
    {'id': 'O10XK4', 'name': '完美冷壳参照', 'role': 'shell',
     'note': 'T93 最佳冷壳（D=0, η=0.039, w_self=2.424）'},
    {'id': 'OXC', 'name': '含 C 三素对照', 'role': 'control',
     'note': 'T93 含 C 冷壳小分子'},
]

# T93 保温模型 A 参数（直接复用，不改口径）
KAPPA0 = 0.35
LAM = 0.03
ETA_ENV = 0.35
ETA_CORE = 0.35
C_CORE = 60.0
T_CORE = 4.0

# 生存判据（模型内约定，见 docs/T94_ENV.md §4）
P_COLD_BAD = 0.50
P_COLD_MEMBRANE = 0.10
DUR_MEMBRANE = 0.80
SHELL_SUPPLY_MIN = 0.05
D_MAX = 3

_CAT = {}
_COUNTS = {}
_MOLS = {}
_SCORES = {}
_PAIRW = {}
_RES = {}
_SHELL = {}

P = dict(CFG.DEFAULT_PARAMS)


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def counts(formula):
    c = _COUNTS.get(formula)
    if c is None:
        raw = TS.parse_formula(formula)
        c = {e: int(v) for e, v in raw.items() if v}
        _COUNTS[formula] = c
    return c


def natoms(formula):
    return sum(counts(formula).values())


def heat(formula):
    hw = P['heat_w']
    return sum(hw.get(e, 0.0) * n for e, n in counts(formula).items())


def scores(formula):
    s = _SCORES.get(formula)
    if s is None:
        s = TS.scores(counts(formula))
        _SCORES[formula] = s
    return s


def mol(formula):
    m = _MOLS.get(formula)
    if m is None:
        m = NE.mol_from_record(_CAT[formula])
        _MOLS[formula] = m
    return m


def pairw(cand_f, env_f):
    key = (cand_f, env_f)
    v = _PAIRW.get(key)
    if v is None:
        v = TS.pair_force(counts(cand_f), counts(env_f), d=1)
        _PAIRW[key] = v
    return v


def load_catalog():
    t0 = time.time()
    with open(CATALOG_FILE, encoding='utf-8') as fh:
        raw = json.load(fh)
    if isinstance(raw, dict):
        if 'records' in raw:
            raw = raw['records']
        else:  # 兜底：取第一层里的 list
            raw = next(v for v in raw.values() if isinstance(v, list))
    out = {}
    for r in raw:
        f = r.get('formula')
        if f:
            out[f] = r
    print('[catalog] %d 条，用时 %.2fs' % (len(out), time.time() - t0))
    return out


def schedule_T(t):
    return CFG.schedule_T(t, T0=P['T0'], T_end=P['T_end'],
                         cool_ticks=P['cool_ticks'], plateau=P['plateau'])


def T_loc(h_pair, T_env):
    ec = P['env_coupling']
    return (h_pair + ec * T_env) / (2.0 + ec)


def ticks_for(T_thr, h_pair):
    """降温窗口内反应活跃拍数（0..cool_ticks）。"""
    if T_thr is None:
        return 0.0
    ct = float(P['cool_ticks'])
    t0, te = float(P['T0']), float(P['T_end'])
    ec = P['env_coupling']
    cold_local = T_loc(h_pair, te)
    if T_thr <= cold_local:
        return ct
    need = (T_thr * (2.0 + ec) - h_pair) / ec  # 需要的 T_env
    if need >= t0:
        return 0.0
    if need <= te:
        return ct
    if te == 0.0:
        t = -ct / 6.0 * math.log(need / t0)
    else:
        t = -ct / 6.0 * math.log((need - te) / (t0 - te))
    return max(0.0, min(ct, t))


def resolve_type(cf, ef, T):
    key = (cf, ef, round(T, 4))
    v = _RES.get(key)
    if v is None:
        v = NE.resolve([mol(cf), mol(ef)], T)['type']
        _RES[key] = v
    return v


def react_at(cf, ef, T):
    return resolve_type(cf, ef, T) != 'none'


def beta(cf, ef):
    """反应剖面：是否反应、最小反应阈值温度、降温窗口活跃拍数。"""
    mc, me = mol(cf), mol(ef)
    h = heat(cf) + heat(ef)
    peak = T_loc(h, schedule_T(0.0))
    cold_local = T_loc(h, float(P['T_end']))
    if not react_at(cf, ef, peak):
        return {'react_peak': False, 'react_cold': False,
                'T_thr': None, 'ticks': 0.0, 'peak_T': peak,
                'cold_T': cold_local, 'h': h}

    cold = react_at(cf, ef, cold_local)
    if react_at(cf, ef, 0.0):
        t_thr = 0.0
    else:
        lo, hi = 0.0, peak
        for _ in range(14):
            mid = 0.5 * (lo + hi)
            if react_at(cf, ef, mid):
                hi = mid
            else:
                lo = mid
        t_thr = hi
    ticks = ticks_for(t_thr, h)
    return {'react_peak': True, 'react_cold': cold, 'T_thr': t_thr,
            'ticks': ticks, 'peak_T': peak, 'cold_T': cold_local, 'h': h}


# ---------------------------------------------------------------------------
# 环境池构造：IPF 权重 + 加权有放回采样
# ---------------------------------------------------------------------------
def ipf_weights(species, want, iters=250, damp=0.5):
    """species: [(formula, counts, natoms)]；want: 元素目标份额（和≈1）。"""
    n = len(species)
    w = [1.0] * n
    keys = [e for e in ELEMS if e in want]
    tot = sum(want[e] for e in keys)
    want = {e: want[e] / tot for e in keys}
    for _ in range(iters):
        cur = {e: 0.0 for e in keys}
        for i, (f, c, ni) in enumerate(species):
            wi = w[i]
            if wi:
                for e, k in c.items():
                    if e in cur:
                        cur[e] += wi * k
        fac = {e: want[e] / cur[e] if cur[e] > 0 else 1.0 for e in keys}
        new = []
        for i, (f, c, ni) in enumerate(species):
            prod = 1.0
            for e, k in c.items():
                if e in fac:
                    prod *= fac[e] ** (k / ni)
            new.append(max(w[i] * (prod ** damp), 1e-12))
        s = sum(new)
        w = [x * n / s for x in new]
    return w


def build_env_pool(env, n_pool, seed, iters=250):
    target = {e: v for e, v in env['target'].items() if v > 0}
    support = set(target)
    species = []
    for f in _CAT:
        c = counts(f)
        ni = sum(c.values())
        if ni < 2 or ni > 8:
            continue
        if not set(c) <= support:
            continue
        species.append((f, c, ni))
    species.sort(key=lambda x: x[0])
    w = ipf_weights(species, target, iters=iters)
    rng = random.Random(seed)
    cum, acc = [], 0.0
    for x in w:
        acc += x
        cum.append(acc)
    pool = []
    for _ in range(n_pool):
        r = rng.random() * acc
        pool.append(species[bisect.bisect_left(cum, r)][0])
    return pool, species, w


def pool_stats(env, pool):
    """池的元素份额与分子式分布。"""
    cnt = Counter(pool)
    total_atoms = 0
    elem_sum = {e: 0 for e in ELEMS}
    heat_sum = 0.0
    dpos = 0
    a_sum = 0.0
    d_sum = 0.0
    w_self_sum = 0.0
    for f in pool:
        c = counts(f)
        ni = sum(c.values())
        total_atoms += ni
        for e, k in c.items():
            elem_sum[e] += k
        heat_sum += heat(f)
        sc = scores(f)
        if sc['D'] > 0:
            dpos += 1
        a_sum += sc['A']
        d_sum += sc['D']
        w_self_sum += (2.5 * sc['A'] - 0.5 * sc['D']) / 3.0
    n = len(pool)
    share = {e: (elem_sum[e] / total_atoms if total_atoms else 0.0) for e in ELEMS}
    maxdev = max(abs(share[e] - env['target'].get(e, 0.0)) for e in ELEMS)
    return {
        'n_pool': n,
        'n_species': len(cnt),
        'atoms_per_mol': total_atoms / n,
        'achieved_share': {e: round(share[e], 4) for e in ELEMS},
        'max_share_dev': round(maxdev, 4),
        'heat_mean': heat_sum / n,
        'heat_pos_share': sum(1 for f in pool if heat(f) > 0) / n,
        'dpos_share': dpos / n,
        'A_mean': a_sum / n,
        'D_mean': d_sum / n,
        'w_self_mean': w_self_sum / n,
        'top_species': [[f, k, round(k / n, 4)] for f, k in cnt.most_common(8)],
    }


def shell_stats(pool):
    """冷壳料可得性：Tdeg=0、物态固、温度冷、w_self>=1、k_raw>=1（T93 口径）。"""
    cnt = Counter(pool)
    n = len(pool)
    share = 0.0
    best = None
    n_shell_species = 0
    for f, k in cnt.items():
        rec = _CAT[f]
        atoms = rec['atoms']
        edges = rec.get('edges')
        c = counts(f)
        ni = len(atoms)
        nL, nF = c.get('L', 0), c.get('F', 0)
        nO, nK, nP = c.get('O', 0), c.get('K', 0), c.get('P', 0)
        tdeg = nL + 2 * nF
        rho = (3 * nO + 2 * nK + nP) / (3.0 * ni)
        eta = (1 - rho) * (tdeg + 1) / (tdeg + 4)
        sc = scores(f)
        w_self = (2.5 * sc['A'] - 0.5 * sc['D']) / 3.0
        attrs = AT.molecule_attrs(atoms, edges)
        ttemp = AT.tier_name(attrs['temperature'], 'temperature')
        tstate = AT.tier_name(attrs['state'], 'state')
        k_raw = len(AT.skeleton_units(atoms, edges))
        if tdeg == 0 and ttemp == '冷' and tstate == '固' and w_self >= 1.0 and k_raw >= 1:
            n_shell_species += 1
            share += k / n
            cand = {'formula': f, 'eta': round(eta, 4), 'w_self': round(w_self, 3),
                    'k_raw': k_raw, 'count': k,
                    'mass': AT.tier_name(attrs['mass'], 'mass'),
                    'state': tstate, 'temperature': ttemp}
            if best is None or w_self > best['w_self']:
                best = cand
    return {'shell_share': round(share, 4), 'n_shell_species': n_shell_species,
            'best_shell': best}


# ---------------------------------------------------------------------------
# 危险度：pair-w 分布 + 反应温度窗口
# ---------------------------------------------------------------------------
def pairw_stats(cand_f, pool):
    cnt = {'strong': 0, 'weak': 0, 'none': 0, 'repel': 0}
    ws = []
    for f in pool:
        w = pairw(cand_f, f)['w']
        cls = TS.classify(w)
        cnt[cls] += 1
        ws.append(w)
    n = len(ws)
    return {
        'strong': cnt['strong'], 'weak': cnt['weak'],
        'none': cnt['none'], 'repel': cnt['repel'],
        'share': {k: round(v / n, 4) for k, v in cnt.items()},
        'w_mean': statistics.fmean(ws),
        'w_min': min(ws), 'w_max': max(ws),
    }


def danger(cand_f, pool, nsample, seed):
    rng = random.Random(seed)
    k = min(nsample, len(pool))
    idx = rng.sample(range(len(pool)), k)
    sample = [pool[i] for i in idx]
    n_peak = n_cold = 0
    ticks = []
    tthrs = []
    for ef in sample:
        p = beta(cand_f, ef)
        if p['react_peak']:
            n_peak += 1
        if p['react_cold']:
            n_cold += 1
        ticks.append(p['ticks'])
        if p['T_thr'] is not None:
            tthrs.append(p['T_thr'])
    dur = statistics.fmean(ticks) / float(P['cool_ticks'])
    return {
        'n_sample': k,
        'p_react_peak': n_peak / k,
        'p_react_cold': n_cold / k,
        'ticks_mean': statistics.fmean(ticks),
        'ticks_max': max(ticks),
        'dur': dur,
        'T_thr_median': statistics.median(tthrs) if tthrs else None,
        'T_thr_min': min(tthrs) if tthrs else None,
        'T_thr_max': max(tthrs) if tthrs else None,
        'react_any': n_peak > 0,
    }


def status_from_metrics(m):
    if m['p_react_cold'] >= P_COLD_BAD:
        return '不可存活'
    if m['p_react_cold'] >= P_COLD_MEMBRANE or m['dur'] >= DUR_MEMBRANE:
        return '需膜'
    return '可存活'


# ---------------------------------------------------------------------------
# T93 保温模型 A
# ---------------------------------------------------------------------------
def kappa(e1, e2):
    return KAPPA0 * math.sqrt(e1 * e2)


def series_R(eta_s, d):
    if d <= 0:
        return 1.0 / kappa(ETA_CORE, ETA_ENV)
    return (1.0 / kappa(ETA_CORE, eta_s) + (d - 1) / kappa(eta_s, eta_s)
            + 1.0 / kappa(eta_s, ETA_ENV))


def t_in(Tenv, eta_s, d, tcore=T_CORE):
    nh = LAM * C_CORE * series_R(eta_s, d)
    return (Tenv + nh * tcore) / (1.0 + nh)


def d_min(eta_s, tenv=200.0, tcore=T_CORE, target=10.0, maxd=6):
    for d in range(1, maxd + 1):
        if t_in(tenv, eta_s, d, tcore) <= target:
            return d
    return None


def membrane_status(env_stat, core_heat):
    """主体+本地膜：本地壳料是否可得且足够致密。"""
    best = env_stat['best_shell']
    if not best:
        return '不可存活', '无本地冷壳料'
    dm = d_min(best['eta'], 200.0, core_heat)
    if dm is None or dm > D_MAX:
        return '不可存活', '本地壳 η=%.3f 需 %s 层>%d' % (best['eta'], dm, D_MAX)
    if env_stat['shell_share'] >= SHELL_SUPPLY_MIN:
        return '可存活', '本地壳 %s d=%d（供给 %.1f%%）' % (
            best['formula'], dm, 100 * env_stat['shell_share'])
    return '需外源膜', '本地壳 %s d=%d，但供给仅 %.1f%%' % (
        best['formula'], dm, 100 * env_stat['shell_share'])


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run(args):
    global _CAT
    t_start = time.time()
    quick = args.quick
    n_pool = args.n_pool or (200 if quick else 400)
    nsample = args.samples or (24 if quick else 80)
    iters = 120 if quick else 250
    _CAT = load_catalog()

    missing = [c['id'] for c in CANDS if c['id'] not in _CAT]
    if missing:
        raise SystemExit('候选不在目录中: %s' % missing)

    print('[config] T0=%.0f T_end=%.0f cool_ticks=%.0f plateau=%s p_react=%.2f '
          'env_coupling=%.2f seed=%d' % (
              P['T0'], P['T_end'], P['cool_ticks'], P['plateau'],
              P['p_react'], P['env_coupling'], P['seed']))
    print('[mode] quick=%s n_pool=%d nsample=%d ipf_iters=%d' % (
        quick, n_pool, nsample, iters))

    # 候选属性
    cand_info = {}
    for c in CANDS:
        f = c['id']
        sc = scores(f)
        cc = counts(f)
        nL, nF = cc.get('L', 0), cc.get('F', 0)
        cand_info[f] = {
            'formula': f, 'name': c['name'], 'role': c['role'], 'note': c['note'],
            'natoms': len(_CAT[f]['atoms']),
            'c': 0,  # 下面由 resolve 在高温下取 csum
            'stable': bool(NE.is_stable(mol(f))),
            'heat': heat(f), 'Tdeg': nL + 2 * nF,
            'A': round(sc['A'], 3), 'D': round(sc['D'], 3),
            'w_self': round((2.5 * sc['A'] - 0.5 * sc['D']) / 3.0, 3),
        }
        # 分解阈 c 与集合阈值直接用 resolve 在高温下的返回
        r = NE.resolve([mol(f)], 100.0)
        cand_info[f]['c'] = r['csum']
        cand_info[f]['csum'] = r['csum']
        cand_info[f]['isum'] = r['isum']

    # 逐环境
    env_out = []
    danger_out = {}
    pair_out = {}
    matrix = {}
    for i, env in enumerate(ENVS):
        t0 = time.time()
        seed = int(P['seed']) + i
        pool, species, w = build_env_pool(env, n_pool, seed, iters=iters)
        st = pool_stats(env, pool)
        sh = shell_stats(pool)
        st.update(sh)
        st['id'] = env['id']
        st['name'] = env['name']
        st['basis'] = env['basis']
        st['target'] = {e: round(env['target'].get(e, 0.0), 4) for e in ELEMS}
        st['n_candidate_species'] = len(species)
        st['pool'] = pool
        env_out.append(st)
        print('[env %s] %s  n_pool=%d  种=%d  最大份额偏差=%.3f  D>0=%.2f  '
              '冷壳料=%.3f  用时 %.2fs' % (
                  env['id'], env['name'], st['n_pool'], st['n_species'],
                  st['max_share_dev'], st['dpos_share'], st['shell_share'],
                  time.time() - t0))

        for ci, c in enumerate(CANDS):
            cf = c['id']
            d = danger(cf, pool, nsample, seed * 1000 + ci)
            d['status'] = status_from_metrics(d)
            danger_out.setdefault(env['id'], {})[cf] = d
            pair_out.setdefault(env['id'], {})[cf] = pairw_stats(cf, pool)

        # 生存矩阵
        row = {}
        for c in CANDS:
            row[c['id']] = danger_out[env['id']][c['id']]['status']
        lm_body = membrane_status(st, cand_info['C3K3F2']['heat'])
        lm_rep = membrane_status(st, cand_info['XK2F4']['heat'])
        row['C3K3F2+local_membrane'] = lm_body[0]
        row['XK2F4+local_membrane'] = lm_rep[0]
        st['local_membrane'] = {
            'body': {'status': lm_body[0], 'note': lm_body[1]},
            'replicator': {'status': lm_rep[0], 'note': lm_rep[1]},
            'd_min_imported_shell': d_min(0.039, 200.0, cand_info['C3K3F2']['heat']),
            'O10XK4_in_pool': sum(1 for f in pool if f == 'O10XK4'),
        }
        matrix[env['id']] = row
        del st['pool']
        print('    危险度 p_cold: ' + '  '.join(
            '%s=%.2f' % (c['id'], danger_out[env['id']][c['id']]['p_react_cold'])
            for c in CANDS))

    # 完美膜热学
    thermal = []
    for eta, label in [(0.039, 'O10XK4 完美冷壳 η=0.039'),
                       (min([e['best_shell']['eta'] for e in env_out
                             if e['best_shell']] or [0.35]), '本地最优壳')]:
        rows = []
        for d in range(0, 6):
            rows.append({'d': d, 'T_in': round(t_in(200.0, eta, d), 2)})
        thermal.append({'label': label, 'eta': eta, 'rows': rows,
                        'd_min_core4': d_min(eta, 200.0, 4.0),
                        'd_min_core8': d_min(eta, 200.0, 8.0)})

    conclusions = build_conclusions(env_out, danger_out, matrix, cand_info, thermal)

    meta = {
        'task': 'T94-C 环境分支：环境族 × 生命候选 危险度与生存矩阵',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'quick': quick,
        'config': {k: P[k] for k in ['T0', 'T_end', 'cool_ticks', 'plateau',
                                     'p_react', 'gravity_G', 'env_coupling',
                                     'cap', 'react_margin', 'heat_w', 'seed']},
        'catalog_file': CATALOG_FILE,
        'catalog_size': len(_CAT),
        'n_pool': n_pool,
        'n_sample': nsample,
        'runtime_s': round(time.time() - t_start, 2),
        'criteria': {
            'P_COLD_BAD': P_COLD_BAD, 'P_COLD_MEMBRANE': P_COLD_MEMBRANE,
            'DUR_MEMBRANE': DUR_MEMBRANE, 'SHELL_SUPPLY_MIN': SHELL_SUPPLY_MIN,
            'D_MAX': D_MAX,
            'local_T': 'T_loc=(h_A+h_B+env_coupling*T_env)/(2+env_coupling)',
            'thermal': 'T93 模型A κ0=%.2f C_core=%.0f λ=%.2f T_CORE=%.1f' % (
                KAPPA0, C_CORE, LAM, T_CORE),
        },
        'candidates': cand_info,
        'envs': env_out,
        'danger': danger_out,
        'pairw': pair_out,
        'matrix': matrix,
        'thermal': thermal,
        'conclusions': conclusions,
    }

    out_json = args.out_json or JSON_DEFAULT
    with open(out_json, 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print('[json] %s（%.1f KB）' % (out_json, os.path.getsize(out_json) / 1024.0))

    out_png = args.out_png or PNG_DEFAULT
    if not args.no_png:
        draw_figure(meta, out_png)
        print('[png] %s' % out_png)

    print_summary(meta)
    print('[done] 用时 %.1fs' % (time.time() - t_start))
    return meta


def build_conclusions(env_out, danger_out, matrix, cand_info, thermal):
    envs = [e['id'] for e in env_out]
    name = {e['id']: e['name'] for e in env_out}
    out = []

    def best_worst(cand):
        vals = [(danger_out[e][cand]['p_react_cold'], e) for e in envs]
        vals.sort()
        return vals[0], vals[-1]

    for cand, label in [('C3K3F2', '裸主体 C3K3F2'),
                        ('XK2F4', '自复制候选 XK2F4'),
                        ('O10XK4', '完美冷壳 O10XK4')]:
        b, w = best_worst(cand)
        if w[0] - b[0] < 0.10:
            out.append('%s：所有环境都同样危险（p_cold %.2f~%.2f），不具环境选择性'
                       % (label, b[0], w[0]))
        else:
            out.append('%s：相对最安全 %s（%s，p_cold=%.2f），最危险 %s（%s，p_cold=%.2f）'
                       % (label, b[1], name[b[1]], b[0], w[1], name[w[1]], w[0]))

    body_good = [e for e in envs if matrix[e]['C3K3F2'] == '可存活']
    body_mem = [e for e in envs if matrix[e]['C3K3F2'] == '需膜']
    body_bad = [e for e in envs if matrix[e]['C3K3F2'] == '不可存活']
    out.append('裸主体 C3K3F2：可存活 %d 个环境%s；需膜 %d 个%s；不可存活 %d 个%s'
               % (len(body_good), body_good, len(body_mem), body_mem,
                  len(body_bad), body_bad))

    rep_bad = [e for e in envs if matrix[e]['XK2F4'] == '不可存活']
    out.append('裸自复制候选 XK2F4：不可存活 %d/%d 个环境%s，几乎所有环境都需要膜或不可存活'
               % (len(rep_bad), len(envs), rep_bad))

    lm_good = [e for e in envs if matrix[e]['C3K3F2+local_membrane'] == '可存活']
    lm_ext = [e for e in envs if matrix[e]['C3K3F2+local_membrane'] == '需外源膜']
    out.append('主体 + 本地冷壳膜：可存活环境 %d 个%s；仅差壳料供给需外源 %d 个%s'
               % (len(lm_good), lm_good, len(lm_ext), lm_ext))

    t = thermal[0]
    out.append('完美冷壳 O10XK4（η=0.039）在 200°C 下：d=%s 层可把核心(4°C)压到 ≤10°C，'
               'd=%s 层可把 8°C 核心压到 ≤10°C；而裸核心 200°C 下为 %.1f°C'
               % (t['d_min_core4'], t['d_min_core8'],
                  [r['T_in'] for r in t['rows'] if r['d'] == 0][0]))
    return out


def print_summary(meta):
    print('\n' + '=' * 78)
    print('环境 × 候选：p_react_cold（降温终点仍可能反应的池比例）')
    cands = ['C3K3F2', 'XK2F4', 'P2W', 'O10XK4', 'OXC']
    print('%-4s %-16s' % ('env', 'name') + ''.join('%10s' % c for c in cands))
    for e in meta['envs']:
        row = meta['danger'][e['id']]
        print('%-4s %-16s' % (e['id'], e['name'])
              + ''.join('%10.2f' % row[c]['p_react_cold'] for c in cands))
    print('\n环境 × 候选：ticks_mean（600 拍降温窗口内平均活跃拍数）')
    print('%-4s %-16s' % ('env', 'name') + ''.join('%10s' % c for c in cands))
    for e in meta['envs']:
        row = meta['danger'][e['id']]
        print('%-4s %-16s' % (e['id'], e['name'])
              + ''.join('%10.0f' % row[c]['ticks_mean'] for c in cands))
    print('\n环境 × 候选：pair-w 分布 strong/weak/none/repel')
    for e in meta['envs']:
        parts = []
        for c in cands:
            s = meta['pairw'][e['id']][c]['share']
            parts.append('%s %.2f/%.2f/%.2f/%.2f' % (
                c, s['strong'], s['weak'], s['none'], s['repel']))
        print('  %s: %s' % (e['id'], ' | '.join(parts)))
    print('\n生存矩阵（行=环境，列=裸主体/裸自复/裸高D膜/主体+本地膜/自复+本地膜）')
    cols = ['C3K3F2', 'XK2F4', 'P2W', 'C3K3F2+local_membrane', 'XK2F4+local_membrane']
    print('%-4s %-16s' % ('env', 'name') + ''.join('%14s' % c for c in cols))
    for e in meta['envs']:
        m = meta['matrix'][e['id']]
        print('%-4s %-16s' % (e['id'], e['name'])
              + ''.join('%14s' % m[c] for c in cols))
    print('\n结论：')
    for i, s in enumerate(meta['conclusions'], 1):
        print('  %d. %s' % (i, s))
    print('=' * 78 + '\n')


# ---------------------------------------------------------------------------
# 作图（Pillow，中文）
# ---------------------------------------------------------------------------
def get_font(size):
    from PIL import ImageFont
    path = FONT_PATH if os.path.exists(FONT_PATH) else FONT_FALLBACK
    return ImageFont.truetype(path, size)


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def heat_color(v, vmax=1.0):
    return lerp((232, 245, 233), (198, 40, 40), v / vmax if vmax else 0)


def draw_text(d, xy, s, font, fill=(30, 30, 30), anchor='la'):
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


def draw_figure(meta, path):
    from PIL import Image, ImageDraw
    W, H = 1600, 1000
    img = Image.new('RGB', (W, H), (250, 250, 248))
    d = ImageDraw.Draw(img)
    f_title = get_font(30)
    f_sub = get_font(15)
    f_panel = get_font(20)
    f_lab = get_font(14)
    f_small = get_font(12)
    f_cell = get_font(13)

    draw_text(d, (40, 22), 'T94-C 环境分支：按元素丰度定义的环境族 × 生命候选 危险度与生存矩阵',
              f_title, (25, 25, 25))
    draw_text(d, (40, 62),
              '温度口径 T0=%.0f°C→T_end=%.0f°C / %.0f 拍指数降温 / env_coupling=%.2f / '
              'G=%.2f；环境池按目录 84,225 条 IPF 丰度采样；危险度=反应温度窗口（规则1~11 resolve）'
              % (meta['config']['T0'], meta['config']['T_end'],
                 meta['config']['cool_ticks'], meta['config']['env_coupling'],
                 meta['config']['gravity_G']),
              f_sub, (90, 90, 90))

    envs = meta['envs']
    cands = ['C3K3F2', 'XK2F4', 'P2W', 'O10XK4', 'OXC']

    # ---------------- A 环境元素丰度 ----------------
    ax0, ay0, aw, ah = 40, 100, 470, 330
    d.rounded_rectangle([ax0, ay0, ax0 + aw, ay0 + ah], 6, fill=(255, 255, 255),
                        outline=(210, 210, 210))
    draw_text(d, (ax0 + 12, ay0 + 8), 'A 环境元素丰度（实际池配平份额）', f_panel)
    chart_x, chart_y = ax0 + 34, ay0 + 44
    chart_w, chart_h = aw - 120, ah - 95
    bar_w = chart_w / len(envs)
    for i, e in enumerate(envs):
        x0 = chart_x + i * bar_w + 4
        y = chart_y + chart_h
        for el in ELEMS:
            v = e['achieved_share'].get(el, 0.0)
            h = v * chart_h
            if h <= 0:
                continue
            y -= h
            d.rectangle([x0, y, x0 + bar_w - 10, y + h],
                        fill=ELEM_COLORS[el], outline=(255, 255, 255))
        draw_text(d, (x0 + (bar_w - 10) / 2, chart_y + chart_h + 6),
                  e['id'], f_lab, anchor='ma')
    # 图例
    lx, ly = ax0 + aw - 92, chart_y
    for el in ELEMS:
        d.rectangle([lx, ly, lx + 12, ly + 12], fill=ELEM_COLORS[el])
        draw_text(d, (lx + 17, ly - 1), el, f_small)
        ly += 20
    draw_text(d, (ax0 + 8, ay0 + ah - 16),
              '每环境 n_pool=%d；元素序 %s' % (meta['n_pool'], '/'.join(ELEMS)),
              f_small, (100, 100, 100))

    # ---------------- B 危险度热图 p_react_cold ----------------
    bx0, by0, bw, bh = 530, 100, 500, 330
    d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], 6, fill=(255, 255, 255),
                        outline=(210, 210, 210))
    draw_text(d, (bx0 + 12, by0 + 8), 'B 危险度：p_react_cold（T_env=0 时仍可能反应）', f_panel)
    gx, gy = bx0 + 52, by0 + 48
    cw, chh = 74, 26
    for j, c in enumerate(cands):
        draw_text(d, (gx + j * cw + cw / 2, gy - 14), c, f_small, anchor='ma')
    for i, e in enumerate(envs):
        row = meta['danger'][e['id']]
        yy = gy + i * chh
        draw_text(d, (gx - 8, yy + chh / 2), e['id'], f_small, anchor='ra')
        for j, c in enumerate(cands):
            v = row[c]['p_react_cold']
            col = heat_color(v, 1.0)
            d.rectangle([gx + j * cw, yy, gx + j * cw + cw - 2, yy + chh - 2],
                        fill=col, outline=(255, 255, 255))
            draw_text(d, (gx + j * cw + cw / 2 - 1, yy + chh / 2), '%.2f' % v,
                      f_cell, (255, 255, 255) if v > 0.55 else (30, 30, 30),
                      anchor='mm')
    draw_text(d, (bx0 + 12, by0 + bh - 18),
              '绿→红 = 0→1；>=0.50 判不可存活，>=0.10 判需膜（模型内约定）', f_small,
              (100, 100, 100))

    # ---------------- C 活跃拍数热图 ----------------
    cx0, cy0, cw0, ch0 = 1050, 100, 510, 330
    d.rounded_rectangle([cx0, cy0, cx0 + cw0, cy0 + ch0], 6, fill=(255, 255, 255),
                        outline=(210, 210, 210))
    draw_text(d, (cx0 + 12, cy0 + 8), 'C 反应窗口：降温 600 拍内平均活跃拍数', f_panel)
    gx2, gy2 = cx0 + 52, cy0 + 48
    cw2 = 86
    for j, c in enumerate(cands):
        draw_text(d, (gx2 + j * cw2 + cw2 / 2, gy2 - 14), c, f_small, anchor='ma')
    for i, e in enumerate(envs):
        row = meta['danger'][e['id']]
        yy = gy2 + i * chh
        draw_text(d, (gx2 - 8, yy + chh / 2), e['id'], f_small, anchor='ra')
        for j, c in enumerate(cands):
            v = row[c]['ticks_mean']
            col = heat_color(v, 600.0)
            d.rectangle([gx2 + j * cw2, yy, gx2 + j * cw2 + cw2 - 2, yy + chh - 2],
                        fill=col, outline=(255, 255, 255))
            draw_text(d, (gx2 + j * cw2 + cw2 / 2 - 1, yy + chh / 2), '%.0f' % v,
                      f_cell, (255, 255, 255) if v > 330 else (30, 30, 30),
                      anchor='mm')
    draw_text(d, (cx0 + 12, cy0 + ch0 - 18),
              '越红=反应持续越久；dur=ticks/600，>=0.80 判需膜', f_small, (100, 100, 100))

    # ---------------- D 生存矩阵 ----------------
    dx0, dy0, dw, dh = 40, 460, 830, 460
    d.rounded_rectangle([dx0, dy0, dx0 + dw, dy0 + dh], 6, fill=(255, 255, 255),
                        outline=(210, 210, 210))
    draw_text(d, (dx0 + 12, dy0 + 8), 'D 生存矩阵（模型内判据）：行=环境，列=候选/复合', f_panel)
    cols = [('C3K3F2', '裸主体'), ('XK2F4', '裸自复'), ('P2W', '裸高D膜'),
            ('C3K3F2+local_membrane', '主体+本地膜'),
            ('XK2F4+local_membrane', '自复+本地膜')]
    mx, my = dx0 + 132, dy0 + 64
    colw, rowh = 138, 42
    for j, (key, lab) in enumerate(cols):
        draw_text(d, (mx + j * colw + colw / 2, my - 14), lab, f_small, anchor='ma')
    for i, e in enumerate(envs):
        yy = my + i * rowh
        short = e['id'] + ' ' + e['name'].replace('环境', '')
        draw_text(d, (mx - 10, yy + rowh / 2), short, f_small, anchor='ra')
        for j, (key, lab) in enumerate(cols):
            st = meta['matrix'][e['id']][key]
            col = STATUS_COLORS.get(st, STATUS_COLORS['无法判定'])
            x0 = mx + j * colw
            d.rectangle([x0, yy, x0 + colw - 3, yy + rowh - 3], fill=col,
                        outline=(255, 255, 255))
            tc = (255, 255, 255) if st in ('不可存活',) else (25, 25, 25)
            draw_text(d, (x0 + (colw - 3) / 2, yy + rowh / 2), st, f_lab, tc,
                      anchor='mm')
    # 图例
    lx, ly = dx0 + 12, dy0 + dh - 26
    for st in ['可存活', '需膜', '需外源膜', '不可存活']:
        c = STATUS_COLORS[st]
        d.rectangle([lx, ly - 10, lx + 14, ly + 4], fill=c)
        draw_text(d, (lx + 20, ly - 11), st, f_small)
        lx += 110
    draw_text(d, (dx0 + 560, dy0 + dh - 26),
              '判据：p_cold>=0.50 坏；>=0.10 或 dur>=0.80 需膜', f_small, (100, 100, 100))

    # ---------------- E 冷壳料可得性 ----------------
    ex0, ey0, ew, eh = 890, 460, 330, 460
    d.rounded_rectangle([ex0, ey0, ex0 + ew, ey0 + eh], 6, fill=(255, 255, 255),
                        outline=(210, 210, 210))
    draw_text(d, (ex0 + 12, ey0 + 8), 'E 本地冷壳料可得性', f_panel)
    gx3, gy3 = ex0 + 46, ey0 + 52
    ch3 = 260
    vmax = max([e['shell_share'] for e in envs] + [0.05]) * 1.15
    bw3 = (ew - 80) / len(envs)
    for i, e in enumerate(envs):
        v = e['shell_share']
        h = (v / vmax) * ch3
        x0 = gx3 + i * bw3 + 2
        d.rectangle([x0, gy3 + ch3 - h, x0 + bw3 - 8, gy3 + ch3],
                    fill=(54, 110, 160))
        draw_text(d, (x0 + (bw3 - 8) / 2, gy3 + ch3 - h - 14), '%.2f' % v, f_small,
                  anchor='ma')
        draw_text(d, (x0 + (bw3 - 8) / 2, gy3 + ch3 + 6), e['id'], f_small,
                  anchor='ma')
    d.line([gx3, gy3 + ch3, gx3 + (ew - 80), gy3 + ch3], fill=(120, 120, 120))
    ly = gy3 + ch3 + 30
    for e in envs:
        b = e['best_shell']
        if b:
            draw_text(d, (ex0 + 12, ly),
                      '%s %s η=%.3f w=%.2f' % (e['id'], b['formula'], b['eta'],
                                               b['w_self']), f_small)
        else:
            draw_text(d, (ex0 + 12, ly), '%s 无冷壳料' % e['id'], f_small,
                      (150, 60, 60))
        ly += 14

    # ---------------- F 保温模型 A ----------------
    fx0, fy0, fw, fh = 1240, 460, 320, 460
    d.rounded_rectangle([fx0, fy0, fx0 + fw, fy0 + fh], 6, fill=(255, 255, 255),
                        outline=(210, 210, 210))
    draw_text(d, (fx0 + 12, fy0 + 8), 'F 保温模型 A：T_in(d)', f_panel)
    ox, oy = fx0 + 46, fy0 + 300
    pw, ph = fw - 80, 220
    d.line([ox, oy, ox + pw, oy], fill=(120, 120, 120))
    d.line([ox, oy, ox, oy - ph], fill=(120, 120, 120))
    ymax = 25.0
    for dmark in range(0, 6):
        x = ox + dmark * (pw / 5.0)
        draw_text(d, (x, oy + 6), str(dmark), f_small, anchor='ma')
    for tv in [0, 5, 10, 20]:
        y = oy - (tv / ymax) * ph
        d.line([ox, y, ox + pw, y], fill=(225, 225, 225))
        draw_text(d, (ox - 6, y), str(tv), f_small, anchor='ra')
    # 10°C 基线
    y10 = oy - (10.0 / ymax) * ph
    d.line([ox, y10, ox + pw, y10], fill=(211, 47, 47), width=2)
    draw_text(d, (ox + pw - 4, y10 - 6), '10°C 目标', f_small, (211, 47, 47),
              anchor='ra')
    curve_colors = [(198, 40, 40), (31, 119, 180)]
    for k, t in enumerate(meta['thermal']):
        pts = []
        for r in t['rows']:
            x = ox + (r['d'] / 5.0) * pw
            y = oy - min(r['T_in'], ymax * 0.98) / ymax * ph
            pts.append((x, y))
        col = curve_colors[k % 2]
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=col, width=2)
        for (x, y), r in zip(pts, t['rows']):
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=col)
        draw_text(d, (fx0 + 14, fy0 + 36 + k * 18), t['label'], f_small, col)
    draw_text(d, (fx0 + 12, fy0 + fh - 92),
              '平均本地壳 η=%.3f；O10XK4 η=0.039' % meta['thermal'][1]['eta'],
              f_small)
    draw_text(d, (fx0 + 12, fy0 + fh - 74),
              '200°C 下完美膜 d_min(4°C 核)=%s、d_min(8°C 核)=%s' % (
                  meta['thermal'][0]['d_min_core4'],
                  meta['thermal'][0]['d_min_core8']), f_small)
    draw_text(d, (fx0 + 12, fy0 + fh - 50),
              '裸核 200°C：T_in=%.1f°C > 10°C' %
              [r['T_in'] for r in meta['thermal'][0]['rows'] if r['d'] == 0][0],
              f_small, (150, 60, 60))

    # 页脚
    draw_text(d, (40, H - 28),
              '复现：python alchemy/t94_env.py（--quick 快速自检）；'
              '数据 t94_envmap.json；判据与局限见 docs/T94_ENV.md',
              f_small, (110, 110, 110))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, 'PNG')
    # 自检：重新打开确认可读
    from PIL import Image as _I
    with _I.open(path) as chk:
        chk.load()
        print('[png-check] size=%s mode=%s' % (chk.size, chk.mode))


class _Args(object):
    pass


def main(argv=None):
    ap = argparse.ArgumentParser(description='T94-C 环境分支：环境族 × 生命候选')
    ap.add_argument('--quick', action='store_true', help='快速自检模式')
    ap.add_argument('--n-pool', type=int, default=None, help='每环境分子池大小')
    ap.add_argument('--samples', type=int, default=None, help='每环境反应抽样数')
    ap.add_argument('--out-json', default=None)
    ap.add_argument('--out-png', default=None)
    ap.add_argument('--no-png', action='store_true')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    run(args)


if __name__ == '__main__':
    main()
