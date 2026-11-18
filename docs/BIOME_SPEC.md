# 生物群系物种表（BIOME SPEC）

> 目标：一次"宇宙爆炸"实验的终态丰度谱 → 一张能驱动地图生成的**物种表**。
> 代码：`alchemy/biome.py`；数据：`data/biomes/*.csv|json`
>
> **本文档的范围限制（2026-11-17 项目决定）**：
> 命名暂不做；不擅自把物质归类成地表/矿物/植被/生物；生态层的判据、物种寿命暂不考虑。
> 表只输出**客观量**，归类与命名留给设计决策。

---

## 1. 一句话

```
世界   = 多个群系模板拼接
模板   = 一次大爆炸实验（元素配比 + 冷却曲线）
物种表 = 终态丰度谱 × 结构分类 × 性质系数
地图   = 用「丰度」定生成频率，用「储量」定矿脉/森林总量，用「体形/属性」定形态
```

## 2. 表的字段（每行 = 一个物种 = 一个分子式）

| 字段 | 含义 | 地图生成怎么用 |
|---|---|---|
| `formula` | 分子式（唯一主键） | 素材 id |
| `label` | 机械标识 `元素中文串·结构`，如 `秩晶冰·链` | 仅用于人读，**不是游戏名** |
| `natoms` | 原子数 | 占格 / 体形 / 碰撞箱 |
| `count` | 该世界的个体数 | 原始数量 |
| `abundance` | 占分子总数比例 | **生成频率** |
| `atom_abundance` | 占原子总数比例 | 质量占比（地表覆盖率） |
| `reserve_units` | `count × natoms` | **储量**（矿脉/森林总限量） |
| `stable` | `F(组成) == 自身`？ | 暂不使用（见 §5） |
| `in_catalog` | 是否在 84,225 条已验证目录 | `false` = 新物质，需单独审 |
| `category` | 三价骨架种类 | 区分"有无骨架" |
| `skeleton_blocks` | 6 级骨架块（38 库） | 器官原型 / 外形依据 |
| `layer_counts` | 骨架/连接/终端三层原子数 | "骨—肉—刺"比例 |
| `divalent_roles` | 桥/链段/支臂等计数 | 连接方式（刚性/铰接/软连） |
| `props` | 9 项属性 + 接口数 | 数值平衡 |
| `shape` | 团/星/环/链/孤核（`孤核` 仅当 `natoms <= 1`） | 地图轮廓 |

`props`：`mass / hp / strength / flex / resist / energy / mobility / sense / attack` +
`slots`（接口数 = 端帽数 + 真桥数，衡量可改造性）。系数来自
`docs/T18D_DESIGN_DIMENSIONS.md`，是**可调的基础值**。

**表里没有** `tier` 和 `name`。需要时显式开启：

```python
rows = B.abundance_table(run, with_tier=True, with_names=True)   # 可选
rows = B.abundance_table(run)                                    # 默认：只有客观量
```

## 3. 群系模板目录（挑模板用）

`template_catalogue(paths)` 给每个模板一行**描述性指标**，不涉及生态归类：

| 指标 | 含义 | 怎么用 |
|---|---|---|
| `effective_species` | `exp(Shannon 熵)`，等效物种数 | 1.0 = 单调世界；20 = 高度发散 |
| `dominance` | 第 1 名的质量份额 | 越大越单调 |
| `top2_mass_share` | 前 2 名质量份额 | 判断是不是"两物质世界" |
| `singleton_fraction` | 只出现 1 个的物种占比 | 高 = 尾部是噪声 |
| `n_ge5` | ≥5 原子的物种数 | "看得出形状"的有几个 |
| `max_natoms` | 最大体形 | 世界能否长出大东西 |

实测（12 个已有模板，按发散度升序）：

