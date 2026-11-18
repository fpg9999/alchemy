# -*- coding: utf-8 -*-
"""差分测试：内核必须与仓库根的历史实现**逐字节等价**。

这是"抽取内核"最关键的保证——新包不是重写，而是搬运 + 去硬编码路径。
如果哪天有人改了成键优先级，这里会立刻失败。
"""

import _util

import alchemy
from alchemy.core import reactor


def test_equivalent_to_pot_v4_rules11():
    orig = _util.load_originals()["pot_v4"]
    feeds = _util.random_feeds(seed=20261117, count=200, max_types=4, max_n=11)
    # 加上一批大投料
    feeds += [list("OOOOOOXXXXXXCCCCKKKKAAAAFFFF"),
              list("OOOXXXCCKKKAAAFFF"),
              _util.random_feeds(20261118, 20, max_types=9, max_n=20)[0],
              _util.random_feeds(20261118, 20, max_types=9, max_n=20)[1]]
    for feed in feeds:
        want = orig.simulate(list(feed))
        got = alchemy.simulate(list(feed))
        if want is None:
            assert got is None, f"原实现失败、新实现成功：{feed}"
            continue
        assert got is not None, f"新实现失败：{feed}"
        assert _util.mol_multiset(got) == _util.mol_multiset(want), \
            f"产物不一致：{feed}\n got={_util.formula_sequence(got)}\nwant={_util.formula_sequence(want)}"


def test_equivalent_to_pot_v3_rules9():
    orig = _util.load_originals()["pot_v3"]
    feeds = _util.random_feeds(seed=99, count=120, max_types=4, max_n=10)
    for feed in feeds:
        want = orig.simulate(list(feed))
        got = alchemy.simulate(list(feed), rules=9)
        if want is None:
            assert got is None
            continue
        assert got is not None
        assert _util.mol_multiset(got) == _util.mol_multiset(want), \
            f"rules=9 不一致：{feed}"


def test_equivalent_to_pot_all_rules8():
    orig = _util.load_originals()["pot_all"]
    feeds = _util.random_feeds(seed=1234, count=120, max_types=3, max_n=9)
    for feed in feeds:
        want = orig.simulate(list(feed))
        got = alchemy.simulate(list(feed), rules=8)
        if want is None:
            assert got is None
            continue
        assert got is not None
        assert _util.mol_multiset(got) == _util.mol_multiset(want), \
            f"rules=8 不一致：{feed}"


def test_level6_matches_pot_v4():
    orig = _util.load_originals()["pot_v4"]
    feeds = _util.random_feeds(seed=555, count=120, max_types=4, max_n=12)
    for feed in feeds:
        want = orig.simulate(list(feed), return_level6=True)
        got = alchemy.simulate(list(feed), return_level6=True)
        if want[0] is None:
            assert got[0] is None
            continue
        assert got[0] is not None
        wl, gl = want[1], got[1]
        assert len(wl) == len(gl), f"level6 块数不同：{feed}"
        # 块逐一对齐（顺序也应一致）
        for (wats, wes, wmem), (gats, ges, gmem) in zip(wl, gl):
            assert wats == gats and wmem == gmem, f"level6 成员不同：{feed}"
            assert sorted(map(tuple, wes)) == sorted(map(tuple, ges)), f"level6 键不同：{feed}"


def test_return_order_matches_pot_v4():
    """产物返回顺序也应当一致（下游脚本依赖它做图/编号）。"""
    orig = _util.load_originals()["pot_v4"]
    feeds = _util.random_feeds(seed=31415, count=60, max_types=4, max_n=10)
    for feed in feeds:
        want = orig.simulate(list(feed))
        got = alchemy.simulate(list(feed))
        if want is None:
            continue
        assert _util.formula_sequence(got) == _util.formula_sequence(want), \
            f"返回顺序不同：{feed}"


def test_trace_bonds_match_original_structure():
    """trace() 的键表应能重建出与原实现相同的产物。"""
    orig = _util.load_originals()["pot_v4"]
    for feed in _util.random_feeds(seed=2718, count=60, max_types=4, max_n=10):
        want = orig.simulate(list(feed))
        if want is None:
            continue
        tr = reactor.trace(list(feed))
        assert tr is not None
        # 用键表重建分子
        from collections import defaultdict
        adj = defaultdict(list)
        for (i, j, m) in tr["bonds"]:
            adj[i].append((j, m))
            adj[j].append((i, m))
        seen = set()
        rebuilt = []
        for s in range(len(tr["atoms"])):
            if s in seen:
                continue
            seen.add(s)
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v, _ in adj[u]:
                    if v not in seen:
                        seen.add(v)
                        st.append(v)
                        mem.append(v)
            rebuilt.append([tr["atoms"][v] for v in mem])
        assert sorted(alchemy.formula_of(x) for x in rebuilt) == \
            sorted(alchemy.formula_of(m["atoms"]) for m in want)
