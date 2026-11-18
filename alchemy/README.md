# alchemy —— 炼金术化学内核

一个"元素 → 价数 → 键型 → 分子 → 骨架"的确定性化学模型，为炼金术题材游戏提供物质生成
与结构分类的底层规则。**纯标准库，无第三方依赖。**

本包是从仓库根的历史脚本（`pot_all.py` / `pot_v2.py` / `pot_v3.py` / `pot_v4.py`）中
**抽取出来的内核**：算法逐字搬运、去掉硬编码路径、加上包结构与测试。原脚本保持不动，
仍可独立运行。

## 安装

```powershell
# 方式一：不安装，直接从仓库根使用（最简单）
cd <repo>
python -c "import alchemy; print(alchemy.simulate(['O','X','C']))"

# 方式二：可编辑安装（需要 setuptools）
pip install setuptools
pip install -e .
```

目录数据（同为大文件）需要先解压一次：

```powershell
python unpack_data.py
```

## 四个入口

```python
import alchemy

# 1) 大锅反应（完全反应）
mols = alchemy.simulate(["O", "X", "C"])          # -> [{'atoms': [...], 'edges': [...]}]
alchemy.simulate(["O", "X", "C", "F"])            # -> None（总价数 7，奇数，接不满）

# 2) 六边形摆放 + 严格校验
place = alchemy.embed(["O", "X", "C"], [(0, 1, 1), (0, 2, 2)])
ok, msg = alchemy.validate(place, ["O", "X", "C"], [(0, 1, 1), (0, 2, 2)])

# 3) 物质目录（84,225 条）
cat = alchemy.get_catalog()
rec = cat["OXC"]                     # {'formula','natoms','zh','atoms','edges','place','feed'}
print(cat.stats())

# 4) 骨架分类
out = alchemy.classify(["O", "X", "C"], [(0, 1, 1), (0, 2, 2)])
out["level6"]["blocks"]              # 6 级中间态骨架块 + 是否在 38 库
out["layers"]                        # 骨架层 / 连接层 / 终端层
out["skeleton"]["structure_theorem_ok"]
out["stable"]                        # 是否 F(自身组成) == 自身
```

## 规则版本

成键优先级在项目历史上有三套口径，``simulate(..., rules=8|9|11)`` 可切换。
**权威实现是内核 `alchemy.core.reactor`（单份参数化实现）；`pot_all.py` / `pot_v3.py` / `pot_v4.py`
只是保留的兼容/历史实现**：

| `rules` | 内核实现（兼容脚本） | 说明 |
|---|---|---|
| 8 | `alchemy.core.reactor`（兼容 `pot_all.simulate`） | 规则 1~8，并列取第一个 |
| 9 | 同上（兼容 `pot_v3.simulate`） | 追加规则 9（元素优先级） |
| **11** | 同上（兼容 `pot_v4.simulate`） | 追加规则 10/11（骨架块优先、链先于环）— **当前正式** |

新代码一律用默认的 `rules=11`。要复现历史数据（T8/T15/T37~T44 等）时用 `rules=9`。

## 测试

```powershell
python tests/run_all.py          # 全部
python tests/run_all.py reactor  # 只跑反应引擎
```

其中 `tests/test_equivalence.py` 是**差分测试**：随机投料下，内核产物必须与原
`pot_v4/pot_v3/pot_all` 逐项一致（含 6 级骨架块与返回顺序）。改动成键规则会让它立刻失败。

## 目录结构

```
alchemy/
  __init__.py        公开 API（四个入口，另有 trace）
  core/
    elements.py      元素表、价数、周期表距离、六边形偏移、分子式
    canon.py         分子同构规范形（mol_label，真·同构不变量）
    geometry.py      摆放搜索与严格校验（修复了旧 L 中点 bug）
    reactor.py       大锅反应引擎（规则 1~11，可切 8/9）
    catalog.py       84,225 条物质目录（只读索引，路径可配置）
    classify.py      骨架分类（38 库 / 6 级块 / 三层拆解 / 结构定理）
  phase.py           三轴判相（v4 hybrid 默认：两两并列循环压制、三者全等归聚、无第四相）
  ability.py         能力（v3 三项数值 + v4 九项次级能力 × 三阶；旧 512 离散体系冻结为历史接口）
  attrs.py           物性（密度 / 粘性 / 温度 → 3³ = 27 格）
  biome.py           群系物种表（模板结果 → 丰度谱 / 导出 CSV·JSON）
  data/
    forms38.json     38 形态库（= 仓库根 t8_forms.json）
tests/               不依赖 pytest 的 124 项测试与差分验证
```

口径说明看 `docs/ABILITY.md`（能力）、`docs/TRAITS.md`（27 格物性）、`docs/BIOME_SPEC.md`（群系物种表）。
旧口径文档 T71~T76 均已加"历史/已被取代"横幅，只作背景。

## 数据来源与口径提醒

仓库里同时存在规则 1~8 / 1~9 / 1~11 三种口径的数据，详见 `docs/CALIBER_DIVERGENCE.md`。
对本内核而言：**分子式层不受影响，结构层受影响**（84,225 条中有 14,745 条被替换为 1~11 口径）。
