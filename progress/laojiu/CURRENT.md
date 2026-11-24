# 牢⑨ 当前状态

> 滚动更新；历史见 `progress/laojiu/log/`。最后更新：2026-11-24 11:40

- **机器 / 昵称**：本机（Windows 10 + DSH），昵称「牢⑨」
- **工作目录**：`G:\AI work\deepseek\work1\alchemy`
- **远程**：`https://github.com/fpg9999/alchemy`（`main`）
- **最近一次同步**：**2026-11-24 T96 追加修复**（reset 残留：清并行数组 + ping 排空内核队列；随机投料 seed）`6e6ac47`，推送 `3cf2bb8..6e6ac47`；此前 **2026-11-24 T96 分子运动修复**（半径连续化 + ChemLab 推挤链/团簇动量/整团平移）`bfc09a2`，推送 `9050259..bfc09a2`，`main...origin/main` = `0 0`；此前 **2026-11-24 T95 碰撞/推挤**（删布朗 + 质量/受力/动量推挤 + A/B 18 组）`396b867`，推送 `3545a87..396b867`，`main...origin/main` = `0 0`；此前 08:30 例行 `f8cce83`、T94 生命综合调查 `55675df`、T93 保护膜 `6b88a1b` 及核验 `b291641`/`3545a87`
- **当前本地**：与 `origin/main` 一致（T96 追加修复 `6e6ac47`，工作树干净）；T96 已提交（`alchemy/three_su.py` 连续半径 + t82/t83/t87/t90 封顶 + `sim.gd`/`main.gd` 推挤/动量/整团平移 + `docs/T96_MOTION.md`/`T96_CHEMLAB.md`）；T95 产物已提交（`t95_config.py`/`t95_collision.py`/`t95_run.py`/`t95_render.py`、`docs/T95_COLLISION.md` + `docs/T95_COLLISION_DESIGN.md`、`t95_ab.json` 1.8MB、3 张图、删布朗 6 脚本 + 8 文档处）；运行日志一律不入库；tracked 约 1,758 文件
- **每日例行**：08:30 定时（`schedule-249fe7ef-…`）：拉取远端 → 删除无用生成物 → 更新文档 → 提交推送 → 核验远程，并更新本文件与当日 log。提醒偶尔漏投递，恢复后按批次补跑并补记 log（见 `log/2026-11-21.md`、`log/2026-11-23.md`）

## 正在进行 / 下一步

