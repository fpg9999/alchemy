# ALCHEMY（炼金术化学系统）

这是元素反应/骨架分类/自然环境的完整研究工作区。

**第一次接手请先读 [`HANDOFF.md`](HANDOFF.md)。**

> **最新进展（2026-11-18）**：2D 粒子环境实验已完成 **T55~T67** 系列——T59 两阶段九元素
> （三价最多）、T62 两阶段九元素（三/二/一价等量，收敛到 `OXCPWKA`+`LF` 1:1 双组分）、
> T63 聚素熔体逐级价数滴定（纯聚素退火 → 加 F2 → 加 A2 → 加 K2，每次投放都整体换代）、
> **T64 生态群系**（12 个"元素社区"：3~9 种元素、1000→25°C 退火 + 25°C 恒温浮动，
> 纯族收敛为单一三元分子，B08 形成 `O2X2P2W2K2` 十原子簇，B11 复现 `LF`+`OXCPWKA` 双组分）、
> **T65 生态群系第二轮**（10 个群系、每群系 ≥4 种元素：产物更杂更大更多新物质，
> 但纯杂由价数互补与端帽决定——C03 98.4% 单一 `XPLA`、C06 93.6% 十原子簇 `O2X2P2K2A2`、
> C09 缺 F 时 26 种/488 新物质；C10 与 T64 B11 同种子逐项复现）、
> **T66 生态群系第三轮（化合物播种）**（10 群系与 T65 一一对应，约 37.5%~60% 原子以化合物/
> 骨架投入：**终态组成余弦 10/10 对 ≥0.9999、top1 8/10 相同**，但 capped 平均少 980 次、
> 净事件少 19.8%——初始化学形态记忆≈0（组成）、路径记忆显著（动力学））、
> **T67 生态群系总目录**（32 个群系按终态专一性分四类：**A 单主 10 / B 主辅 11 / C 双主 7 /
> D 多主 4**；类别由元素角色配比 + 温度日程决定、初始形态无关；特色 Top10 见报告）；
> T61/T62/T63/T64 另有全部大分子的严格六边形棋盘格摆放图。详见
> [`docs/T67_BIOME_CATALOG.md`](docs/T67_BIOME_CATALOG.md)、
> [`docs/T66_BIOMES.md`](docs/T66_BIOMES.md)、[`docs/T65_BIOMES.md`](docs/T65_BIOMES.md)、
> [`docs/T64_BIOMES.md`](docs/T64_BIOMES.md)、
> [`docs/T63_STAGED_TITRATION.md`](docs/T63_STAGED_TITRATION.md)
> 与 [`docs/T62_EQUAL_VALENCE.md`](docs/T62_EQUAL_VALENCE.md)、[`docs/T60_SERIES_SUMMARY.md`](docs/T60_SERIES_SUMMARY.md)。
>
> **图形阶段（2026-11-17~18，最新）**：T68 大分子骨架形状语言 + 36 个 ≥14 原子稳定大分子图册
> （[`docs/T68_GIANT_ATLAS.md`](docs/T68_GIANT_ATLAS.md)、[`docs/T68_GLYPH_SYSTEM.md`](docs/T68_GLYPH_SYSTEM.md)）、
> T69 连接件与端帽（元素隐去版，[`docs/T69_SKELETON_SHAPES.md`](docs/T69_SKELETON_SHAPES.md)）、
> T70 生成式形状语言（超公式骨架 + 编织腱/褶幕桥 + 冰锥/飘带/螺旋丝端帽，
> [`docs/T70_EMERGENT_GLYPHS.md`](docs/T70_EMERGENT_GLYPHS.md)）、
> T70b 整体形体画法（块/桥/端帽并入同一剪影，一个分子看起来像一件完整物质，
> [`docs/T70B_WHOLE_BODY.md`](docs/T70B_WHOLE_BODY.md)）。

## 快速开始

1. 安装 Python 3.10+，并安装 Pillow（绘图脚本需要）：
   ```powershell
   pip install -r requirements.txt
   ```
2. 如果 `t4_catalog_all_validated.json` 等大文件不存在（clone 后通常只有 `_data_gz/`），先解压：
   ```powershell
   python unpack_data.py
   ```
3. 跑一个大锅反应示例：
   ```powershell
   python -c "import pot_v4; print(pot_v4.simulate(['O','K']))"
   ```

## 目录

- `pot_all.py` / `pot_v2.py` / `pot_v3.py` / `pot_v4.py`：大锅反应与几何校验核心（规则 1~11 以 `pot_v4.py` 为准）；
- `natural_engine.py` / `fast_pot.py` / `t55_kinetic_env.py`：自然环境引擎与 2D 粒子环境；
- `t4_*` ~ `t70b_*`：各阶段研究脚本/数据（编号=任务阶段）；
- `docs/`：全部研究报告（`T*.md`）；`docs/templates/` 放报告模板（如 `t60_report_template.md`）；
- `images/`：全部结果图（T68~T70b 的图册按 `t68_*`/`t69_*`/`t70_*`/`t70b_*` 命名）；
- `_data_gz/`：大数据的 gzip 版本 + `manifest.json`（GitHub 传输用）；
- `tools/`：跨电脑传输工具（`make_transfer_archive.py` 重新生成全量 zip、`pack_transfer_data.py` 打包 `_data_gz/`）；
- `archive/`：历史脚本与旧数据，已按阶段/主题分子文件夹（`archive/README.md` 有对照表）。

## 跨电脑交接

见 [`TRANSFER.md`](TRANSFER.md)：GitHub / 全量 ZIP / git bundle 三种方式。
2026-11-18 清理时已删除工作区里 2026-11-14 的旧 ZIP / bundle 快照（内容已被 GitHub 上的 T01~T70b 覆盖）；
需要新的离线包时运行 `python tools\make_transfer_archive.py` 重新生成。
