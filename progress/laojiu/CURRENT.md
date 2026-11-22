# 牢⑨ 当前状态

> 滚动更新；历史见 `progress/laojiu/log/`。最后更新：2026-11-22 18:45

- **机器 / 昵称**：本机（Windows 10 + DSH），昵称「牢⑨」
- **工作目录**：`G:\AI work\deepseek\work1\alchemy`
- **远程**：`https://github.com/fpg9999/alchemy`（`main`）
- **最近一次同步**：2026-11-22 整理轮推送 `2336866..`（本机产出 `ea4a982` T91、`a7af5e1` ChemLab、`727e229` T92 + 整理提交 `c5e5779`，共 4 个；随后成果与 godot 整理为第 5 个提交：补 `docs/T91_TRIPLE_SEARCH.md`、`godot/README.md`、`godot/chem_lab/.gitignore` 与索引同步；远程 HEAD 与本地一致、`0 0`）
- **当前本地**：与 `origin/main` 一致，工作树干净（仅忽略项）；`docs/` 128→129（+T91 报告）、`godot/` 17→19（+README/.gitignore）
- **每日例行**：08:30 定时（`schedule-249fe7ef-…`）：拉取远端 → 删除无用生成物 → 更新文档 → 提交推送 → 核验远程，并更新本文件与当日 log。提醒偶尔漏投递，恢复后按批次补跑并补记 log（见 `log/2026-11-21.md`）

## 正在进行 / 下一步

- 维持每日 08:30 例行；对方机器在 `minimal-force` 分支工作（`bb4d1d5`），合回 `main` 时按 `progress/README.md` 约定处理
- 每个新阶段在 `docs/T*.md` 与 `HANDOFF.md` 维护记录里登记，并在本目录写当天 log
- 双机协作：本文件即本机进展的权威入口；共享约定见 `progress/README.md`

## 待办 / 已知坑（本机）

- `alchemy/emergence.py` 仍按旧 attrs 字段（density/stickiness）取值，与新 attrs（mass/state/temperature）不兼容 → 需另开任务修
- tag `kernel-0.2.0` 仍在本地未推
- 沙箱内 `git push` 会因凭据助手 `sh.exe` 无法创建命名管道而失败，需在 danger-full-access 下推送；网络不稳时「fetch 重试 + push 重试」
- 本机同一工作目录可能有另一个 DSH 代理并发提交（T82~T92、ChemLab 均为其产出）：提交前后 `git status`/`git log` 复核，push 前先 `git fetch`
- 仓库体积约 1.24GB、root 699 个平铺文件（历史阶段脚本/数据，BASE 硬编码路径，保持平铺）；`_data_gz/t12b_pairs.jsonl.gz` 41.3MB 为最大 tracked 文件
- 日常可清项：`__pycache__/`、`godot/chem_lab/.godot/`、根 `*.log`、`intake/tmp/`（均已 ignore）
