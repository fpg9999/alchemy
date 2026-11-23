# 牢⑨ 当前状态

> 滚动更新；历史见 `progress/laojiu/log/`。最后更新：2026-11-23 19:00

- **机器 / 昵称**：本机（Windows 10 + DSH），昵称「牢⑨」
- **工作目录**：`G:\AI work\deepseek\work1\alchemy`
- **远程**：`https://github.com/fpg9999/alchemy`（`main`）
- **最近一次同步**：**2026-11-23 晚间 T93 保护膜（冰壳）综合**：`6b88a1b T93: 保护膜（冰壳）综合——冷壳分子筛选、保温/排斥定量、9 臂动态验证`（26 files，+183,325/−2），推送 `a3ed282..6b88a1b` 成功（经本地 CONNECT 代理 `gh_proxy.py` 8899；首推遇 GitHub 短时不可达，恢复后重试成功），`main...origin/main` = `0 0`；此前 2026-11-23 例行维护推送 `cbdfd34..39ef0c9`（仅文档）
- **当前本地**：与 `origin/main` 一致，工作树干净（仅忽略项）；tracked **1,713** 文件（根 713 / images 530 / docs 132 / archive 187 / examples 35 / data 32 / alchemy 22 / godot 19 / tests 15 / intake 8 / _data_gz 7 / progress 7 / reports 3 / tools 2），工作树约 796MB（不含 `.git`）
- **每日例行**：08:30 定时（`schedule-249fe7ef-…`）：拉取远端 → 删除无用生成物 → 更新文档 → 提交推送 → 核验远程，并更新本文件与当日 log。提醒偶尔漏投递，恢复后按批次补跑并补记 log（见 `log/2026-11-21.md`、`log/2026-11-23.md`）

## 正在进行 / 下一步

- **T93 保护膜（冰壳）已完成并推送**：静态 6,492 冷壳候选 + 434,964 对排斥统计 + 9 臂动态；综合报告 `docs/T93_MEMBRANE.md`；遗留 5 条模型扩展建议见该文档 §8（斥力公式对 D=0 生效、壳自修复、τ 场回写 rho/gate、双层+支撑面、C2 气态口径修正）
- 维持每日 08:30 例行；对方机器在 `minimal-force` 分支工作（`bb4d1d5`），合回 `main` 时按 `progress/README.md` 约定处理
- 每个新阶段在 `docs/T*.md` 与 `HANDOFF.md` 维护记录里登记，并在本目录写当天 log
- 双机协作：本文件即本机进展的权威入口；共享约定见 `progress/README.md`

## 待办 / 已知坑（本机）

- `alchemy/emergence.py` 仍按旧 attrs 字段（density/stickiness）取值，与新 attrs（mass/state/temperature）不兼容 → 需另开任务修
- tag `kernel-0.2.0` 仍在本地未推
- 沙箱内 `git push` 会因凭据助手 `sh.exe` 无法创建命名管道而失败，需在 danger-full-access 下推送；网络不稳时「fetch 重试 + push 重试」
- GitHub 连通：系统 DNS 会把 `github.com` 解析到不可达 IP（如 `57.155.223.240`/`20.247.166.64`）。可用本地 CONNECT 代理 `G:\AI work\deepseek\work1\gh_proxy.py`（`python gh_proxy.py 8899 20.27.177.113`，后台任务）配合 `git -c http.proxy=http://127.0.0.1:8899`；若各 IP 直连 curl 全 000，等 1~2 分钟再试（区域性短时封锁）
- 本机同一工作目录可能有另一个 DSH 代理并发提交（T82~T92、ChemLab 均为其产出）：提交前后 `git status`/`git log` 复核，push 前先 `git fetch`
- 仓库体积约 1.24GB、root 699 个平铺文件（历史阶段脚本/数据，BASE 硬编码路径，保持平铺）；`_data_gz/t12b_pairs.jsonl.gz` 41.3MB 为最大 tracked 文件
- 日常可清项：`__pycache__/`、`godot/chem_lab/.godot/`、根 `*.log`、`intake/tmp/`（均已 ignore）
