# -*- coding: utf-8 -*-
"""T95 碰撞/推挤规则参数（可调；默认值 = 用户 2026-11-24 确认的初值）。

设计见 docs/T95_COLLISION_DESIGN.md。动力学代码一律从 params() 取参，
不在 t95_collision.py 里硬编码；命令行或脚本可传覆盖值：

    from t95_config import params
    P = params(Kmax=8, Vmax=3.0)

keys:
    e           恢复系数（一维冲量解算）
    mu          摩擦系数（地面/链内能量损耗）
    Kmax        单次推挤最多推动的分子数（链长上限）
    Vmax        单拍最大位移（格/拍）
    gamma       速度阻尼（每拍）
    M_min_ratio 推动者质量下限比：M_A >= ratio * M_B
    dt          冲量时间步
"""

PUSH = {
    "e": 0.2,
    "mu": 0.25,
    "Kmax": 6,
    "Vmax": 2.0,
    "gamma": 0.15,
    "M_min_ratio": 0.5,
    "dt": 1.0,
}

KEY_NAMES = tuple(PUSH)


def params(**over):
    """返回一份参数副本；只接受已知键，未知键抛 ValueError（防拼写错误静默生效）。"""
    bad = [k for k in over if k not in PUSH]
    if bad:
        raise ValueError("unknown T95 params: %s" % ", ".join(sorted(bad)))
    p = dict(PUSH)
    p.update(over)
    return p


def describe(p=None):
    p = PUSH if p is None else p
    ks = ", ".join("%s=%s" % (k, p[k]) for k in KEY_NAMES)
    return "T95 push params: " + ks