| 模板 | 物种 | 分子 | 等效物种 | top1 质量 | top2 | 单例% | ≥5原子 | 最大 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| t55_kinetic | 9 | 5,974 | **1.0** | 99.1% | 99.3% | 0.0% | 6 | 8 |
| t57_area | 4 | 12,054 | **1.6** | 75.9% | 99.7% | 0.0% | 2 | 8 |
| t63_phase1 | 4 | 12,032 | 1.7 | 75.7% | 99.3% | 0.0% | 2 | 8 |
| t56_kinetic | 22 | 9,020 | 2.8 | 51.6% | 81.0% | 45.5% | 17 | 22 |
| t62_phaseB | 43 | 51,937 | 2.8 | 74.4% | 95.6% | 37.2% | 34 | 40 |
| t63_phase2 | 7 | 11,129 | 3.1 | 59.3% | 88.0% | 0.0% | 4 | 9 |
| t62_phaseA | 43 | 34,476 | 3.4 | 71.1% | 91.5% | 34.9% | 35 | 40 |
| t63_phase3 | 5 | 20,082 | 3.6 | 40.5% | 68.3% | 0.0% | 1 | 5 |
| t63_phase4 | 14 | 17,227 | 4.5 | 61.9% | 76.9% | 21.4% | 11 | 40 |
| t59_phaseB | 67 | 38,609 | 6.2 | 33.3% | 62.0% | 80.6% | 63 | 40 |
| t59_phaseA | 43 | 27,431 | 6.3 | 37.2% | 62.5% | 79.1% | 39 | 40 |
| t58 | 937 | 15,823 | **20.6** | 8.9% | 17.5% | **74.9%** | 918 | 20 |

读法（供参考，不是规则）：

- `effective_species ≈ 1`：单调世界，适合当沙漠/戈壁/冰原这类"底材单一"的地貌；
- `≈ 3~7`：有若干共存物质的"正常世界"；
- `> 10` 且 `singleton_fraction` 高：尾部是**退火未完成**的动力学噪声，建议丢弃（T58 就是）。

## 4. 复现

```powershell
$env:PYTHONIOENCODING="utf-8"
cd <repo>

# 单个模板
python -c "import alchemy.biome as B; r=B.load_result('t62_phaseB_result.json'); rows=B.abundance_table(r); B.to_csv(rows,'data/biomes/t62B.csv'); print(B.render_markdown(rows, top=15))"

# 模板目录（只取 12 个群系模板；勿用 't*_result.json' 通配——仓库根有 50+ 个 *_result.json）
python -c "import alchemy.biome as B; from pathlib import Path; import json; T=('t55_kinetic','t56_kinetic','t57_area','t58','t59_phaseA','t59_phaseB','t62_phaseA','t62_phaseB','t63_phase1','t63_phase2','t63_phase3','t63_phase4'); c=B.template_catalogue([Path(t+'_result.json') for t in T], with_props=False); json.dump(c, open('data/biomes/_catalogue.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)"

python tests/run_all.py biome
```

> 数据口径：`data/biomes/` 下 12 个模板的 `label` / `shape` 已按**当前内核（rules=11）**
> 复算刷新（旧快照曾把 `链` / `环` 误记为 `孤核`）；`candidates/_union.json` 的
> `spec.source` 已统一为相对文件名。需要复核时重跑上面的复现命令即可。

## 5. 暂缓项（明确记下来，避免以后重复讨论）

| 项 | 状态 | 说明 |
|---|---|---|
| 游戏内命名 | **暂缓** | 只保留机械标识 `label`；`biome_names.json` 的覆盖机制已就绪，随时可用 |
| 生态层归类（地表/矿物/植被/生物） | **暂缓** | `assign_tier` 已实现但默认关闭；阈值是建议值，不是项目决定 |
| 层的判据（丰度 vs 属性） | **待定** | 丰度阈值 vs 属性门槛，两条路都留了口子 |
| 物种寿命 / 亚稳物质 | **待定** | 完全退火世界里 `stable` 恒为真，暂无区分度；部分退火世界才有用 |