- **T96 追加修复已完成并推送（2026-11-24）**：用户 m01643/m01655 反馈「重置后同配置第二局完全不同」——根因 `sim.gd` 并行数组未随 reset 清空（旧 id 残留坐标/半径/吸引力/alive），修复 + 三局验证（13,646/396/179 → 13,661/13,556/12,755）；随机投料 seed 读输入框；selftest 240 拍 N=343；tests 150/150；详见 `docs/T96_CHEMLAB.md` §10
- **T96 分子运动修复已完成并推送（2026-11-24）**：用户 m01396 指令——半径连续化（`R_att=clamp(Q,1,R_MAX)`、`R_rep=clamp(round(0.7Q),1,R_MAX)`，R_MAX 默认 12；Python 世界按 force_r 封顶；ChemLab r_cap=12），ChemLab P1 链式推挤（Kmax=6、J_A/J_B、e=0.2）+ P2 团簇动量（γ=0.15、Vmax=2）+ 2b 整团净力平移；headless 240 拍 rows mean 91.7→75.8~76.5、n_push 78~94、整团 1,922~1,999、1.3×；tests 150/150；断弱键仍 TODO；报告 `docs/T96_MOTION.md` + `docs/T96_CHEMLAB.md`
- **T95 碰撞/推挤已完成并推送（2026-11-24）**：删除全部布朗运动；新增 PushWorld（阶段 0/1/2，质量+受力+动量链式推挤，参数可调 e=0.2/µ=0.25/Kmax=6/Vmax=2/γ=0.15）；A/B 18 组×600 拍 163.65s，18/18 守恒、A1~A5 全过、链长严格 ≤6、性能 1.79×；v2 G=0 把 PK/双层膜保护恢复到 envC=0/cov 1.00，G=0.2 把 PK envC 9,344→4,901、双层 584→0，但不修复沉降（cov 0.36~0.42）；无膜对照部分条件接触反升；报告 `docs/T95_COLLISION.md`（含 §13 Lead 复核）
- **T94 生命综合调查已完成并推送**：A 自复制普查（2,596 模板 / 24,708 组 / 模板作用 0 / 二元催化 0/946,946）、B 完美膜 10 臂（PK+G=0：envC 0、coreER 0、cov 0.92；G=0.2 重膜失效；自制造身体 48→102 +212%）、C 环境谱系（8 族生存矩阵；危险度来自环境热值；本地冷壳救 6 环境；repel 13/16,000）、D 七判据梳理；综合报告 `docs/T94_LIFE_SURVEY.md`，6 条模型扩展建议见其 §8（模板依赖、同分异构体、可逆膜-主体键、真正催化位点、隔室化补膜、持续能源）
- **T93 保护膜（冰壳）已完成并推送**：静态 6,492 冷壳候选 + 434,964 对排斥统计 + 9 臂动态；综合报告 `docs/T93_MEMBRANE.md`；遗留 5 条模型扩展建议见该文档 §8
- 维持每日 08:30 例行；对方机器在 `minimal-force` 分支工作（`bb4d1d5`），合回 `main` 时按 `progress/README.md` 约定处理
- 每个新阶段在 `docs/T*.md` 与 `HANDOFF.md` 维护记录里登记，并在本目录写当天 log
- 双机协作：本文件即本机进展的权威入口；共享约定见 `progress/README.md`

## 待办 / 已知坑（本机）

- 断弱键（可断键/熔化）后续实现（用户 m00963 明确先不做但要记着）
- T96 后旧 T81~T95 半径/长程力数字不可比：T94/T95 正式报告需按新规则重跑（本轮只做 smoke，临时 outdir）；若 Python 世界也要长程力，需调大 force_r 后重跑
- 热运动/最小扩散：无布朗后净力 0 的对称团完全静止（物理上合理但观感像“死”），待设计温度驱动速度
- GitHub token：用户曾称插入 `alchemy/googitcode/github.txt`，实际不存在（目录都没有）→ 待重新提供（用于 gh CLI / API 推送）
- `alchemy/emergence.py` 仍按旧 attrs 字段（density/stickiness）取值，与新 attrs（mass/state/temperature）不兼容 → 需另开任务修
- tag `kernel-0.2.0` 仍在本地未推
- 沙箱内 `git push` 会因凭据助手 `sh.exe` 无法创建命名管道而失败，需在 danger-full-access 下推送；网络不稳时「fetch 重试 + push 重试」
- GitHub 连通：系统 DNS 会把 `github.com` 解析到不可达 IP（如 `57.155.223.240`/`20.247.166.64`）。可用本地 CONNECT 代理 `G:\AI work\deepseek\work1\gh_proxy.py`（`python gh_proxy.py 8899 20.27.177.113`，后台任务）配合 `git -c http.proxy=http://127.0.0.1:8899`；若各 IP 直连 curl 全 000，等 1~2 分钟再试（区域性短时封锁）
- 本机同一工作目录可能有另一个 DSH 代理并发提交（T82~T92、ChemLab 均为其产出）：提交前后 `git status`/`git log` 复核，push 前先 `git fetch`
- 仓库体积约 1.24GB、root 699 个平铺文件（历史阶段脚本/数据，BASE 硬编码路径，保持平铺）；`_data_gz/t12b_pairs.jsonl.gz` 41.3MB 为最大 tracked 文件
- 日常可清项：`__pycache__/`、`godot/chem_lab/.godot/`、根 `*.log`、`intake/tmp/`（均已 ignore）
- **运行日志不入库**：`t93_run.log`、`t94_run.log` 等由脚本 append，`.gitignore` 的 `*.log` 覆盖；2026-11-24 已把误入库的 `t94_run.log` 经 `git rm` 出库
