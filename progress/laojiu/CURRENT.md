# 牢⑨ 当前状态

> 滚动更新；历史见 `progress/laojiu/log/`。最后更新：2026-11-24 08:31

- **机器 / 昵称**：本机（Windows 10 + DSH），昵称「牢⑨」
- **工作目录**：`G:\AI work\deepseek\work1\alchemy`
- **远程**：`https://github.com/fpg9999/alchemy`（`main`）
- **最近一次同步**：**2026-11-24 凌晨 T94 生命综合调查（四分支）**：`T94: 生命综合调查——自复制普查/完美膜/环境谱系/文献梳理 + 综合报告``55675df2bfe9b4722a2b3bf937c6edbb849ac94e`，`main...origin/main` = `0 0`（经本地代理 8899→20.205.243.166 推送，重试第 1 次成功）；此前 2026-11-23 晚间 T93 保护膜（冰壳）综合 `6b88a1b`（26 files，+183,325/−2）推送 `a3ed282..6b88a1b` 成功（经本地 CONNECT 代理 `gh_proxy.py` 8899）
- **当前本地**：与 `origin/main` 一致（`b291641`），工作树干净；T94 产物已提交（`docs/T94_*.md` 5 份、`t94_*.py` 5 个、`t94_census.json` 7.9MB、`t94_life.json` 633KB + 10 份臂 JSON、`t94_envmap.json`、7 张图）；2026-11-24 例行把误入库的 `t94_run.log` 出库（运行日志一律不入库）；tracked 约 1,744 文件
- **每日例行**：08:30 定时（`schedule-249fe7ef-…`）：拉取远端 → 删除无用生成物 → 更新文档 → 提交推送 → 核验远程，并更新本文件与当日 log。提醒偶尔漏投递，恢复后按批次补跑并补记 log（见 `log/2026-11-21.md`、`log/2026-11-23.md`）

## 正在进行 / 下一步

- **T94 生命综合调查已完成并推送**：A 自复制普查（2,596 模板 / 24,708 组 / 模板作用 0 / 二元催化 0/946,946）、B 完美膜 10 臂（PK+G=0：envC 0、coreER 0、cov 0.92；G=0.2 重膜失效；自制造身体 48→102 +212%）、C 环境谱系（8 族生存矩阵；危险度来自环境热值；本地冷壳救 6 环境；repel 13/16,000）、D 七判据梳理；综合报告 `docs/T94_LIFE_SURVEY.md`，6 条模型扩展建议见其 §8（模板依赖、同分异构体、可逆膜-主体键、真正催化位点、隔室化补膜、持续能源）
- **T93 保护膜（冰壳）已完成并推送**：静态 6,492 冷壳候选 + 434,964 对排斥统计 + 9 臂动态；综合报告 `docs/T93_MEMBRANE.md`；遗留 5 条模型扩展建议见该文档 §8
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
- **运行日志不入库**：`t93_run.log`、`t94_run.log` 等由脚本 append，`.gitignore` 的 `*.log` 覆盖；2026-11-24 已把误入库的 `t94_run.log` 经 `git rm` 出库
