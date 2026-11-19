"""T79 · 自催化/自生长扫描（只读，不动内核）。

问题（用户 m00871）：是否存在这样一种"生命"——
主体 A（+ 辅件 B/C/D），通过抓取周围小分子、经一步或几步反应产生新的 A，
并把新 A 并入自身（于是身体长大）。

本脚本在当前正式口径（规则 1~11，natural_engine）下做四组搜索：
  S1 营养物对：两两小分子的完全反应，产物中出现 >=2 份同一分子（净增/放大）；
     产物中含投入物之一（看似催化）；
  S2 生长链：从种子开始，每次并入一个营养物，只要 F(总向量) 仍是单产物就继续，
     直到不能再长；统计最大原子数（"增长饱和"天花板）；
  S3 自再生/自放大：候选主体 A（大型稳定分子） + 小营养物，
     检查产物是否仍含 A（催化再生）或含 >=2 份 A（净放大）；
  S4 随机生长链：大量随机营养物序列，测 F 保持单产物的最长原子数分布。

为避开极端大图 embedding 的尾部延迟，所有生长搜索把总原子数上限设为 MAX_ATOMS=22
（远超已知 14~17 饱和区；超过即无法再判为"生长"）。

输出：t79_life_scan.json + 控制台摘要。
用法：python t79_life_scan.py [--quick]
"""
import argparse
import io
import json
import random
import time
from collections import Counter

import natural_engine as E
import pot_all as P

CAT_INDEX = 't4_catalog_index.json'
SEED = 20261120
MAX_ATOMS = 22
F_CACHE = {}


def load_index():
    with io.open(CAT_INDEX, encoding='utf-8') as f:
        return json.load(f)


def f_products(vec):
    """F(vec) -> (formulas, natoms_list, ok)；原子数 > MAX_ATOMS 直接判 unknown。"""
    key = vec
    if key in F_CACHE:
        return F_CACHE[key]
    if sum(vec) > MAX_ATOMS:
        res = ([], [], None)
        F_CACHE[key] = res
        return res
    try:
        prods = E.complete_products(vec)
    except Exception:
        res = ([], [], False)
        F_CACHE[key] = res
        return res
    if not prods:
        res = ([], [], False)
    else:
        res = ([m['formula'] for m in prods], [len(m['atoms']) for m in prods], True)
    F_CACHE[key] = res
    return res


