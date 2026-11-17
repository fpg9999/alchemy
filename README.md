# ALCHEMY（炼金术化学系统）

这是元素反应/骨架分类/自然环境的完整研究工作区。

**第一次接手请先读 [`HANDOFF.md`](HANDOFF.md)。**

> **最新进展（2026-11-17）**：2D 粒子环境实验已完成 **T55~T62** 系列——T59 两阶段九元素
> （三价最多）、T62 两阶段九元素（三/二/一价等量，收敛到 `OXCPWKA`+`LF` 1:1 双组分）；
> T61/T62 另有全部大分子的严格六边形棋盘格摆放图。详见 [`docs/T62_EQUAL_VALENCE.md`](docs/T62_EQUAL_VALENCE.md)
> 与 [`docs/T60_SERIES_SUMMARY.md`](docs/T60_SERIES_SUMMARY.md)。

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
- `t4_*` ~ `t62_*`：各阶段研究脚本/数据（编号=任务阶段）；
- `docs/`：全部研究报告（`T*.md`）。
- `images/`：全部结果图。
- `_data_gz/`：大数据的 gzip 版本 + `manifest.json`（GitHub 传输用）。
- `archive/`：历史脚本与旧数据。

## 跨电脑交接

见 [`TRANSFER.md`](TRANSFER.md)：GitHub / 全量 ZIP / git bundle 三种方式。
