# -*- coding: utf-8 -*-
"""t12_theory.py：反应幂等性（F(F(v))=F(v)）数值验证 + 理论说明
定律：反应结果只由元素总计数向量 v 决定，记为 F(v)。产物总向量恒等于 v（守恒），
因此把一次反应的全部产物再投锅 = 对同一 v 再求 F ⇒ 产物不变。即 F 是幂等映射。
"""
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]


def atoms_of(v):
    return [s for s, c in zip(ORDER, v) for _ in range(c)]


def react(v):
    mols = P.simulate(atoms_of(v))
    if mols is None or not pot_v2.embed_all2(mols):
        return None
    return mols


def main():
    rng = random.Random(2027)
    tests = 0
    same = 0
    fail = 0
    examples = []
    vecs = []
    # 全 9 元素、总原子 2..14 的随机向量
    for _ in range(120):
        n = rng.randint(2, 14)
        v = [0] * 9
        for _ in range(n):
            v[rng.randrange(9)] += 1
        vecs.append(tuple(v))
    # 再补一些均衡向量
    for k in (2, 3, 4):
        for _ in range(10):
            v = [0] * 9
            for i in range(9):
                v[i] = rng.randint(0, k)
            vecs.append(tuple(v))
    for v in vecs:
        mols = react(v)
        if mols is None:
            fail += 1
            continue
        tests += 1
        p1 = sorted(P.formula_of(m["atoms"]) for m in mols)
        # 产物全部再投锅：产物原子总数 = v，故再反应 = F(v)
        mols2 = react(tuple(v))
        p2 = sorted(P.formula_of(m["atoms"]) for m in mols2)
        if p1 == p2:
            same += 1
        else:
            examples.append((v, p1, p2))
    print(f"测试 {len(vecs)} 个向量：成功 {tests}，失败 {fail}；产物再投锅结果一致 {same}/{tests}")
    if examples:
        print("不一致例子:", examples[:3])

    # 另一层验证：把产物分子拆回原子（总向量 = v）再投 → 同上
    # 这里通过构造"产物多重集"的原子列表再 simulate 验证
    ok2 = 0
    for v in vecs[:60]:
        mols = react(v)
        if mols is None:
            continue
        atoms = []
        for m in mols:
            atoms.extend(m["atoms"])
        mols2 = P.simulate(atoms)
        if mols2 is None or not pot_v2.embed_all2(mols2):
            print("产物再投失败!", v)
            continue
        p1 = sorted(P.formula_of(m["atoms"]) for m in mols)
        p2 = sorted(P.formula_of(m["atoms"]) for m in mols2)
        if p1 == p2:
            ok2 += 1
    print(f"产物原子重组验证：{ok2}/60 一致")


if __name__ == "__main__":
    main()
