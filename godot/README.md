# godot/ —— 交互式前端项目

本目录放 Godot 前端项目；它们只做"交互沙盒 / 可视化"，**规则权威始终在 `alchemy/` 内核包与根目录脚本**里，前端通过 Python 侧车（TCP JSON）调用。

## 项目一览

| 目录 | 项目 | 说明 | 文档 |
|---|---|---|---|
| `chem_lab/` | **ChemLab 九元素化学实验场**（Godot 4.7） | 把 T83~T91 规则做成交互沙盒：投料、调参（重力/三素力/温度/反应）、观察分层·成团·反应·生长；支持存档/CSV/截图 | [`chem_lab/README.md`](chem_lab/README.md)、[`chem_lab/docs/CHEMLAB_PARAMS.md`](chem_lab/docs/CHEMLAB_PARAMS.md) |

## 环境要求

- **Godot 4.7.x**（`project.godot` 里 `config/features` 声明 `4.7`；GL Compatibility 渲染，集显可跑）。
- **Python 3.11**（`python` 在 PATH 中），且本仓库根目录已解压大目录数据（`python unpack_data.py`）。
- Windows 下双击 `chem_lab/run_lab.bat` 即可一键启动（内部先起 Python 内核服务再开游戏）。

> 跨机器使用：`run_lab.bat` / `run_kernel.bat` 顶部的 `GODOT`/`PYTHON` 路径按本机实际安装位置修改，不要提交本机绝对路径。

## 约定（重要）

- **不提交** Godot 导入缓存与运行产物：`.godot/`（每项目自带 `.gitignore` 兜底）、`*.import` 之外的临时文件、`*.err`、`shot*.log`、`selftest_out.log`、`screenshot_check.png`、截图测试文件。
- **提交**：`project.godot`、`*.tscn`、`scripts/*.gd` 与 `.gd.uid`、`preview.png` + `preview.png.import`（Godot 4.4+ 需要 uid/import 保持引用稳定）、启动脚本、README 与参数手册。
- 存档写在 Godot 的 `user://`（仓库外），不进入版本库。
- 每个项目一个子目录，新增项目按 `godot/<项目名>/` 放置并在此表登记。
- 前端只读内核：`kernel_server.py` 通过 `import` 使用 `natural_engine` / `alchemy`，不修改仓库文件。

## 与仓库其他部分的关系

- `alchemy/`：规则 1~11 内核（resolve / complete_products / three_su 力参数 / attrs 三轴）——前端所有物理与反应数值都来自这里。
- `docs/`：规则与研究口径（`THREE_AXES_FINAL.md`、`PHASE_RULE.md`、`T83_ENV_AXES.md`、`T87_ENV_ASYM.md`、`THREE_SU_AXES.md`、`T91_TRIPLE_SEARCH.md` 等）。
- 进展记录写在本机协作区：`progress/<机器名>/`（`CURRENT.md` + `log/`），不在本目录堆积临时笔记。