def addv(a, b):
    return tuple(a[i] + b[i] for i in range(9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--out', default='t79_life_scan.json')
    args = ap.parse_args()
    t0 = time.time()
    E.set_fast(True)
    rng = random.Random(SEED)
    idx = load_index()
    by_n = {}
    for rec in idx:
        by_n.setdefault(rec.get('natoms'), []).append(rec)

    # ---------- 池：小营养物（natoms<=3）----------
    small = []
    for n in (2, 3):
        small.extend([r['formula'] for r in by_n.get(n, [])])
    small = sorted(set(small))
    vecs = {f: P.parse_formula(f) for f in small}
    print('nutrient pool (natoms<=3): %d' % len(small), flush=True)

    # ---------- S1 营养物对 ----------
    s1 = {'pairs': 0, 'ok': 0, 'fail': 0, 'inert': 0, 'single': 0, 'multi': 0,
          'amplified_pairs': 0, 'amplified_examples': [],
          'catalytic_pairs': 0, 'catalytic_examples': [],
          'max_product_atoms': 0, 'max_product_formula': ''}
    n = len(small)
    for i in range(n):
        fi = small[i]
        vi = vecs[fi]
        for j in range(i, n):
            fj = small[j]
            f, na, ok = f_products(addv(vi, vecs[fj]))
            s1['pairs'] += 1
            if not ok:
                s1['fail'] += 1
                continue
            s1['ok'] += 1
            if len(f) == 1:
                s1['single'] += 1
            else:
                s1['multi'] += 1
            inp = Counter([fi, fj])
            if Counter(f) == inp:
                s1['inert'] += 1
            mx = max(na)
            if mx > s1['max_product_atoms']:
                s1['max_product_atoms'] = mx
                s1['max_product_formula'] = ' + '.join(sorted(f))
            c = Counter(f)
            amp = [g for g, k in c.items() if k >= 2 and inp.get(g, 0) == 0]
            if amp:
                s1['amplified_pairs'] += 1
                if len(s1['amplified_examples']) < 40:
                    s1['amplified_examples'].append(
                        {'inputs': [fi, fj], 'products': f, 'amplified': amp})
            cat = [g for g in c if g in (fi, fj)]
            if cat and not (Counter(f) == inp):
                s1['catalytic_pairs'] += 1
                if len(s1['catalytic_examples']) < 40:
                    s1['catalytic_examples'].append(
                        {'inputs': [fi, fj], 'products': f, 'kept': cat})
    s1['multi_share'] = s1['multi'] / max(1, s1['ok'])
    print('S1 %.1fs: pairs=%d ok=%d single=%d multi=%d(%.1f%%) inert=%d amp=%d cat=%d maxatoms=%d'
          % (time.time() - t0, s1['pairs'], s1['ok'], s1['single'], s1['multi'],
             100 * s1['multi_share'], s1['inert'], s1['amplified_pairs'],
             s1['catalytic_pairs'], s1['max_product_atoms']), flush=True)

    # ---------- S2 生长链（贪心，单个营养物并入）----------
    seeds = ['CF', 'LF', 'L2', 'WA', 'OK', 'PK', 'OP', 'XA', 'C2', 'CL',
             'OXC', 'OXCPWK', 'OXCPWKA', 'O2XCP3WK2', 'O3X2P3WK2A', 'X3C3P3W3K2']
    s2 = {'chains': [], 'max_atoms': 0, 'max_chain': None}
    for seed in seeds:
        try:
            v = P.parse_formula(seed)
        except Exception:
            continue
        cur, cur_atoms, path = seed, sum(v), [seed]
        steps = 0
        while steps < 15:
            best = None
            for nut in small:
                vt = addv(v, vecs[nut])
                if sum(vt) > MAX_ATOMS:
                    continue
                f, na, ok = f_products(vt)
                if not ok or len(f) != 1:
                    continue
                if f[0] == cur:
                    continue
                gain = na[0] - cur_atoms
                if gain <= 0:
                    continue
                if best is None or gain > best[0]:
                    best = (gain, f[0], vt, na[0], nut)
            if best is None:
                break
            _, cur, v, cur_atoms, nut = best
            path.append(nut + '->' + cur)
            steps += 1
        rec = {'seed': seed, 'steps': steps, 'final': cur, 'final_atoms': cur_atoms, 'path': path}
        s2['chains'].append(rec)
        if cur_atoms > s2['max_atoms']:
            s2['max_atoms'] = cur_atoms
            s2['max_chain'] = rec
        print('  S2 seed %-12s -> %-18s atoms=%2d steps=%d' % (seed, cur, cur_atoms, steps), flush=True)
    print('S2 %.1fs: max_atoms=%d' % (time.time() - t0, s2['max_atoms']), flush=True)

    # ---------- S3 自再生 / 自放大（主体 A + 营养物）----------
    bodies = ['CF', 'LF', 'L2', 'WA', 'OK', 'PK', 'OP', 'XA', 'OXC', 'OXCPWK',
              'OXCPWKA', 'O2XCP3WK2', 'O3X2P3WK2A', 'O2XCP2KA', 'O2LKA',
              'O4L3K2AF', 'O6W3K4', 'X3C3P3W3K2']
    s3 = {'cases': 0, 'regenerate': [], 'amplify': [], 'decomp': 0, 'inert': 0, 'unknown': 0}
    for A in bodies:
        try:
            va = P.parse_formula(A)
        except Exception:
            continue
        for nut in small:
            vt = addv(va, vecs[nut])
            f, na, ok = f_products(vt)
            s3['cases'] += 1
            if ok is None:
                s3['unknown'] += 1
                continue
            if not ok:
                s3['decomp'] += 1
                continue
            c = Counter(f)
            inp = Counter([A, nut])
            if Counter(f) == inp:
                s3['inert'] += 1
                continue
            if c.get(A, 0) >= 2:
                s3['amplify'].append({'A': A, 'nutrient': nut, 'products': f})
            elif c.get(A, 0) == 1:
                s3['regenerate'].append({'A': A, 'nutrient': nut, 'products': f})
    print('S3 %.1fs: cases=%d regenerate=%d amplify=%d inert=%d decomp=%d unknown=%d'
          % (time.time() - t0, s3['cases'], len(s3['regenerate']), len(s3['amplify']),
             s3['inert'], s3['decomp'], s3['unknown']), flush=True)

    # ---------- S4 随机生长链天花板 ----------
    start_seeds = ['CF', 'LF', 'L2', 'WA', 'OK', 'PK', 'OP', 'XA', 'C2', 'CL']
    s4 = {'chains': 0, 'max_atoms': 0, 'steps_hist': {}, 'final_atoms_hist': {},
          'examples': []}
    for _ in range(40 if args.quick else 200):
        seed = rng.choice(start_seeds)
        v = P.parse_formula(seed)
        cur, cur_atoms, steps = seed, sum(v), 0
        while steps < 15:
            cand = []
            for nut in small:
                vt = addv(v, vecs[nut])
                if sum(vt) > MAX_ATOMS:
                    continue
                f, na, ok = f_products(vt)
                if ok and len(f) == 1 and f[0] != cur and na[0] > cur_atoms:
                    cand.append((nut, f[0], vt, na[0]))
            if not cand:
                break
            nut, cur, v, cur_atoms = rng.choice(cand)
            steps += 1
        print('  S4 chain %d: seed=%s steps=%d final=%s atoms=%d'
              % (s4['chains'] + 1, seed, steps, cur, cur_atoms), flush=True)
        s4['chains'] += 1
        s4['max_atoms'] = max(s4['max_atoms'], cur_atoms)
        s4['steps_hist'][str(steps)] = s4['steps_hist'].get(str(steps), 0) + 1
        s4['final_atoms_hist'][str(cur_atoms)] = s4['final_atoms_hist'].get(str(cur_atoms), 0) + 1
        if len(s4['examples']) < 20:
            s4['examples'].append({'seed': seed, 'steps': steps, 'final': cur,
                                   'final_atoms': cur_atoms})
    print('S4 %.1fs: chains=%d max_atoms=%d' % (time.time() - t0, s4['chains'],
                                                s4['max_atoms']), flush=True)

    out = {'meta': {'script': 't79_life_scan.py',
                    'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'engine': 'natural_engine (rules 1-11)', 'seed': SEED,
                    'max_atoms_guard': MAX_ATOMS, 'quick': args.quick,
                    'nutrient_pool': len(small),
                    'elapsed_s': round(time.time() - t0, 1)},
           'S1_nutrient_pairs': s1,
           'S2_growth_chains_greedy': s2,
           'S3_body_regeneration': s3,
           'S4_random_growth_ceiling': s4}
    with io.open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('saved', args.out)


if __name__ == '__main__':
    main()
