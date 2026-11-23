"""T94 生命普查 —— 试验场默认参数（用户 2026-11-24 指定）。

这套默认值与 Godot ChemLab（godot/chem_lab/scripts/sim.gd）保持一一对应，
T94 的所有 Python 仿真（t94_*.py）必须从这里取默认值，不要各自硬编码。

用户指定：
  * 初始温度 T0 = 200 °C
  * 终态温度 T_end = 0 °C
  * 分子接触后反应概率 = 1.0（100%）
  * 重力 G = 0.2
  * 环境耦合度 env_coupling = 0.5

注意口径（与 ChemLab 相同）：
  - 温度曲线：T(t) = T_end + (T0 - T_end) * exp(-6*t/cool_ticks)（t < cool_ticks）
    平台开启时 t >= cool_ticks 后恒为 T_end；关闭时继续 T_end*exp(-3*(t-ct)/ct)。
  - 局部温度（反应门控）：T_local = (Σ_{2 格内分子 heat} + ec*T_env) / (n + ec)，
    heat = -1*n_C + 1*n_L + 2*n_F（ChemLab 默认热值权重）。
  - 重力：每拍 gacc += G*mass，累计 >= 1 整块下移 1 格（最多 4 格/拍）。
  - p_react = 1.0 表示条件满足时每次接触必反应（不再抽样）。
"""

DEFAULT_PARAMS = {
    "T0": 200.0,          # 初始温度 °C
    "T_end": 0.0,         # 终态温度 °C
    "cool_ticks": 600.0,  # 降温拍数
    "plateau": True,      # 降到 T_end 后恒温
    "p_react": 1.0,       # 接触反应概率（1.0 = 必反应）
    "gravity_G": 0.20,    # 重力
    "env_coupling": 0.5,  # 环境耦合度
    "cap": 36,            # 单次反应总原子上限
    "react_margin": 0.0,  # 反应温度余量
    "heat_w": {"C": -1.0, "L": 1.0, "F": 2.0},  # 热值权重
    "seed": 20261124,
}

# ChemLab 参数名 -> 本模块名（用于文档/对照）
CHEMLAB_ALIASES = {
    "T0": "T0",
    "T_end": "T_end",
    "cool_ticks": "cool_ticks",
    "plateau": "plateau",
    "p_react": "p_react",
    "gravity_G": "gravity_G",
    "env_coupling": "env_coupling",
    "cap": "cap",
    "react_margin": "react_margin",
}


def schedule_T(t, T0=None, T_end=None, cool_ticks=None, plateau=None):
    """环境温度曲线，与 sim.gd schedule_T 完全一致。"""
    import math

    p = DEFAULT_PARAMS
    T0 = p["T0"] if T0 is None else T0
    T_end = p["T_end"] if T_end is None else T_end
    ct = p["cool_ticks"] if cool_ticks is None else float(cool_ticks)
    plateau = p["plateau"] if plateau is None else plateau
    if t < ct:
        return T_end + (T0 - T_end) * math.exp(-6.0 * t / ct)
    if plateau:
        return T_end
    return T_end * math.exp(-3.0 * (t - ct) / ct)


def heat_of(counts, heat_w=None):
    """分子热值 heat = wC*nC + wL*nL + wF*nF。counts 为 {元素: 数量}。"""
    w = DEFAULT_PARAMS["heat_w"] if heat_w is None else heat_w
    return w["C"] * counts.get("C", 0) + w["L"] * counts.get("L", 0) + w["F"] * counts.get("F", 0)


def local_T(heats, T_env, ec=None):
    """ChemLab 局部温度：T_local = (Σ heat + ec*T_env)/(n + ec)。"""
    ec = DEFAULT_PARAMS["env_coupling"] if ec is None else ec
    n = len(heats)
    if n == 0:
        return T_env
    return (sum(heats) + ec * T_env) / (n + ec)


def describe():
    return ("T94 试验场默认：T0=200°C → T_end=0°C（600 拍指数降温，平台恒温）、"
            "p_react=1.0、G=0.2、env_coupling=0.5、cap=36、heat(C,L,F)=(-1,+1,+2)")
