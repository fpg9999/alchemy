# alchemy 内核审计报告

- **审计对象**：`G:\AI work\deepseek\work1\alchemy`，HEAD `4a2e4d6`「kernel: 抽出 alchemy 内核（四入口 + 106 项测试）」，工作区干净（`git status --porcelain` 为空；运行测试产生的 `__pycache__` 被 `.gitignore` 忽略）。
- **审计范围**：内核包全部源码、`pyproject.toml`、`tests/` 全部、`examples/demo_kernel.py`；只读仓库，未修改任何仓库文件。
- **审计环境**：Windows，Python **3.11.3**（`C:\Users\123\AppData\Local\Programs\Python\Python311\python.exe`），setuptools 65.5.0，无 `pytest`、无 `wheel`。
- **方法**：通读源码；实跑测试/demo；在 `intake/tmp/` 下做只读实验（不污染仓库）；用 git 对象核对文件漂移；用 manifest + sha256 核对数据完整性。
- **实验脚本与原始日志**（均在 `G:\AI work\deepseek\work1\intake\tmp\`）：`exp2.py`/`exp2.txt`、`exp3.py`/`exp3.txt`、`exp4.py`/`exp4.txt`、`exp5.py`/`exp5.txt`、`level6_edge.py`、`defs.txt`（全部模块顶层 def/class/常量与行号）、`tests_out.txt`（测试输出全文）。

> 下文路径除特别说明外均相对**仓库根** `G:\AI work\deepseek\work1\alchemy`（包内文件写作 `alchemy/…`，仓库根层级写作 `./…`）。行号对应提交 `4a2e4d6`。

---

## 一、总体结论

| # | 结论 | 判定 |
|---|---|---|
| 1 | 四个入口 `simulate` / `embed`+`validate` / `get_catalog` / `classify` 与 README 逐条一致，示例可直接运行 | ✅ 实测 |
| 2 | `python tests/run_all.py` → **106/106 PASS**（24.4s / 27.0s 两次），exit 0 | ✅ |
| 3 | 目录 84,225 条成立（`stats()`：total 84225、max_natoms 97、le16 82961、missing_place 245）；文件 sha256 与 `_data_gz/manifest.json` 记录一致 | ✅ |
| 4 | 14,745 条 1~11 口径替换有文档、脚本、汇总三方佐证；抽样 800 条结构 100% 与 `rules=11` 引擎自洽 | ✅ 强证据（原始逐条清单未入库） |
| 5 | `alchemy/data/forms38.json` 与仓库根 `t8_forms.json` **字节级完全相同**（同 sha256） | ✅ |
| 6 | 缺 `t4_catalog_all_validated.json` 时报错文案明确指向 `python unpack_data.py`；`unpack_data.py` 在干净副本中可一次解压并 sha 校验通过 | ✅ |
| 7 | 导入内核不读大文件、无网络/写盘副作用（import 约 0.10s，`_CACHE` 为空） | ✅ |
| 8 | `pyproject.toml` 打包声明能带上 `alchemy/data/*.json`；tests/examples 不进包；39MB 目录数据按设计不进包 | ✅ 模拟 `build_py` 验证；真实 wheel 未验证（环境无 `wheel`） |
| 9 | `rules=8/9/11` **不是逐项复用** `pot_all/pot_v3/pot_v4`，而是单份参数化重写；等价性由差分测试保证 | ⚠️ 结论成立，但覆盖是抽样 |
| 10 | 主要风险：`get_catalog` 无锁且返回可变共享缓存；`place` 键 str/int 双轨；`demo_kernel.py` 在 GBK 控制台崩溃；`phase.py` 文档与 `__all__` 漂移；测试依赖仓库根大数据且未验证 pytest 路径 | ⚠️ 见第七、八节 |

**一句话**：内核抽取质量高、声明基本可信；问题集中在“缓存/并发/表示一致性/文档漂移”这类工程健壮性，而非算法正确性。

---

## 二、模块地图

### 2.1 目录与文件

| 文件 | 行数/大小 | 职责 | 依赖 | 外部 IO |
|---|---|---|---|---|
| `alchemy/__init__.py` | 90 行 / 2986B | 公开 API 汇总、四入口再导出 | core 全部 + `biome`/`phase`（**急切导入**） | 无 |
| `alchemy/README.md` | 96 行 / 3768B | 内核用法、规则版本表、测试命令 | — | — |
| `alchemy/core/elements.py` | 199 行 / 7449B | 9 元素表、价数、周期表距离、六边形偏移、分子式 | 纯标准库 | 无 |
| `alchemy/core/canon.py` | 125 行 / 4533B | 分子同构规范形（1-WL + 分支定界） | elements | 无 |
| `alchemy/core/geometry.py` | 184 行 / 7136B | 摆放搜索 `embed`、严格校验 `validate` | elements | 无 |
| `alchemy/core/reactor.py` | 295 行 / 11730B | 大锅反应引擎，规则 1~11 可切 8/9/11 | elements | 无 |
| `alchemy/core/catalog.py` | 185 行 / 6786B | 84,225 条目录的加载/查询/缓存/路径解析 | elements | 读 39MB JSON |
| `alchemy/core/classify.py` | 443 行 / 17445B | 骨架分类（38 库、6 级块、三层、结构定理） | reactor、canon、elements | 读 `data/forms38.json` |
| `alchemy/phase.py` | 457 行 / 19107B | 三相（骨架/状态/能量）理论：`phase_of`/`describe` 等 | elements | 无 |
| `alchemy/ability.py` | 155 行 / 5631B | 8 情形 × 3 轴 = 512 能力编号 | elements | 无 |
| `alchemy/attrs.py` | 252 行 / 9559B | 硬度/黏性/温度三属性与档位 | elements、catalog（字符串输入时） | 间接读目录 |
| `alchemy/biome.py` | 604 行 / 27465B | 生物群系：物种表、物性、分层、导出 CSV/JSON/MD | classify、catalog、elements | 读结果 JSON、可选写文件 |
| `alchemy/data/forms38.json` | 103,930B | 38 形态库（35 多三价形态 + 7 单三价模板在代码里） | — | 读 |
| `alchemy/data/biome_names.json` | 754B | 物种中文名映射（`save_names` 默认写回这里） | — | 读/写 |
| `pyproject.toml` | 26 行 / 704B | 打包/依赖/pytest 配置 | — | — |
| `tests/` | 11 个 `test_*.py` + `run_all.py` + `_util.py`，106 用例 | 见第七节 | 依赖仓库根 `pot_*.py`、结果 JSON | 读 |
| `examples/demo_kernel.py` | 96 行 / 3577B | 四入口演示 | 无 | 无 |
| `examples/build_biome_candidates.py` | 249 行 / 12067B | **会写仓库**的候选群系生成器 | biome | 读根 JSON、写 `data/biomes/…` 与 docs |
| `examples/render_species_sheets.py` | 17,025B | 物种 PNG 图册（需 Pillow） | biome、Pillow | 写 PNG（本次未审） |

### 2.2 依赖方向

```
alchemy/__init__.py ──┬─→ core.elements, core.canon, core.geometry, core.reactor,
                      │   core.catalog, core.classify
                      ├─→ biome ──→ core.classify, core.catalog, core.elements
                      └─→ phase ──→ core.elements
    ability ──→ core.elements         （顶层未导入）
    attrs   ──→ core.elements + core.catalog（仅字符串输入时惰性取目录）（顶层未导入）
```

要点：

- `alchemy/__init__.py:70-71` 用 `from . import biome` / `from . import phase` **急切导入**，因此 `import alchemy` 会连带 `phase.py`、`biome.py`；但 `attrs`、`ability` 不在顶层导入（新进程里 `alchemy.attrs` 会 `AttributeError`，需显式 `import alchemy.attrs`）。
- 包内**没有**任何 `pot_all/pot_v2/pot_v3/pot_v4` 依赖，也没有 `t4_catalog_index.json` 引用（`t4_catalog_index.json` 8.3MB 对内核是死数据，仅 `unpack_data.py` 按 manifest 顺带解压）。
- `core/reactor.py:40` 只 `from .elements import TRI, VAL, family_rank, ptable_dist`，不 import 任何历史模块。

### 2.3 数据流

```
原子序列/分子式 ──elements.formula_of/parse_formula──→ 9 维计数向量
      │
      ├─ reactor.simulate(…, rules=8|9|11) → mols[{atoms,edges}] + level6（可选）
      ├─ geometry.embed/validate          → {下标:(q,r)}（六边形坐标）
      ├─ canon.mol_label                  → "OXC|102000"（同构规范形）
      ├─ catalog.get_catalog()            → 84,225 条记录（含 place）
      ├─ classify.classify(_record)       → level6/skeleton/layers/divalent/stable
      ├─ phase.phase_of/describe          → 骨架/状态/能量三相 + 物性名
      ├─ ability.ability_of               → "O|X|C" 能力编号
      ├─ attrs.attrs_of / property_of     → 硬度/黏性/温度 + 档位
      └─ biome.abundance_table/summary    → 生物群系物种表与导出
```

---

## 三、公开 API 签名表

### 3.1 四入口（README「四个入口」，`alchemy/README.md:28-52`）

| API | 精确签名（位置） | 返回结构 | 失败/边界 |
|---|---|---|---|
| `simulate` | `simulate(atom_list, rules: int = 11, return_level6: bool = False)` `alchemy/core/reactor.py:262` | `list[dict{"atoms": list[str], "edges": list[tuple[int,int,int]]}]`；`return_level6` 时 `(mols, level6)` | 价数和奇数/接不满 → `None`（`return_level6` 时 `(None,None)`）；`rules∉(8,9,11)` → `ValueError`（`reactor.py:96-97`） |
| `trace` | `trace(atom_list, rules: int = 11)` `reactor.py:288` | `dict{"mols","level6","bonds","atoms","steps"}`，失败 `None` | 同 simulate |
| `simulate_many` | `simulate_many(feeds, rules: int = 11)` `reactor.py:293` | `list`（逐投料 simulate 结果） | — |
| `embed` | `embed(atoms, edges, max_nodes: int | None = None, final_check: bool = True)` `alchemy/core/geometry.py:58` | `{原子下标: (q,r)}`（int 键）；`n==0 → {}`、`n==1 → {0:(0,0)}`（:68-71） | 不连通 → `None`（:90-91）；`max_nodes` 超限 → `None`（**"未判定"语义**，与 pot_v2 的 `False` 不同，:61-63、:111-112） |
| `embed_all` | `embed_all(mols, max_nodes=None, final_check=True) -> bool` `geometry.py:166` | 全部可摆放才 True | 任一 `None` → False |
| `validate` | `validate(place, atoms, edges) -> tuple[bool, str]` `geometry.py:28` | `(True,"ok")` 或 `(False,原因)` | `place` 可 dict 或坐标序列；`None → (False,"None")`；**只校验几何/键型，不校验每原子键级和==价数**（:45-55） |
| `to_place_dict` | `to_place_dict(place, atoms=None) -> dict[str, list[int]]` `geometry.py:174` | `{"0":[q,r],…}`（**str 键**，目录/JSON 用） | `None/{}` → `{}` |
| `get_catalog` / `load_catalog` / `clear_cache` | `get_catalog(path=None) -> Catalog` `alchemy/core/catalog.py:173`；`load_catalog(path=None)` :168；`clear_cache()` :183 | `Catalog` | 缺文件 → `FileNotFoundError`，文案含 "`python unpack_data.py`"（:84-85） |
| `classify` | `classify(atoms, edges, rules: int = 11, library: dict | None = None, place=None, check_stable: bool = True) -> dict` `alchemy/core/classify.py:240` | 见 3.4；传 `place` 时含 `bonds`；`check_stable` 时含 `stable` | `place` 需 `{int: (q,r)}`（docstring :250） |
| `classify_record` | `classify_record(rec, rules=11, library=None, check_stable=True)` `classify.py:430` | classify 结果 + `source`/`catalog_formula`，内部把目录 str 键 place 转 int | — |
| `classify_feed` | `classify_feed(atom_list, rules=11, library=None, check_stable=True)` `classify.py:395` | `{ok, feed, formula, rules, mols, summary{n_mols,formulas,all_in_library,all_stable,level6_blocks}}` | — |
| `block_label` / `load_library` / `classify_block` | `:69` / `:77` / `:114` | label 字符串 / `{multi,single,forms,n_forms,n_multi,n_single_templates,path}` / `{kind,in_library,library_formula,label}` | — |

`Catalog`（`catalog.py:61`）查询面：`__len__/__iter__/__contains__/__getitem__`、`get(formula,default=None)`、`formulas()`、`records()`、`by_natoms(n)`、`natoms_histogram()`、`feed(formula) -> tuple[int,…]`、`find_by_vec(vec)`、`stats() -> {total,natoms,max_natoms,le16,over16,missing_place,sources}`。

### 3.2 `phase.py`（三相理论，457 行）

| API | 签名（位置） | 返回 |
|---|---|---|
| `phase_of` | `phase_of(formula_or_vec, mode=DEFAULT_MODE, absent_mode=DEFAULT_ABSENT_MODE)` `:242` | `{formula,vec,mode,absent_mode,skeleton,state,energy,axes,id,names,label,n_tied_axes,n_fourth,n_absent}`；`label` 如 `"秩·固·冰"`，`id` 如 `"O/X/C"` |
| `axis_vote` / `axis_winner` | `:169` / `:233` | `{element,phase,count,kind(strict|two|three|absent),counts,tops}` / `(元素,最大计数,是否并列)` |
| `role_of` / `state_of` / `energy_of` | `:315` / `:342` / `:347` | 刚体/胶体/软体（附 `fourth_source`）/ 固/气/液 / `{energy,effect,fourth_source}` |
| `describe` | `:411` | 键：`formula,frame,state,energy,name,typical,hardness,density,cohesion,gravity,energy_effect,id` |
| `physical_name` | `:400` | `{概念形容词}{能量形容词}{物态名词}`，如 OXC→"刚性低温固体" |
| `phase_names/id/label`、`agree_axes`、`two_axis_table`、`distribution` | `:295,:300,:305,:310,:365,:447` | 名字元组 / id 串 / label 串 / 一致轴数 / 二维表 / 分布 dict |
| 常量 | `:73` `RULE9_PRIORITY`（与 `reactor.py:45` 重复定义，非共享）、`:142` `SUPPORTED_MODES=("hybrid","hierarchy","cycle")`、`:144` `ABSENT_MODES`、`:147` `DEFAULT_MODE="hybrid"`、`:148` `DEFAULT_ABSENT_MODE="fourth"`、`:151` `N_TYPES=27` | — |

### 3.3 `ability.py` / `attrs.py` / `biome.py`

| 模块 | 公开 API（位置） | 返回/说明 |
|---|---|---|
| ability | `axis_case(vec, trio)` `:70`、`case_name(axis_key, case)` `:90`、`ability_of(formula_or_vec)` `:95`、`distribution(formulas, axis=None)` `:129`、`catalog_combos(formulas)` `:139` | `ability_of` → `{formula,cases("O|X|C"),names,counts,id,label}`；`N_CASES=8`、`N_ABILITIES=512`（`:53-54`） |
| attrs | `molecule_attrs(atoms, edges=None)` `:103`、`attrs_of(formula_or_atoms, edges=None, catalog=None)` `:118`、`skeleton_units(atoms, edges)` `:151`、`grade(value, attr, thresholds=None)` `:232`、`property_of(attrs, thresholds=None)` `:242` | 权重 `HARD_W{O:3,K:2,P:1}`、`STICK_W{X:3,W:2,A:1}`、`TEMP_W{F:3,L:2,C:1}`；`GRADES=("低","中","高")`，阈值 `{hardness:(10,16),stickiness:(6,11),temperature:(3,6)}`；字符串输入经 `get_catalog()` 取结构，不在目录时 `error="not_in_catalog"` 且三值为 0 |
| biome | `load_result(path)` `:104`、`shape_label(classification)` `:176`、`properties(atoms, edges, classification=None)` `:211`、`systematic_name(formula, classification=None, props=None)` `:281`、`load_names/save_names` `:300/:312`、`assign_tier` `:322`、`tier_counts` `:357`、`abundance_table(run, *, rules=11, min_count=1, with_tier=False, tiers=None, with_names=False, names=None, catalog=None, library=None, with_props=True)` `:367`、`biome_summary` `:466`、`template_catalogue(paths)` `:519`、`to_csv/to_json/render_markdown` `:537/:565/:578` | 行字段：`formula,label,natoms,count,abundance,atom_abundance,reserve_units,stable,in_catalog,structure_source,category,in_library,skeleton_blocks,level6_sizes,shape,layer_counts,divalent_roles,props,attrs`（默认无 `tier`/`name`）；CSV 用 utf-8-sig、嵌套 JSON 串 |

### 3.4 `core` 其它公开函数

- `elements.py`：`element_category`、`valence`、`allowed`、`allowed_set`、`ptable_dist`（同类=价差、跨类=价和）、`family_rank`、`formula_of`、`zh_of`、`parse_formula`、`atoms_to_vec`、`vec_to_atoms`、`classify_offset`、`midpoint_of`（`:99-195`）。
- `canon.py`：`mol_label(atoms,edges)->str`（`:76`）、`canon_signature`（`:95`，预算 40000 超时退化原始标号）、`molecule_key`（`:114`）、`same_structure`（`:123`）。
- `reactor.py` 额外导出 `RULE9_PRIORITY`（`:45`）、`SUPPORTED_RULES=(8,9,11)`（`:47`）。

### 3.5 导出面差异（易踩）

1. **`phase.__all__`（`:61-70`）漏了 `describe` / `physical_name` / `FRAME_ADJ` / `ENERGY_ADJ` / `STATE_NOUN` / `TYPICAL` / `_PROFILE`**：`from alchemy.phase import *` 拿不到这些，但测试与 `alchemy.phase.describe` 直接属性访问都正常 → 说明 `__all__` 只是陈旧，不是缺失实现。
2. `alchemy.__all__`（`__init__.py:75+`）含 `biome`、`phase` 子模块名，不含 `ability`/`attrs`，也没有 `__getattr__` 惰性导入 → 新进程 `import alchemy; alchemy.attrs` → `AttributeError`（`import alchemy.attrs` 可以）。
3. `phase.py:1-53` docstring 仍是 **v2 口径**（说 `cycle` 是默认、只列两种模式、提到不存在的 `absent_as_fourth=False` 参数），与代码 `DEFAULT_MODE="hybrid"`（`:147`，v4 口径）矛盾。
4. `reactor.py:150` 的 `snapshot(..., want_all_components: bool)` 参数**未被使用**（函数体固定按"块内含三价原子"过滤，`:154`）；`pot_v4.py:180-181` 还留着 `for g in sorted(range(0)): pass` 死代码（历史遗留，非内核代码）。

---

## 四、`rules=8/9/11` 的实现路径（是否逐项复用 `pot_all/pot_v3/pot_v4`？）

**结论：不是逐项复用，而是把三代算法合并为一份参数化实现。**

证据：

1. `alchemy/core/reactor.py:40` 只 `from .elements import TRI, VAL, family_rank, ptable_dist`，**不 import 任何 `pot_*`**；`reactor.py:1-35` docstring 明写三套口径对应关系（8→`pot_all.simulate`、9→`pot_v3.simulate`、11→`pot_v4.simulate`，新代码用 11）。
2. 键函数是同一段代码按 `rules` 逐段追加（`reactor.py:202-215`）：
   - 基础 13 项（与 `pot_all.py:183-186` 逐项相同）；
   - `rules>=9` 追加 `_rule9_extra`（`:50-52`，与 `pot_v3.py:30-32` 同式，优先级表同为 `("O","X","C","K","A","F","P","W","L")`）；
   - `rules>=11` 追加规则 10（`blockid`）与规则 11（`_ring_flags` 链/环标志）。
3. 6 级块封口：`reactor.py:218-220` 在循环内 `if level6 is None and not any6` 时 `snapshot(...)`；`pot_v4.py:151-166` 在 `if not cands: break` 之后封口，且 `pot_v4.py:176-193` 还有循环结束后的兜底封口。二者等价（内核把兜底移进循环）：实测 `["O","K"]`、`["O","O"]`、`["P","K"]`、`["O","K","K","O"]`、`["O","K","O","K"]` 的 `level6` 与 mols 完全一致（见 `intake/tmp/level6_edge.py` 输出）。
4. 并列裁决：内核 `tied[0]`（`reactor.py:224-226`，候选生成顺序=下标序）；`pot_all.simulate` 在传 `rng` 时用 `rng.choice(tied)`、`rng=None` 时 `tied[0]`；`pot_v3`/`pot_v4` 也是 `tied[0]`。**内核没有 `rng` 参数**（规则 8 的随机裁决能力未搬入，README 只承诺"并列取第一个"，一致）。
5. 历史模块在仓库根且**带硬编码绝对路径**（`pot_v2.py:13`、`pot_v3.py:23`、`pot_v4.py:18` 均为 `sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")`），说明"去硬编码路径"只对内核包生效，原脚本按 README 保持不动。

**等价性验证口径**：`tests/test_equivalence.py` 用 `_util.load_originals()` 现场 import 四个历史脚本做差分（固定种子、每个规则 120~200 条 feed + 大投料），`test_equivalence` 6 项全绿。注意这是**抽样验证**，不是全量证明（见 7.3）。另做独立验证：随机 300 条目录记录 + le16 500 条，100% 与 `simulate(rules=11)` 的 `mol_label` 多重集一致（`intake/tmp/exp3.txt`）。

---

## 五、实测记录（命令 + 输出摘要）

### 5.1 全量测试

```
cd G:\AI work\deepseek\work1\alchemy
python tests\run_all.py
```
输出尾部：`ALL 106 TESTS PASSED  (24.4s)`（第一次），`ALL 106 TESTS PASSED  (27.0s)`（第二次，日志 `intake/tmp/tests_out.txt`），两次 exit 0。

单模块过滤（README 承诺）：

```
python tests\run_all.py reactor   →  ALL 10 TESTS PASSED  (0.2s)
```

分模块用例数：ability 10、attrs 11、biome 10、catalog 8、classify 13、elements 6、equivalence 6、geometry 7、phase 16、property 9、reactor 10，合计 **106**。11 个 `test_*.py`（任务描述里的"12 个"是含 `_util.py` 的笔误）。

### 5.2 `examples/demo_kernel.py`

```
python examples\demo_kernel.py                       → rc=1
  UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'（✓，表格行）
$env:PYTHONIOENCODING="utf-8"; python examples\demo_kernel.py   → rc=0，3.39s，46 行
```

四段均正常：simulate（OK/OXC/失败例）、embed（OXC 摆放 `{0:(0,0),1:(-1,0),2:(0,1)}`、非法摆放 `(False,'offset (5, 5) not allowed (O-C)')`）、catalog（84000+）、classify 表格（含 ✓/✗）。**缺陷：Windows 中文默认 GBK 控制台直接崩溃**，README 未提示 `-X utf8`/`PYTHONIOENCODING`（可用 `sys.stdout.reconfigure(encoding="utf-8")` 或避免 ✓ 修复）。

### 5.3 `examples/build_biome_candidates.py`

- **会写仓库**：生成 `data/biomes/candidates/{T55,T57,T63S4,T62B,T59B}.csv`、`_union.csv`、`_union.json`、`docs/BIOME_CANDIDATES.md`；无 `--help`/无 argv 处理，直接 `main()`；依赖仓库根 5 个结果 JSON（`t55/t57/t63/t62/t59`，均已被 git 跟踪）。因写仓库，本次**只读源码未运行**（符合只读约束）。用法即 `python examples/build_biome_candidates.py`。

### 5.4 `unpack_data.py`（干净副本实测）

```
复制 unpack_data.py + _data_gz 到 intake/tmp/unpack_test，运行：
首次 rc=0 wall=1.87s，6 条 ok：t12b_pairs.jsonl / t4_catalog_all_validated.json / …
      / t4_catalog_index.json，末行 done；解压后 catalog 39,150,742B，sha256 与 manifest 一致
重复运行 rc=0 0.50s，全部 ok (exists)
损坏 catalog 后再跑：打印 "exists but checksum differs; use --force to overwrite"，但 rc 仍为 0
```

小问题：校验失败/缺 gz 时只打印提示、**退出码仍 0**（`unpack_data.py:23-47`），CI 下会"假绿"。

### 5.5 导入、缓存与并发

| 项 | 实测 |
|---|---|
| `import alchemy`（新进程 wall） | 0.10s（模块内 0.060s）；`phase` 0.055s、`biome` 0.053s、`attrs` 0.063s、`ability` 0.066s、`core.catalog` 0.057s；导入后 `_CACHE` 为空、无大文件读取 |
| 首次 `get_catalog()` | 1.768s（39MB JSON）；`cat.stats()` = total 84225 / le16 82961 / over16 1264 / max_natoms 97 / missing_place 245 / sources {le16 82961, triple 999, search 265} |
| 4 线程同时 `get_catalog()` | 总 12.24s，4 个线程各拿到**不同对象**，最终缓存 1 条（**无锁，重复加载 4×39MB**）；单线程二次取同一对象 `is True`；`clear_cache()` 清空；`load_catalog()` 不缓存 |
| 缓存可变性 | `get_catalog()` 返回的记录是缓存内**可变 dict**：外部 `r["x_marker"]=1` 后再次 get 仍可见；`records()` 返回内部 list 本体 → 调用方可污染全局缓存 |

### 5.6 `place` 表示与 `classify`

- 目录 84,225 条中 83,980 条带 `place`，**键全是字符串**（`{"0":[q,r],…}`），且**没有**"键数≠natoms"的残缺 place（`exp5.txt:31-34`）。
- `classify(atoms, edges, place=rec["place"])` 直接传目录 place → **`KeyError: 1`**（`classify.py:360` 用 int 下标访问）；docstring（`:250`）要求 `{int:(q,r)}`，`classify_record` 内部转换后才可传。→ 公开 API 存在 str/int 双轨表示坑。
- `classify_record(OXC)` 返回键：`bonds,caps,catalog_formula,category,divalent,divalent_roles,formula,in_library,layers,level6,natoms,ok,rules,skeleton,source,stable,zh`；400 条 0.336s。

### 5.7 性能（单进程、冷缓存）

| 操作 | 耗时 |
|---|---|
| `attrs_of` 300 条 | 0.116s |
| `ability_of` 300 条 | 0.004s |
| `mol_label` 300 条 | 0.013s |
| `embed` 300 条（重新求解） | 0.014s，300/300 成功 |
| `abundance_table`（43 物种，全开 tier+names） | 0.163s |
| `phase_of` 500 条 | 0.008s |
| 最大记录（97 原子）`simulate` | 1.174s（产物 1 个分子 `O3X8C15P10WK36A22F2`） |
| `load_library()` | 0.005s（n_forms 38 / n_multi 35 / n_single_templates 7） |

### 5.8 打包与 pytest

- `build_py` 模拟（修正 `dist.script_name` 后）：输出 14 个文件，包含 `alchemy/data/biome_names.json`、`alchemy/data/forms38.json`，无缺失；`read_configuration` 可解析 pyproject（setuptools 报 `[tool.setuptools]` beta 警告，正常）。
- 真实 wheel **未验证**：本机 `pip wheel` 因缺 `wheel` 模块失败（`No module named 'wheel'`），且该 pip 子进程会僵死（已放弃并 kill；属环境问题，不是仓库缺陷）。README 的 `pip install -e .` 因此也**未在本机验证**。
- `pytest` 未安装（`No module named pytest`）→ README "也兼容 pytest" 与 `tests/run_all.py:8` 的承诺**未实测**。

### 5.9 其它观察

- `git ls-files` 确认：`alchemy/` 包 16 个文件、`tests/` 14 个文件、6 个结果 JSON（`t55/t57/t58/t59/t62/t63`）与 `t8_forms.json` 均被跟踪；39MB 目录与 `t12*` 大文件被 `.gitignore`（`:15` 等）排除，靠 `_data_gz` + `unpack_data.py` 传输 → clone 后必须先跑 `unpack_data.py` 才能跑大部分测试，与 README 一致。
- `catalog` 文件 sha256 = `2049a0cf…f4f2ab`，与 `_data_gz/manifest.json` 的 `orig_sha256`、`orig_bytes=39,150,742` 完全一致；6 个 manifest 条目的 `orig_bytes` 与磁盘文件大小全部匹配（`exp5.txt:4-11`）。

---

## 六、README/文档声明验证矩阵

| 声明（出处） | 验证方法 | 结果 |
|---|---|---|
| 纯标准库（`alchemy/README.md:4`） | 检查包内 import | ✅ 仅标准库（`json/os/gzip/csv/collections/pathlib` 等）；`render_species_sheets.py` 用 Pillow，但那是 optional extra `plots`，且不在内核包 |
| 算法"逐字搬运…原脚本保持不动"（`:6-8`） | 读源码 + diff 精神 | ⚠️ 算法等价但**不是逐字复制**：`reactor.py` 是新的参数化实现；`geometry.py` 修了 L 中点 bug 并改了 `max_nodes` 语义；文档用"逐字"略夸大 |
| 四入口示例（`:28-52`） | 实跑 demo + 手写调用 | ✅ 全部成立（含 `cat["OXC"]` 键、`out["level6"]["blocks"]` 等） |
| 目录 84,225 条（`:41`） | `cat.stats()` | ✅ total 84225、`len(cat)==84225` |
| 规则表 8/9/11 对应关系（`:58-62`） | 读 `reactor.py:1-35,202-215` + 差分测试 | ✅ 关系正确；实现是重写（见第四节） |
| 差分测试承诺（`:73-74`） | 实跑 + 读 `test_equivalence.py` | ✅ 存在且通过；⚠️ 抽样（固定种子、几百 feed） |
| `forms38.json` = 仓库根 `t8_forms.json`（`:89`） | sha256 + 字节 + JSON 深比较 | ✅ 同 sha256 `6372dba1…12a7`、103,930B、38 条 |
| 14,745 条替换为 1~11 口径（`:96`） | 读 `docs/CALIBER_DIVERGENCE.md`、`t52_replace_catalog.py`、`t52_replace_catalog.json` + 抽样 | ✅ 三方自洽：`t52_replace_catalog.json` 记录 `records 84225 / unchanged 69480 / replaced 14745 / place_computed 14717 / place_none 28 / sim_fail 0`；doc 给出 14,745 = 14,615（v3≠v4）+130（旧目录=v1）；doc 与实测 `missing_place=245`（=le16 24 + search 220 + triple 1，其中 28 条为 t52 place_none）吻合。⚠️ 逐条替换清单未入库，复现需重跑 `t52_replace_catalog.py`（约 952.7s，且会覆盖目录文件） |
| 需先 `python unpack_data.py`（`:22-26`） | 干净副本实跑 | ✅ 6 文件、1.87s、sha 校验通过；缺 catalog 时报错文案指向该脚本 |
| 不依赖 pytest（`tests/run_all.py:2-8`） | 实跑 run_all | ✅ 106 PASS；pytest 路径未测（环境无 pytest） |
| pyproject 打包（`pyproject.toml`） | 模拟 build_py + read_configuration | ✅ 带上 `alchemy/data/*.json`；不含 tests/examples；catalog 不进包（符合设计，但安装后必须外部提供目录文件） |

补充核对：`docs/CALIBER_DIVERGENCE.md`（32,111B）与 `alchemy/README.md` 的 17.51%、14,745、69,480、245、28 等数字互相一致；`catalog.py` 自身**没有**写 14,745（只在 README/docs 层），所以"catalog.py 与 CALIBER_DIVERGENCE.md 的衔接"是间接的——代码只负责加载被替换后的结果，不记录替换历史。

---

## 七、测试覆盖矩阵与脆弱点

### 7.1 逐文件覆盖矩阵

| 文件（用例数） | 覆盖点 | 关键断言 | 未覆盖/盲点 |
|---|---|---|---|
| `test_elements.py`（6） | 元素表/价数/键型集合/周期表距离/分子式往返/偏移分类 | `ptable_dist` 具体值（O-X=1、O-K=6、X-F=3…）、`classify_offset`/`midpoint_of` | `allowed_set`、`zh_of` 单独断言 |
| `test_canon.py` 无独立文件 → `test_classify.py` 间接 | `mol_label` 同构不变量 | 库命中/块标号 | `canon_signature`、`molecule_key`、`same_structure` 未直接测 |
| `test_geometry.py`（7） | embed/validate/单原子/空分子/目录摆放/与 pot_v2 对拍 | `embed([],[])=={}`、非法摆放三种、150 条目录 place 校验 | `embed_all`、`max_nodes` 边界（返回 None 的"未判定"语义）、大分子（97 原子）、与 pot_v2 **只比是否 None 不比坐标** |
| `test_reactor.py`（10） | 空/奇数价/已知案例/结构/确定性/顺序无关/幂等/原子守恒/规则切换/level6 格式 | 每原子 deg==VAL、3 个 pot_v4 自检案例、`SUPPORTED_RULES==(8,9,11)`、`rules=10` 抛错 | `simulate_many`、`rng` 行为（内核无此参数）、极端大投料 |
| `test_equivalence.py`（6） | rules 8/9/11 与 `pot_all/pot_v3/pot_v4` 差分、level6、返回顺序、bonds 重建 | 随机 120~200 feed + 大投料多重集相等 | 固定种子、几百样本、max_n 有限 → **非全量证明**；未覆盖 level6 兜底封口路径（本次手工补测 5 例相等） |
| `test_catalog.py`（8） | 数量/字段/已知物质/查询 API/feed 向量/与引擎一致性/路径/环境变量 | `len==84225`、`le16==82961`、`max_natoms==97`、`missing_place>0` | "与引擎≥70%"阈值**容忍 30% 旧口径**；未测 `find_by_vec` 多义、`__contains__/__iter__`、损坏文件 |
| `test_classify.py`（13） | 库覆盖/目录口径/feed/no_trivalent/奇数价/record/简单例/二价角色/融合键/已知 SKU/库加载/结构定理抽样/不稳定物质 | rules=11 自洽率>0.98 且 rules=9 低 0.05；结构定理抽样 | `classify_feed` 的 `all_stable` 分支、`classify_block` 的 `bad`/`no_trivalent` 分支、500+ 原子 |
| `test_phase.py`（16） | 27 型可达/缺席三态/九元素覆盖/目录不变量/三循环/无松散端/分布/相位确定/公式=向量/层级模式/混合模式/并列裁决/简单例/三轴第四相/双轴 | 默认 hybrid 无第四相、液>25%、电>20%、固<45% | `two_axis_table`、`phase_names/phase_label`、`distribution` 的 `absent_mode="none"` 之外组合 |
| `test_property.py`（9） | describe 字段/命名三段/无第四相/OXC+XA/向量入口/剖面排序/九格表/三 frame | `OXC`→"刚性低温固体"、`name==FRAME_ADJ+ENERGY_ADJ+STATE_NOUN` | 依赖 `phase.__all__` 未包含的私有/漏列符号（直接属性访问，`from … import *` 会失败） |
| `test_ability.py`（10） | 单/双/三/零情形/严格多数/ability_of/512 空间/命名/目录组合/分布 | `axis_case` 5 种形态、id/label | `distribution` 的求和之外统计、`case_name` 全组合 |
| `test_attrs.py`（11） | 逐原子累加/分子级/桥双属/无骨架/温度非负/权重表/阈值有序/目录抽样/档位/property_of/atoms+edges 入口 | 权重表精确值、OXC 3/3/1、O2XP2W2K2A2 stick=7 hard=12 | `skeleton_units` 直接返回、`grade` 边界值、`attrs_of` 的 `not_in_catalog` 分支 |
| `test_biome.py`（10） | 43 物种表/汇总/不同群系/默认无 tier/name/导出往返/加载/opt-in 命名/字段/模板排序 | 丰度和≈1、top2={OXCPWKA,LF}、CSV 不含 tier 列、JSON 不含 tier_counts | **依赖仓库根 4 个结果 JSON**（t57/t58/t62/t63，均被 git 跟踪）；`render_markdown`、`save_names`/`load_names` 写路径、`tier_counts` 未直接测；依赖 `biome_names.json` 内容 |

### 7.2 公开 API 中**未被测试直接覆盖**的函数

`geometry.embed_all`、`reactor.simulate_many`、`canon.canon_signature`/`molecule_key`/`same_structure`、`phase.two_axis_table`/`phase_names`/`phase_label`、`biome.render_markdown`/`tier_counts`/`save_names`/`load_names`、`attrs.skeleton_units`（仅间接）、`catalog.load_catalog`（仅经 `get_catalog`/`load_catalog` 各一次）、`Catalog.__iter__/__contains__`。

### 7.3 脆弱点清单

| 级别 | 问题 | 证据/复现 | 影响 |
|---|---|---|---|
| P1 | `get_catalog()` **非线程安全**，返回**可变共享对象**；`records()` 直接暴露内部 list | 4 线程并取 12.24s、4 个不同对象；外部改记录污染缓存（`exp3.txt`） | 多线程服务/长进程易重复加载 4×39MB 或数据被调用方改动 |
| P1 | `place` 表示双轨：目录/`to_place_dict` 用 **str 键**，`classify(place=…)` 要求 **int 键** | `classify(..., place=rec["place"])` → `KeyError: 1`（`classify.py:360`） | 用户按 README 直接传目录 place 会崩；需文档强调或加自动转换 |
| P1 | `demo_kernel.py` 在 Windows 默认 GBK 控制台 **必定崩溃**（`✓`） | `python examples\demo_kernel.py` → rc=1 `UnicodeEncodeError: 'gbk' … '\u2713'` | 新用户第一印象失败；README 未提示编码 |
| P2 | `phase.py` 文档与代码漂移：docstring 仍写 v2/cycle 默认，`__all__` 漏 6 个公开符号 | `phase.py:1-53` vs `:147`；`:61-70` | 文档误导 + `import *` 少符号 |
| P2 | 测试**依赖仓库根大数据**：`t57/t58/t62/t63` 结果 JSON + 39MB 目录；无 `skipIf` 守卫 | `test_biome` 直接 `REPO/"t62_phaseB_result.json"`；`test_catalog` 直接 84225 | 未 `unpack_data` 或数据被清理时整批测试红，错误信息不友好 |
| P2 | `test_catalog_matches_engine` 阈值仅 **≥70%** | `test_catalog.py:80` | 目录中 30% 旧口径结构可悄悄存在而不被测试发现 |
| P2 | 差分测试为**抽样**：固定种子、120~200 feed、max_n≤11/20 | `test_equivalence.py` 种子 20261117/99/1234/555/31415/2718 | 规则实现回归的证明力有限；极端元素配比可能漏检 |
| P2 | `pytest` 兼容路径**未验证**（环境无 pytest）；`run_all.py` 用裸 `assert`，`python -O` 下会**静默跳过全部断言** | `python -m pytest --version` → No module named pytest | README "也兼容 pytest"、CI 用 `-O` 时的假绿 |
| P2 | `phase.RULE9_PRIORITY` 与 `reactor.RULE9_PRIORITY` **重复定义**（`:73` / `:45`），仅靠 `test_phase.priority_reuses_rule9` 守护 | grep 两处 | 未来改一处忘另一处会分叉 |
| P3 | `unpack_data.py` 校验失败/缺 gz 时 **exit code 仍 0** | `unpack_data.py:23-47`（`missing gz:` / `checksum differs` 后继续） | CI 假绿 |
| P3 | `geometry.embed(max_nodes=…)` 语义与 pot_v2 不同（`None`=未判定 vs `False`=失败），未测试 | `geometry.py:61-63,111-112` vs `pot_v2.embed_mol2` | 迁移旧代码时语义误读 |
| P3 | `save_names` 默认写**包内** `data/biome_names.json` | `biome.py:300-320` | 安装到只读 site-packages 后写失败；测试未覆盖写路径 |
| P3 | `Catalog` 无 mtime/版本失效机制；替换目录文件后需手动 `clear_cache()` | `catalog.py:168-185` | 长进程拿到旧目录 |
| P3 | `alchemy.attrs`/`alchemy.ability` 未顶层导入，`__all__` 也不含 | `__init__.py:41-71,75+` | `import alchemy; alchemy.attrs` → AttributeError |
| P3 | `test_env_var_override(tmp_path=None)` 的 `tmp_path` 参数未被使用（pytest fixture 注入但与断言无关） | `test_catalog.py:90` | 无害，但说明未真正按 pytest fixture 设计 |
| P3 | 库/lib 路径：`tests/_util.load_originals()` 依赖仓库根历史脚本；若后续清理 `pot_*.py`，差分测试立刻失效 | `_util.py` | 测试与历史脚本耦合 |

### 7.4 关于浮点/性能/线程安全的结论

- 浮点：属性累加为整数权重（float 表示），测试用整数相等断言（3.0/12.0/7.0）与 `== 6.0` 等，**没有引入除法误差**；`abundance` 求和用容差（`≈1`），合理。`phase`/`attrs` 无数值积分，无浮点脆弱性。
- 性能：单条分类 0.8ms、属性 0.4ms、reactor 9 元素 1ms；**最大 97 原子 1.17s**（`simulate` 的候选/连通块每步重算，O(n²·V) 级别）；`embed` 对测试样本很快但最坏回溯无上界（`max_nodes=None` 默认），大分子/畸形键表可能爆炸。
- 线程安全：模块级 `_CACHE`/`_LIB_CACHE` 均无锁（`catalog.py`、`classify.py`），`get_catalog` 并发重复加载已实测；`load_library` 有 `_LIB_CACHE` 但同样无锁（加载仅 5ms，风险低）。`reactor/geometry/phase/ability/attrs` 均为纯函数或只读，无共享可变状态。

---

## 八、建议（按优先级）

**P1（会影响用户/生产正确性）**

1. `catalog.py`：给 `_CACHE` 加 `threading.Lock`（或 `lru_cache` 双检锁）；`get_catalog` 返回前做 `copy.deepcopy`（或至少 `records()` 返回副本）避免缓存污染；可选按 `(path, mtime, size)` 失效。
2. `classify.py`：`place` 参数入口自动识别 str/int 键（一行归一化），并在 docstring/README 明确"目录 place 是 str 键，`classify_record` 会转换"；或让 `Catalog.__getitem__` 返回 int 键副本（会破坏现有目录数据，不推荐）。
3. `examples/demo_kernel.py`：避免非 GBK 字符（或 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`），并更新 README 提示 Windows 编码。

**P2（文档/测试可信度）**

4. 重写 `phase.py` 顶部 docstring 至 v4 口径；补齐 `__all__`（`describe/physical_name/FRAME_ADJ/ENERGY_ADJ/STATE_NOUN/TYPICAL`）。
5. `phase.py` 从 `reactor` 导入 `RULE9_PRIORITY`，消除重复定义。
6. 测试加数据守卫：`test_biome`/`test_catalog` 在缺文件时 `skip` 并给出 `python unpack_data.py` 提示；`test_catalog_matches_engine` 阈值改为统计报告 + 对已知旧口径白名单断言，而非固定 70%。
7. 差分测试扩大：种子多样化、加 `max_n=20~30` 与极端 9 元素配比、把本次手工补的 level6 兜底封口例（OK/OO/OKKO）纳入用例；CI 至少跑一次 `python tests/run_all.py` 且禁止 `-O`。
8. 在 `alchemy/README.md` 补一段"已知坑"：`place` 键类型、`get_catalog` 缓存可变、demo 编码、pytest 未内置依赖。

**P3（易用性/清理）**

9. `unpack_data.py` 校验失败时返回非 0。
10. `embed` 恢复/文档化 `max_nodes` 语义（`None`=未判定），迁移指南里写清与 pot_v2 `False` 的区别。
11. `alchemy/__init__.py` 增加 `__getattr__` 惰性导入 `attrs`/`ability`（或文档说明子模块需显式 import）。
12. 清理 `reactor.py:150` 未用参数、`pot_v4.py:180-181` 死代码（后者属历史脚本，可不动）。
13. 若 `t4_catalog_index.json` 确实无用，考虑从 manifest/仓库移除（8.3MB 冗余传输）。

---

## 九、附录

### 9.1 关键文件位置索引

- 四入口与依赖：`alchemy/__init__.py:41-71`、`alchemy/core/reactor.py:262`、`alchemy/core/geometry.py:28,58`、`alchemy/core/catalog.py:61,168-185`、`alchemy/core/classify.py:240,395,430`
- 规则实现：`alchemy/core/reactor.py:45-52,85,176-235`；对照 `pot_all.py:183-186`、`pot_v3.py:30-32`、`pot_v4.py:117-193`
- 路径解析/报错：`alchemy/core/catalog.py:39-96,136`
- 三相：`alchemy/phase.py:73,142-151,169,233,242,315-365,400-457`
- 属性/群系：`alchemy/attrs.py:103-260`、`alchemy/biome.py:104,176,211,281,300-320,367,466,519-600`
- 测试：`tests/run_all.py:17-65`、`tests/_util.py:11-43`、`tests/test_equivalence.py`
- 数据/打包：`pyproject.toml`、`unpack_data.py`、`_data_gz/manifest.json`、`.gitignore:2,11-20`

### 9.2 复现命令（只读，均在仓库根执行）

```powershell
python tests\run_all.py                     # 106 PASS, ~24s
python tests\run_all.py reactor             # 10 PASS
$env:PYTHONIOENCODING="utf-8"; python examples\demo_kernel.py
python -c "import alchemy; c=alchemy.get_catalog(); print(c.stats())"
python -c "import alchemy; print(alchemy.phase.phase_of('OXC')['label'])"
# 干净副本解压验证（写 intake/tmp，不动仓库）：
#   复制 unpack_data.py + _data_gz 到 intake/tmp/unpack_test 后 python unpack_data.py
```

### 9.3 本次审计的边界（未做/未验证）

- 未做真实 `pip install .` / wheel 构建（环境缺 `wheel`）、未验证 `pip install -e .`（README 方式二）。
- 未验证 pytest 运行路径（环境无 pytest）。
- 未运行 `examples/build_biome_candidates.py`（**会写仓库**，违反只读约束）；仅静态审阅。
- 未审 `examples/render_species_sheets.py`（需 Pillow，超出内核范围）。
- 未全量逐条复跑 14,745 替换（需重跑 `t52_replace_catalog.py`，约 16 分钟且会覆盖目录文件）；以 sha256 + 800 条抽样 + 三方文档自洽为准。
- 未做 fuzz/属性测试（随机长键表、畸形 edges、超长 formula 等）。
