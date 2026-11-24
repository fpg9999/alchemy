# 跨电脑交接方案（ALCHEMY）· 最新成果版

> 最后更新：**2026-11-24**（**T96 分子运动修复**：用户 m01396 指令「改 1、3 条 + 统一半径 + 全部同步 ChemLab」。半径连续化 `R_att=clamp(Q,1,R_MAX)`、`R_rep=clamp(round(0.7Q),1,R_MAX)`，R_MAX 默认 12（Python 世界按 force_r 封顶、ChemLab r_cap=12）；ChemLab 新增 P1 链式推挤（Kmax=6、J_A/J_B、e=0.2）与 P2 团簇动量（γ=0.15、Vmax=2）+ 整团净力平移；headless 240 拍 rows mean 91.7→75.8~76.5、n_push 78~94、整团 push 1,922~1,999、1.3×、tests 150/150；断弱键仍 TODO；旧 T81~T95 半径数字不可比，报告 `docs/T96_MOTION.md` + `docs/T96_CHEMLAB.md`）。此前：**T94 生命综合调查**：现有规则 + 今晚新默认参数 **T0=200°C→终态 0°C、p_react=1.0、G=0.20、env_coupling=0.5**（`t94_config.py`，ChemLab 已同步）。四分支：**A 自复制普查** 2,596 模板 / 2,411 个有食物拆分 → 24,708 组，最小 `A2F2+A2+F2→2A2F2`（4 原子、≥26°C、放热+8、窗口 204 拍），但 `F(compB+compC)=[A]` 80/80 ⇒ **模板作用=0**、二元催化 0/946,946；**B 完美膜 10 臂×600 拍**：PK 膜 + G=0 → 环境-主体接触 0、核心-环境反应 0、角覆盖 0.92、膜留存 89%，默认 G=0.2 重膜下沉失效（cov 0.00、接触 8,782 反超无膜），轻膜 W2/WA2 cov 0.67~0.78 但密封不足，自修复净消耗 3.7×，**自制造身体成立 48→102 原子（+212%）**；**C 环境谱系 8 族×5 候选**：危险度不来自攻击物 D 而来自环境热值（E3 D>0=96.3% 但 p_cold=0.07；E8 D>0=0% 却 p_cold=0.56），主体可存活 E2/E3/E4、需膜 E1/E5/E6/E7、E8 不可存活，本地冷壳 O4XK2/O2X 可救 6 环境，16,000 对 repel 仅 13 对；**D 文献梳理**：七判据仅边界/生长有证据、复制与选择完全缺失。**综合：模型内最接近生命的是「O2/OK 主体 + PK/W2 膜（需 G≈0）+ O4XK2/O2X 冷壳 + XA3/C2K2 食物 + E4/E2/E3 环境」组合，能长大/被保护/有自复制化学式，但仍不是生命**；报告 `docs/T94_LIFE_SURVEY.md`（+ T94_REPLICATION / T94_LIFE_SIM / T94_ENV / T94_HISTORY）。此前：**2026-11-23**（**T93 保护膜（冰壳）综合**：C2 类低温分子能否做膜、保温 + 隔绝外来分子——静态扫 6,492 冷壳候选（O10XK4/O7XK3/O6XK2 等 O–X–K 冰岩）、434,964 对壳×攻击物 **repel=0.000%**、动态 9 臂×600 拍核心存留 11/24→21~24、外来-核心接触 3,202→172~275、保温仅瞬态（峰值差 12.8~48.6°C、600 拍末内部仍 302~325°C）、G=0.30 塌膜；**结论：挡分子可行（占格+牺牲层）、保温只延迟（需持续冷源）、力场排斥不可行、高温完全不反应做不到；C2 做最外层牺牲层、OXC/O10XK4 保温、双层最优、需微重力 G≤0.02**；报告 `docs/T93_MEMBRANE.md`；此前：**2026-11-22**（T92 群系全扫 + ChemLab 交互升级 + 成果/godot 整理轮；此前：把"聚/散/动"落成可计算点值 + 配对公式——聚素=吸引力（O3/X2/C1）、散素=覆盖半径（K3/A2/F1）、动素=排斥力（P3/W2/L1）；84,225 全目录校准（同种净吸 80,396 = 95.5%、强粘 69,046 = 82.0%、无作用/自斥 3,829 = 4.5%）、方阵环面 8 邻域动态验证（强吸引成团 max_comp 4~5）、夜间 κ 网格 25×3×3 定性不变（选择性 0.772~0.829）；**诚实结论：力是动力学加速器而非终态决定者**，体生长需不对称机制（T80 模型）；报告 `docs/THREE_SU_AXES.md`。此前：**T80 组装体生长**（能长但无边界/遗传/复制/稳态、抓取并入是脚本化步骤 → 不算生命）、**T79 自催化生命搜索**（84,225 目录内无单分子自催化生命，只有端帽聚合物生长体）、**T78 九元素三轴环境实验**（质量→重力、物态→碰撞、温度→恒素富集 r=0.957，三臂跑通但不收敛）、**物质三轴定稿 `c438fef`**（质量/物态/温度 + 27 格行为表，测试随之 151→150 项）；本轮 T78~T81 与整理记录一起推送，HEAD 见 §6.1）
> 工作目录：`G:\AI work\deepseek\work1\alchemy`
> 交接入口：`HANDOFF.md`（最新结论以它为准）；本文件负责"如何迁移/同步"。
> 远程仓库：**https://github.com/fpg9999/alchemy**

---

## 0. 当前状态（2026-11-24）

| 项目 | 状态 |
|---|---|
| 本地仓库 | `G:\AI work\deepseek\work1\alchemy`，分支 `main` |
| 远程仓库 | `https://github.com/fpg9999/alchemy`（`origin/main` = **`396b867` T95 碰撞/推挤**；其下依次 `3545a87` progress 核对、`f8cce83` 2026-11-24 例行、`b291641` T94 文档同步、`55675df` T94 生命综合调查、`c907658` T93 文档同步、`6b88a1b` T93 保护膜综合、`a3ed282` ChemLab 修复 + `8b97f5e`/`e404c7f`/`d63c8df`/`da600ff`/`41920dd` 共 6 个 ChemLab 提交、`c5e5779` 2026-11-22 整理、`727e229` T92 + ChemLab 升级、`a7af5e1` ChemLab、`ea4a982` T91、`2336866`/`5be747a` progress 双机协作区、`1b2860c` T90 … `8acde64` T84；远端另有分支 `minimal-force`） |
| 双机协作 | 本机昵称「牢⑨」；进展写在 `progress/laojiu/`（`CURRENT.md` + `log/YYYY-MM-DD.md`），另一台主机自建 `progress/<name>/`；协作规则见 `progress/README.md`（只写自己目录、共享文档只追加、推前 `git fetch`+`rebase`、不做 force push） |
| 认证 | Git Credential Manager 已存 `fpg9999` 的 GitHub 凭据（`cmdkey` 中 `git:https://github.com`）；`gh` CLI 未登录，但不影响 git push |
| 推送 | **已推送（2026-11-24）**：T95 碰撞/推挤 `3545a87..396b867`（27 项变更；其后仅进度文档）；T94 生命综合调查 `c907658..55675df`（39 files；经本地 CONNECT 代理 `gh_proxy.py` 8899 → 20.205.243.166 推送；多次 `OpenSSL ... unexpected eof while reading` / `Proxy CONNECT aborted` 后由重试脚本第 1 次成功），`main...origin/main` = `0 0`。**已推送（2026-11-23）**：T93 保护膜综合 `a3ed282..6b88a1b`（26 files，+183,325/−2；经本地 CONNECT 代理 `gh_proxy.py` 8899 推送；首推遇网络短时不可达，恢复后重试一次成功），`main...origin/main` = `0 0`；此前（2026-11-22）T84~T90（`8acde64`→`1b2860c`）、progress 双机协作区（`5be747a`/`2336866`）、T91（`ea4a982`）/ChemLab（`a7af5e1`）/T92（`727e229`）均已在远程，最后随 2026-11-22 整理 `c5e5779` 与成果/godot 整理推送；tag `kernel-0.2.0` 仍留本地未推 |
| 最新成果 | **T95 碰撞/推挤规则（2026-11-24，最新）**：删除全部布朗运动（代码 6 文件、文档 8 处）；新增「质量+受力+动量」链式推挤（`t95_collision.py`，阶段 0/1/2，参数 `t95_config.py` 可调，默认 e=0.2/µ=0.25/Kmax=6/Vmax=2/γ=0.15）；A/B 18 组×600 拍 163.65s：18/18 元素守恒、A1~A5 全过、链长严格 ≤6、性能最慢 1.79×；v2 在 G=0 把 PK/双层膜保护恢复到 envC=0、cov=1.00，G=0.2 把 PK envC 9,344→4,901、双层 584→0，但不修复重膜沉降（cov 0.36~0.42）；无膜对照部分条件下接触反升；报告 `docs/T95_COLLISION.md`、设计 `docs/T95_COLLISION_DESIGN.md`、图 `images/t95_*.png` 3 张。**T94 生命综合调查（2026-11-24）**：在现有规则 + 今晚新默认参数（T0=200°C→0°C、p_react=1.0、G=0.20、env_coupling=0.5，`t94_config.py` + ChemLab 已同步）下四分支：**A 自复制** 2,596 模板 / 2,411 有食物拆分 → 24,708 组，最小 `A2F2+A2+F2→2A2F2`（4 原子、≥26°C、窗口 204 拍），但 `F(compB+compC)=[A]` 80/80 ⇒ 模板作用=0、二元催化 0/946,946；**B 完美膜** 10 臂×600 拍：PK 膜 + G=0 → 环境-主体接触 0、核心-环境反应 0、角覆盖 0.92、膜留存 89%；默认 G=0.2 重膜下沉失效，轻膜 W2/WA2 覆盖 0.67~0.78 但密封不足，自修复净消耗 3.7×，**自制造身体 48→102 原子（+212%）**；**C 环境谱系** 8 族：危险度来自环境热值而非攻击物 D（E3 D>0 96.3% 但 p_cold 0.07；E8 D=0 却 p_cold 0.56），裸主体可存活 E2/E3/E4、需膜 E1/E5/E6/E7、E8 不可存活，本地冷壳 O4XK2/O2X 可救 6 环境，16,000 对 repel 仅 13；**D 文献** 七判据仅边界/生长有证据。**综合：最接近生命 =「O2/OK 主体 + PK/W2 膜（需 G≈0）+ O4XK2/O2X 冷壳 + XA3/C2K2 食物 + E4/E2/E3 环境」组合，能长大/被保护/有自复制化学式，但仍不是生命**；报告 `docs/T94_LIFE_SURVEY.md`（+ T94_REPLICATION / T94_LIFE_SIM / T94_ENV / T94_HISTORY），图 `images/t94_*.png` 7 张。**T93 保护膜（冰壳）综合（2026-11-23）**：回答 T89「生命还差一层膜」——静态 `t93_static.py` 全扫 84,225 目录得 6,492 个严格冷壳候选（w_self top3 = O10XK4 2.424 / O7XK3 2.396 / O6XK2 2.381，全为 O–X–K 冰岩；含 C 小冰壳 O4XCK 等），434,964 对壳×攻击物 repel=0.000%（斥力项要求双方含动素，F/O 攻击物 D=0）；保温模型 A：600°C 下 OXC d=3 → 9.67°C、O10XK4 d=2 → 6.70°C，1000°C 下 O10XK4 d=2 → 8.51°C。动态 `t93_membrane.py` 9 臂×600 拍（核心 `C3K3F2`×24 + 壳 OXC/C2/X2C2/双层 OXC+OP + 400°C 攻击浴 + τ 热场）：核心存留 11/24（无壳）→ 21~24，外来-核心接触 3,202 → 172~275，但保温仅瞬态（峰值差 12.8~48.6°C，600 拍末内部仍 302~325°C），壳被壳-浴反应消耗（300→17~161），G=0.30 核心 24→1。**结论：挡分子可行（占格+牺牲层）、保温只延迟（需持续冷源/热汇）、力场排斥不可行、高温完全不反应做不到；C2 做最外层牺牲层、OXC/O10XK4 保温、双层最优、需微重力 G≤0.02**；报告 `docs/T93_MEMBRANE.md`（综合）+ `docs/T93_STATIC.md` + `docs/T93_SIM.md`，图 `images/t93_*.png` 7 张。**T92 群系网格（2026-11-21，最新）**：336 个 3/4/5 元元素子集全扫（160×110、700 分子、400 拍、10°C 恒温），平均 HHI 0.056→0.027→0.018、优势种最高 27.3%、**无 A 单主**（B 主辅 29 / D 多主 307），终态种数 42/120/246 与投料池 r=0.970；报告 `docs/T92_BIOME_GRID.md`、图 `images/t92_biome_grid.png`。**T91 三元组搜索（2026-11-21）**：551 种 2~5 原子小分子 → 151,525 对 → 38,312 组 `(A,B,C)`，四类化学条件筛后仅 **4 组**（全 7 原子富 F 主体：`O2AF4+OAF+OF3`、`O2WF4+OWF+OF3`、`XK2F4+XKF+KF3`、`XP2F4+XPF+PF3`）；报告 `docs/T91_TRIPLE_SEARCH.md`。**ChemLab（2026-11-21）**：Godot 4.7 前端 + Python 内核侧车，把 T83~T91 规则做成可交互沙盒（参数面板/预设/存档/CSV/截图），入口 `godot/chem_lab/run_lab.bat`、说明 `godot/README.md`。**2026-11-22 整理轮**：清理 `__pycache__`/Godot 导入缓存/运行日志/`intake/tmp`/`_t84_*` 死脚本，补 T91 文档与 godot 目录索引。**T83 九元素环境三轴切片（2026-11-20）**：`t83_env_axes.py` + `t83_render.py` 同时打开质量/物态/温度三轴与三素力，6,998 个九元素分子投入 240×160 方格硬边界世界（1,000°C → 900 拍冷却到 73.4°C），骨架方块渲染 4 个 22×16 切片 + 13×9 原地放大；质量三档 y 均值 33.0/79.2/111.6 行、物态 气 46.0%/液 27.5%/固 26.5%（含固反应占 58.3%）、恒素场 ρ 0.549±0.043；1,034 团 / 最大团 1,322（21.7%）、顶部 10 行 1,346 分子「浮膜」（22.0%）；成功反应 5,199 次（13.7%）、终态 2,032 种分子式、734 种目录外新物质、9 元素严格守恒；报告 `docs/T83_ENV_AXES.md`、图 `images/t83_slices.png`。`t82_env_sim.py` + `t82_render.py` 在 150×110 方格环面（16,500 格、每格 ≤1 分子）投入 1,599 个 T62 batchA 缩放的九元素小分子，跑三素力场 + 规则 1~11 反应：1,599→1,425 分子、1,005 次反应、701 种分子式、188 种目录外新物质、9 元素严格守恒；四块切片成分一致（首位都是 `L2A2`）差异只在团大小/密度；16×12 原地放大图按目录六边形坐标画原子方块（S 实线 / C 虚线 / L 点线）；报告 `docs/T82_ENV_SLICES.md`、图 `images/t82_slices.png`（+5 单图）。**远端世界物理（`bdaaff1` 及之前 13 提交）**：`alchemy/core/reactor.py` 重写（599 行）、新增 `alchemy/efield.py`/`natural.py`/`reaction.py`、`docs/WORLD_PHYSICS.md`，力模型改为引力/斥力独立衰减 + 半径解耦、四象限 39/23/12/26，网格惯性滑行 + 等重纵向交换（垂直运动 41~59%），恒素守恒重分布只作反应门槛——详见 `docs/WORLD_PHYSICS.md`。**T81 三素相互作用公式（2026-11-20）**：`alchemy/three_su.py` + 脚本 `t81_su_calibrate.py`/`t81_su_world.py`/`t81_growth_search.py`/`t81_probe.py`/`t81_sweep.py`/`t81b_variants.py`/`t81c_overlap.py`/`t81_overnight.py`/`t81_su_plot.py`；点值：**聚素=吸引力**（O3/X2/C1 点）、**散素=覆盖半径**（K3/A2/F1 点）、**动素=排斥力**（P3/W2/L1 点）；84,225 全目录校准 **同种净吸 80,396 = 95.5% / 强粘 69,046 = 82.0% / 无作用·自斥 3,829 = 4.5%**；方阵环面 8 邻域动态验证（E1 强吸引成团 max_comp 4~5，无聚素/自斥物种 0 键）；夜间 κ 网格 25×3 混合×3 seed 定性不变（选择性 (2.0,0.3)=0.829、(2.5,0.5)=0.772）；**结论：同种强吸引 + 异种双弱成立；力是动力学加速器而非终态决定者；体生长需不对称机制（T80 模型）**；报告 `docs/THREE_SU_AXES.md`、图 `images/t81_su.png`。**T80 组装体生长（2026-11-19）**：主体 A 的组装体吞小分子 → 合成新 A → 并入自身，能长，但体是动态组装体、靠外部食物、无边界/遗传/复制/稳态、抓取与并入是脚本化主动步骤 ⇒ **不算生命**（`t80_assembly_body.py`、`t80_plot.py`，12 份 `t80_assembly_<arm>_s<seed>.json`，arm = full/farspawn/nochem/bare × seed = 20261119/20/21；报告 `docs/T80_ASSEMBLY_LIFE.md`、图 `images/t80_assembly.png`）。**T79 自催化生命搜索（2026-11-19）**：在 84,225 目录内搜索"单分子自催化生长" ⇒ 无此类生命，只找到端帽聚合物生长体（`t79_life_scan.py`，报告 `docs/T79_LIFE_SEARCH.md`）。**T78 九元素三轴环境实验（2026-11-19）**：自包含脚本 `t78_three_axis_env.py`（不改 `alchemy/` 内核），4×2 km² 竖直介质箱（中·气·温），投料 1,793 分子/18,222 原子（120 分子式、9 元素各约 2020、三/二/一价等量），240 min 三臂对照：**质量→重力**（轻/中/重 y 均值 3936.5 / 2330.6 / 91.4）、**温度→恒素富集**（终态局部 ρ-温度 r=0.957）、**物态→碰撞**；main 13,329 次反应、70.6% 集中在顶部富集带、810 个目录外新物质（全部不在 84,225 目录内）、607 种终态、守恒与漏斗闭合；三臂（main/nogate/nochem）对照说明门控把化学压进富集区、化学消耗热分子使 ρ 从 0.649(nochem) 降到 0.280(main)；**不收敛**（对照 T62 的 `LF`+`OXCPWKA` 双组分不动点，无退火/无整理/cap=20）。报告 `docs/T78_THREE_AXIS_ENV.md`、分析 `docs/T78_ANALYSIS.md`、图 `images/t78_overview.png` 与 `t78_products*.png`。**物质三轴定稿（`c438fef`）**：质量/物态/温度按层平均 → 27 格行为表 + 浮力，权威 `docs/MATERIAL_AXES.md`（旧「密度/粘性/温度」作废，`docs/TRAITS.md` 仅历史）。**上一轮第三轮（2026-11-19）**：`docs/ABILITY_EMERGENCE.md` 总纲 + `alchemy/ops.py`（9 操作能力）+ `alchemy/emergence.py`（L1~L4 涌现原型，无 alive 标志）+ 27 新测试（远端 `c438fef` 重写 `test_attrs.py` 后共 **150 项**）+ demo/参数文件 + 参数标定（800×800 组装率 68.5%、器官系统 1~4、活性无机档出现；B/H 判据仍 0）；结果见 `HANDOFF.md` §14.4 与 `intake/calibration.md` |
| 本地 commit 历史 | T01 → … → T67 → T68~T70b 图形阶段 → T71~T76（`8877e8d`）→ kernel 内核入库（`4a2e4d6`）→ 整理（`7dd324c`）→ 第二轮（`3d45357`/`becbd06`）→ 第二轮分析（`2916777`）→ 第三轮 v5+涌现（`b15ae4a`）→ 第三轮根文档同步（`e9b178c`）→ T77b（`02b9553`）→ 2026-11-19 整理（`6b3af38`）→ 三轴定稿 `c438fef` → 温度维度 v1/v2/定稿（`6c5ee49`/`894867b`/`68b897b`）→ 能力候选 110 项（`a9c8b44`）→ 基础能力原子 36 个（`48e7f46`）→ T78（`159a10d`）→ T79（`371b9ae`）→ T80（`69394d4`）→ T81（`1ac9603`）→ 2026-11-20 整理（`5ccd966`）→ T82（`0e14bd5`）→ T83（`676ddd2`）→ 拉取远端世界物理 13 提交（`bdaaff1`）→ T84（`8acde64`）→ T85（`4ffe8f4`）→ T86（`21e5e0e`）→ T87（`7b46c98`）→ T88（`cca77d6`）→ T89（`56c6ce9`）→ T90（`1b2860c`）→ progress 双机协作区（`5be747a`/`2336866`）→ T91（`ea4a982`）→ ChemLab（`a7af5e1`）→ T92（`727e229`）→ 2026-11-22 整理（`c5e5779`）→ 成果与 godot 整理（`cbdfd34`）→ T93（`6b88a1b`）→ T93 文档同步（`c907658`）→ T94（`55675df`）→ T94 文档同步（`b291641`）→ 2026-11-24 例行（`f8cce83`）→ progress 核对（`3545a87`）→ T95 碰撞/推挤（`396b867`） |

> 2026-11-18 工作区整理：已删除未跟踪的根目录日志/调试图/`__pycache__` 与工作区根的 2026-11-14 旧 ZIP/bundle 快照；
> `archive/` 已按阶段分子文件夹；传输工具在 `tools/`；详见 `docs/CLEANUP_LOG.md` 末节。

> 2026-11-19 工作区整理：删除工作区根 `intake/` 暂存区（312.2MB，与仓库 `alchemy/intake/` 内容重复）与仓库 5 处 `__pycache__/`；
> 保留 `alchemy/intake/tmp/calib/`（标定中间产物，gitignore 排除）；详见 `docs/CLEANUP_LOG.md` 末节。

> 2026-11-20 工作区整理：删除仓库未跟踪生成物 21 个根 `*.log`（35.9KB）、3 处 `__pycache__/`（26 pyc / 718KB）、16 个 0 字节 `t80_*.err`、
> 5 份被 12 份 seed 版取代的 T80 首轮结果（`t80_assembly_{full,farspawn,nochem,bare}.json` + `t80_quick_full.json`）；
> `git status` 干净后 tracked 1355 文件（最大 tracked 文件 `_data_gz/t12b_pairs.jsonl.gz` 39.41MB，全部 <40MB）；
> 同时把本地 12 个提交（T78~T82 + 整理提交）rebase 到远端世界物理 13 提交（`bdaaff1`）之上，连同并发代理提交的 T83 结果与 2 个整理同步提交全量推送（`bdaaff1..6aacdd9` 共 15 个提交）；详见 `docs/CLEANUP_LOG.md` 末节。

> 2026-11-22 工作区整理：删除 `__pycache__/`（3 处 799KB）、`godot/chem_lab/.godot/` 导入缓存（25 文件 2.66MB）、根 7 个运行日志与 4 个 Godot 日志、
> `alchemy/intake/tmp/`（16 文件 110KB）、tracked 死脚本 `_t84_probe.py`/`_t84_handoff_patch.py`，并清掉工作区根 `.acl-repair/`；
> 随后把此前只有脚本+JSON 的 T91 结果补成 `docs/T91_TRIPLE_SEARCH.md`、整理 `godot/` 目录（`godot/README.md` + 项目级 `.gitignore`）；
> 详见 `docs/CLEANUP_LOG.md` 2026-11-22 节与 `HANDOFF.md` 同名维护记录。

> 如果是新电脑 clone：`git clone https://github.com/fpg9999/alchemy` → `python unpack_data.py` → 读 `HANDOFF.md`。

---

## 1. 最新成果摘要（T55 → T67，全部 2D 粒子环境实验）

| 实验 | 投料 / 环境 | 核心结论 |
|---|---|---|
| T55 | 3 元素单质，9000 分子 / 18,000 原子，L=10000 | 1000→0°C 退火到 **99.5% `OXC`**；温度标度不匹配问题暴露 |
| T56 | 六元素，价数比 3<2<1（1:1.75:3），9200 分子 | 终态同价跨类盐 **`CF`+`XA`+`OK` = 99.6%**；120 种目录外新物质 |
| T57 | 全部 29 种聚素 + 面积模型，9002 分子 | **面积不改变热力学终态**（OXC 80.9% + OX2C 19.0%）；面积是动力学旋钮 |
| T58 | 九元素随机 44 种 / 73,216 原子，L=400000，cap20 | **937 种分子式 / 1,927 新物质**；cap20 堆积是人工边界 |
| T59 | 九元素 120+120 种，三价最多（52.3:26.3:21.4），L=60000，cap40，两阶段 | A 27,431 分子/43 种 → B 38,609 分子/67 种；`CF`+`O2XP2WK2A(2)` 等；cap60 后收敛到 9/13 种 |
| T60 | T55~T59 总汇报 | 12 张图 + 67 种重要物质图鉴；跨系列机制总结 |
| T61 | T59 终态 66 种 ≥5 原子大分子 | **66/66 严格六边形棋盘格摆放**（`embed_mol2`+`validate_place`）；13 张图 |
| T62 | 九元素 120+120 种，三/二/一价等量 ≈33.4:33.3:33.3（9 元素各 ≈11.1%），L=60000，cap40，两阶段 | A 34,476 分子/43 种 → B 51,937 分子/230,046 原子/43 种；体系收敛到 `LF` + `OXCPWKA` 1:1 等摩尔双组分（A 88.5%、B 94.0% 分子）；二次投放只"提纯"不"洗牌"；cap40→60：A 43→41、B 43→38、max 40→19/20、capped 0.095%/0.063%→0 |
| T63 | 29 种纯聚素 9,002 分子 → 0°C 整理后依次加 F2/A2/K2 各 8,000 分子（16,000 原子），L=30000，cap40，四阶段 | 终态 4/7/5/14 种分子式；**每次投放把上一终态完全熔断换代（retained=0）**，家族依次 OXC 盐 → F 端帽 → A 桥 → K 骨架；K 阶段 O≡K 把 F 挤回 F2（81.5% F 再生）+ 24 个 39/40 原子巨型；终态价数 32.4:35.1:32.5 回弹 ~1:1:1（印证 T62 吸引子）；capped 仅 K 阶段 0.435%，独立验证 39 项 PASS |
| **T67（最新）** | **汇总 T64(12)+T65(10)+T66(10)=32 个生态群系**（三份 `*_analysis.json`），不新增模拟；按终态专一性自动分四类（`t67_catalog.py`） | **32 群系收敛为 4 类终态形态：A 单主型 10 个（≥90%）、B 主辅型 11 个（50%~90%）、C 双主型 7 个（40%~50%）、D 多主型 4 个（<40%）**；A 类含两亚型（一元盐 B01/B02/B03/E03/C03/E07/C07 + 十原子簇 B08/C06/E06）；**10/10 对同元素集 E/C 群系同类别 → 类别由元素角色配比（三价骨架 O/P/K、二价桥 X/W/A、一价端帽 C/L/F）+ 温度日程决定，初始形态无关**；特色 Top10：B11/C10 九元双主、B08/C06/E06 十原子簇（9.7~9.8 原子）、C05 capped 7,313 最高、B09/B10 三对双原子各 1/3、E10 恒温活性 1.318 事件/分、C01/E01 双主+40 原子巨型 |
| **T66（保留）** | **10 群系 E01~E10 与 T65 C01~C10 一一对应（同元素集/同每元素原子数/同 L=18,000~20,000/同温度日程/cap40），唯一变量为初始化学形态：约 37.5%~60%（平均 47.3%）原子以目录内化合物/骨架投入（OP/OK/PK/XW/XA/CL/XPLA/KAF/XKF/OXCPKA/OXCPWK/OXCPWKA/OXC 等），其余双原子单质** | **初始化学形态记忆≈0（组成）、路径记忆显著（动力学）**：终态组成余弦 10/10 对 ≥0.9999（E01~E09 全 1.0000、E10 0.9999），top1 8/10 相同（另 2 对为计数几乎相等的产物互换）；但 capped 平均少 980 次（E01 2,250 vs C01 4,247、E05 1,009 vs 7,313、E10 1 vs 1,637）、净事件少 19.8%、瞬态新物质少 50 种；例外 E09 因种子 OXCPWKA（7 原子骨架）early 越 40 原子界，capped 反增（746 vs 1）；特色：E10 恒温活性 1.318 事件/分、E06 聚合度 9.77、E09 max 39；合计 45,152 分子/152,600 原子；独立验证 89 项 PASS |
| T65（保留） | 10 群系，每群系 ≥4 种元素（4/4/4/4/5/5/6/7/8/9；双原子单质、每元素 2,000~3,500 原子），L=18,000~20,000，cap40；温度日程同 T64（1000→25°C 退火 975 分钟 + 25°C 恒温浮动 600 分钟） | **产物整体更杂更大更多新物质**（对 T64：终态种数 12→16.8、聚合度 3.27→4.22、新物质 106→224、capped 490→1,381、混合家族 63.1%→92.8%）；但纯杂由价数互补与端帽决定：C03 仅 4 元素就 98.4% 单一 `XPLA`、C06 93.6% 原子锁进十原子簇 `O2X2P2K2A2`（9.70 原子/分子）、C07 93.9% `OXCPKA`；缺端帽的 C01/C05 出现 19~22 原子巨型簇（capped 4,247/7,313）；缺 F 的 C09"杂而不大"（26 种/488 新物质/max 17）；C10 与 T64 B11 同条件同种子（20261137）逐项一致（余弦 1.0000）；合计 44,979 分子/152,600 原子；独立验证 88 项 PASS |
| T64（保留） | 12 群系 × 3~9 种元素（双原子单质、每元素 2,000~4,000 原子），L=17,000~20,000，cap40；1000→25°C 退火 975 分钟 + 25°C 恒温浮动 600 分钟（日 ±8°C + 季节 ±3°C） | 12 群系全部形成稳定群落：B01/B02/B03 纯族→单一三元分子 OXC/PWL/KAF（99%+）；B04~B07/B12 配对双产物；**B08 形成 `O2X2P2W2K2` 十原子封闭簇（94.4%、9.73 原子/分子）**；B09/B10 三对双原子各 1/3（镜像）；**B11 复现 T62 的 `LF`+`OXCPWKA` 双组分（24 种/417 新物质）**；合计 59,714 分子/165,000 原子；**价数结构决定终态、元素身份只改符号**；独立验证 102 项 PASS |

最新核心资产（T67 新增）：

- 代码：`t67_catalog.py`（汇总三份 analysis、按专一性自动分四类、输出 JSON 与两张图）；
- 数据：`t67_catalog.json`（32 群系总表：round/id/name/元素/top1/专一性/聚合度/capped/种数/新物质…）；
- 报告：`docs/T67_BIOME_CATALOG.md`；
- 图：`images/t67_catalog_map.png`（生态位全景）、`images/t67_catalog_bars.png`（32 群系条带目录）。

**T67 一句话**：把 T64/T65/T66 三轮共 32 个生态群系放进同一张"生态位"图后，它们自然收敛为
**A 单主 10 / B 主辅 11 / C 双主 7 / D 多主 4** 四类形态——类别由元素角色配比（三价骨架/二价桥/一价端帽）
与温度日程决定，与初始投料形态无关；这为"给定元素集合预判群落形态"提供了经验规则。

最新核心资产（T66，保留）：

- 代码：`t66_biomes.py`（10 群系化合物播种主脚本，`--list/--biome/--all/--control`；含化合物+单质逐元素配平自检）、
  `t66_analysis.py`、`t66_render.py`、`t66_verify.py`（复用引擎 `t55_kinetic_env.py` 的 `temp_schedule`）；
- 数据：`t66_biomes.json`、`t66_biome_E01..E10_result.json`、`t66_biome_E01..E10_state.json`、
  `t66_control_E01.json`、`t66_biome_index.json`、`t66_analysis.json`、`t66_verify.json`；
- 报告：`docs/T66_BIOMES.md`、`docs/T66_VERIFY.md`；
- 图：`images/t66_*.png`（14 张：13 主图 + T66 vs T65 组成余弦/capped 对照图）。

**T66 一句话**：把初始底物从"全单质"换成"37.5%~60% 化合物/骨架 + 其余单质"，与 T65 逐群系配对后，
**终态组成几乎完全不变（余弦 10/10 对 ≥0.9999、top1 8/10 相同）**，但 capped 平均少 980 次、
净事件少 19.8%——初始化学形态被退火抹平（组成记忆≈0），而到达终态的路径被保留（路径记忆）；
种子本身是大骨架时（E09 的 OXCPWKA）capped 反而增加，说明"路径记忆"取决于种子尺寸。

最新核心资产（T65，保留）：

- 代码：`t65_biomes.py`（10 群系主脚本，`--list/--biome/--all/--control`）、`t65_analysis.py`、
  `t65_render.py`、`t65_verify.py`（复用引擎 `t55_kinetic_env.py` 的 `temp_schedule`）；
- 数据：`t65_biomes.json`、`t65_biome_C01..C10_result.json`、`t65_biome_C01..C10_state.json`、
  `t65_control_C01.json`、`t65_biome_index.json`、`t65_analysis.json`、`t65_verify.json`；
- 报告：`docs/T65_BIOMES.md`、`docs/T65_VERIFY.md`；
- 图：`images/t65_*.png`（14 张：13 主图 + T64 对比图）。

**T65 一句话**：把元素数下限抬到 4 再做 10 个生态群系——产物整体变得更杂更大更多新物质，但"纯不纯"由**价数互补与端帽**决定而非元素数：价数链一次闭合就极纯（C03 98.4% XPLA、
C06 93.6% 十原子簇、C07 93.9% OXCPKA），端帽缺失 + 骨架过量会长巨型簇（C01/C05），
端帽缺失 + 骨架不足则"杂而不大"（C09 26 种/488 新物质）。F 的角色被精确定位为"把 L 从 L2
拉出来"的端帽；C10 与 T64 B11 同条件同种子逐项复现（组成余弦 1.0000）。

最新核心资产（T64，保留）：

- 代码：`t64_biomes.py`（12 群系主脚本，`--list/--biome/--all/--control`）、`t64_analysis.py`、
  `t64_render.py`、`t64_verify.py`、`t64_hex_layouts.py`、`t64_hex_render.py`；
  引擎 `t55_kinetic_env.py` 新增 `temp_schedule` 参数（向后兼容）；
- 数据：`t64_biomes.json`、`t64_biome_B01..B12_result.json`、`t64_biome_B01..B12_state.json`、
  `t64_control_B01.json`、`t64_biome_index.json`、`t64_analysis.json`、`t64_verify.json`、
  `t64_hex_layouts.json`；
- 报告：`docs/T64_BIOMES.md`、`docs/T64_VERIFY.md`；
- 图：`images/t64_*.png`（13 张主图）+ `images/t64_hex_*.png`（20 张严格六边形摆放图）。

**T64 一句话**：把元素反应从"大锅混合"推进到"生态群系"——每个群系只放 3~9 种元素的双原子单质，
1000→25°C 退火后再让温度在 25°C 附近做日/季节浮动；12 个群系全部形成稳定群落，且终态由**价数结构**
而非元素身份决定（三族纯系同构、B09/B10 镜像、B05/B06 同构）；B08 长出十原子封闭簇
`O2X2P2W2K2`（94.4%），B11 复现 T62 的 `LF+OXCPWKA` 双组分——初始条件完全不同却同一终态，
说明这对双组分是 9 元素等原子比下的热力学/动力学吸引子。

T63 核心资产（保留）：

- 代码：`t63_staged.py`（四阶段单质滴定主脚本，`--phase 1..4/all`、`--control`）、
  `t63_analysis.py`、`t63_render.py`、`t63_verify.py`、`t63_hex_layouts.py`、`t63_hex_render.py`；
- 数据：`t63_loads.json`、`t63_phase1..4_result.json`、`t63_state1..4.json`、`t63_control_s1.json`、
  `t63_analysis.json`、`t63_verify.json`、`t63_hex_layouts.json`；
- 报告：`docs/T63_STAGED_TITRATION.md`、`docs/T63_VERIFY.md`；
- 图：`images/t63_*.png`（12 张主图）+ `images/t63_hex_*.png`（5 张严格六边形摆放图）。

**T63 一句话**：先只投 29 种纯聚素退火，再逐级投放"大量单质"（1 价 F2 → 2 价 A2 → 3 价 K2），
每一次投放都把上一阶段终态**完全熔断、整体换代**（top20 保留数 0），产物家族严格按元素角色接力
（聚素盐 OXC 80.8% → F 端帽 → A 桥 → K 骨架）；K 阶段 O≡K 三键把 F 挤回单质（F2 6,521，81.5% F），
并首次触发 capped（0.435%）与 24 个 39/40 原子巨型；终态价数 32.4:35.1:32.5 回弹到 ~1:1:1，
与 T62 的"等量价数吸引子"互相印证——**投放顺序本身就是配方变量**。

T62 核心资产（保留）：

- 代码：`t62_mixture.py`（IPF 等量投料）、`t62_two_phase.py`（两阶段主脚本，支持 cap/control）、
  `t62_analysis.py`、`t62_render.py`、`t62_verify.py`、`t62_hex_layouts.py`、`t62_hex_render.py`；
- 数据：`t62_loads.json`、`t62_phaseA_result.json`、`t62_stateA.json`、`t62_phaseB_result.json`、
  `t62_stateB.json`、`t62_control_A.json`、`t62_phaseA_hf_result.json`、`t62_phaseB_hf_result.json`、
  `t62_analysis.json`、`t62_verify.json`、`t62_hex_layouts.json`；
- 报告：`docs/T62_EQUAL_VALENCE.md`、`docs/T62_VERIFY.md`；
- 图：`images/t62_*.png`（13 张主图）+ `images/t62_hex_*.png`（5 张严格六边形摆放图）。

**T62 一句话**：把 T59 的"三价最多/一价最少"改成"三/二/一价数量相当"后，体系不再收敛为
"大骨架 + 双原子盐"混合物，而是几乎完全收敛到 **`OXCPWKA`（7 原子等摩尔杂环）+ `LF`（双原子盐）
≈1:1** 的双组分；等量价数让终态更纯净、更不依赖 cap 与初始条件，二次投放只进一步提高纯度
（91.4%→95.5% 原子），为"价数配比 = 终态配方"提供了最强单变量对照。

---

## 2. 方案 A：GitHub（推荐，日常同步最方便）

### 前提
- git 2.56.0、gh 2.103.2（`gh` 未登录也可，git 凭据由 Git Credential Manager 提供）；
- 本机已存 GitHub 凭据（用户 `fpg9999`）；若凭据过期，运行 `gh auth login` 或
  `git credential-manager github login` 重新登录即可。

### A1. 推送（本文件夹到已有远程仓库）

```powershell
cd "G:\AI work\deepseek\work1\alchemy"

git remote add origin https://github.com/fpg9999/alchemy.git   # 已配置过则跳过
git add -A
git commit -m "T67: 生态群系总目录（32 群系分四类 A10/B11/C7/D4，生态位全景图+条带目录，类别由元素角色配比决定）"
git push -u origin main
```

> 本仓库当前只有一个远程 `origin`，分支 `main`。

### A2. 在新电脑上 clone

```powershell
git clone https://github.com/fpg9999/alchemy.git
cd alchemy
python unpack_data.py          # 解压 _data_gz/ 里的大文件（若原始 JSON 未随仓库提供）
python -c "import pot_v4; print(pot_v4.simulate(['O','K']))"
```

### A3. 仓库里有什么

- 全部 `.py` 脚本（核心模拟器 `pot_*.py`、自然引擎 `natural_engine.py`、快速引擎 `fast_pot.py`、
  T4~T62 各阶段实验/分析脚本）、`docs/`（全部 `T*.md` 报告）、`images/`（全部结果图）、`archive/`；
- `_data_gz/`：6 个超大文件的 gzip（最大 41MB，低于 GitHub 100MB 单文件限制），见 §4；
- **T58/T59/T62 的大结果 JSON 直接入库**（单个 20~28MB，均 <100MB）；其余被 `.gitignore` 排除的
  大文件原件需 `unpack_data.py` 恢复；
- 仓库总大小约 **190MB**（含历次实验数据），不需要 Git LFS。

### A4. 如果一定要把全部原始大文件也放进 GitHub
- 需要 Git LFS（免费配额有限，不推荐）：
  ```powershell
  git lfs install
  git lfs track "t4_catalog_all_validated.json" "t12b_pairs.jsonl" ...
  ```
- 日常同步用 `_data_gz/` + 已入库的大结果 JSON 已足够。

---

## 3. 方案 B/C/D（历史迁移方式；注意快照时间）

> ⚠️ 2026-11-14 生成的 B/C 快照文件**已在 2026-11-18 整理时删除**（内容早已被 GitHub 上的后续提交覆盖）。
> 需要新的离线包时，在仓库根目录运行 `python tools\make_transfer_archive.py`（输出到工作区根，
> 文件名自动带当天日期）；方案 A 的 GitHub clone 与方案 D 的目录复制始终最新。
> 方案 D（直接复制目录）始终是最新最稳的。

### B. 全量 ZIP（按需重新生成）
```
python tools\make_transfer_archive.py
# → G:\AI work\deepseek\work1\alchemy_transfer_<YYYY-MM-DD>.zip（+ 脚本打印的 sha256）
```
- 包含全部原始文件（不含 `.git`、`__pycache__`、`_compression_test`）；
- 解压即得完整 `alchemy/` 目录，无需 `unpack_data.py`。

### C. git bundle（按需重新生成，离线 git 历史）
```
cd "G:\AI work\deepseek\work1\alchemy"
git bundle create ..\alchemy_repo_%DATE%.bundle --all
```
- 在新电脑：`git clone alchemy_repo_<DATE>.bundle alchemy` → `python unpack_data.py`；
- 2026-11-14 的旧 bundle（head `4a4dca4`）已删除，最新历史以 GitHub 为准。

### D. 直接复制整个目录
同系统/同盘直接复制 `alchemy/`（含 `_data_gz`、`archive`、`docs`、`images`）；
脚本纯 Python + Pillow，无路径依赖；复制后读 `HANDOFF.md`。

---

## 4. 数据文件说明

### 4.1 `_data_gz/` 中被压缩的 6 个超大文件（manifest 校验）

| 原文件 | 大小 | gzip |
|---|---:|---:|
| `t12b_pairs.jsonl` | 149MB | 41MB |
| `t4_catalog_all_validated.json` | 114MB | 4.7MB |
| `t12b_vec_v3.json` | 31MB | 3.9MB |
| `t12b_results.json` | 31MB | 3.9MB |
| `t12c_sample_pairs.json` | 8.6MB | 0.8MB |
| `t4_catalog_index.json` | 8.3MB | 0.8MB |

- `_data_gz/manifest.json` 含每个文件原始/压缩后的 SHA256；
- `python unpack_data.py` 自动校验并解压（`--force` 可覆盖）。

### 4.2 直接入库的大结果文件（均 <100MB）

`t58_result.json`、`t59_phaseA_result.json`、`t59_phaseB_result.json`、`t59_phaseA_hf_result.json`、
`t59_phaseB_hf_result.json`、`t62_phaseA_result.json`、`t62_phaseB_result.json`、
`t62_phaseA_hf_result.json`、`t62_phaseB_hf_result.json`、`t63_phase1_result.json` ~
`t63_phase4_result.json`、`t64_biome_B01_result.json` ~ `t64_biome_B12_result.json`、
`t65_biome_C01_result.json` ~ `t65_biome_C10_result.json`、`t66_biome_E01_result.json` ~
`t66_biome_E10_result.json` 等，单个 20~28MB。
其余 >16MB 的中间数据（`t12b_*` 等）仍走 `_data_gz/`。
T67 无大结果文件（`t67_catalog.json` 约 40KB，直接入库）。

---

## 5. 新电脑最小检查清单

1. Python 3.10+ 可运行；
2. `pip install -r requirements.txt`（Pillow）；
3. 数据文件存在（或 `python unpack_data.py`）；
4. 冒烟测试（内核，推荐）：
   ```powershell
   $env:PYTHONIOENCODING="utf-8"
   python examples/demo_kernel.py      # 四入口演示（GBK 控制台需上一行，否则 ✓/→ 报 UnicodeEncodeError）
   python tests/run_all.py             # 150 项测试全绿（约 16~27s）
   ```
   涌现原型冒烟（可选）：`python examples/emergence_demo.py --sample 600 --steps 600`（约 13s，输出 JSON；组装率约 57%、器官 22、器官系统 3）。
   兼容旧根脚本：`python -c "import pot_v4; print(pot_v4.simulate(['O','K']))"`。
5. 读 `HANDOFF.md` 第 0 节的新对话启动语、§13（内核包与新规则体系）；
6. 需要最新实验时：`python t67_catalog.py`（汇总 32 群系总目录，不跑模拟）；要跑模拟：化合物播种
   `python t66_biomes.py --all`（或复用 `t66_analysis.py` / `t66_render.py` / `t66_verify.py`）；
   上一轮 T65 用 `python t65_biomes.py --all`；T64 用 `python t64_biomes.py --all`
   （+ `t64_hex_*`）；T63 用 `python t63_staged.py --phase all`。图形阶段（不跑模拟）：
   `python t68_atlas.py`（36 分子图册）→ `python t69_render.py`（T69 连接件版）→
   `python t70_render.py`（生成式形状语言四图）→ `python t70b_body.py`（整体形体图）。
   最新阶段（自包含脚本，按需跑）：三轴环境 `python t78_three_axis_env.py`（约 30s）→ 分析/出图 `t78_analysis.py` / `t78_products.py` / `t78_render.py`；
   自催化生命搜索 `python t79_life_scan.py`；组装体生长 `python t80_assembly_body.py`（12 组 arm×seed，约 36KB/份）→ `t80_plot.py`；
   三素相互作用 `python t81_su_world.py`（方阵环面动态）与 `python t81_su_calibrate.py`（84,225 全目录校准）→ `t81_su_plot.py`；
   夜间扩展网格 `python t81_overnight.py`（25 组 κ × 3 混合 × 3 seed），变体验证 `t81b_variants.py` / `t81c_overlap.py`，生长搜索 `t81_growth_search.py`。
   内核阶段（不跑模拟）：`python examples/build_biome_candidates.py`（复算候选群系，约 26s）；
   `python examples/render_species_sheets.py`（46 种物种图，需 Pillow）。

---

## 6. 推送记录

### 6.1 2026-11-20（拉取远端世界物理 13 提交 + T78~T83 全量推送 + 整理轮，最新）

| 项目 | 内容 |
|---|---|
| 拉取（fetch） | 本轮开始时 `origin/main`=`c438fef`；推送时发现远端已前进到 **`bdaaff1`**（13 个提交：`544c84f` 世界物理定稿 → `84562d5` 接入恒素场与自然反应 → `4b26ebb`/`8111172`/`caec201` 恒素场标定与守恒重分布 → `beb441d` 反应层网格一致性 → `61221e0`/`3494e3f`/`f9bcb79`/`782cf46` 惯性滑行与主导力源过滤 → `b953cbf`/`671b0ab`/`bdaaff1` 力模型重构与四象限校准；新增 `alchemy/efield.py`、`alchemy/natural.py`、`alchemy/reaction.py`，重写 `alchemy/core/reactor.py`（599 行），新增 `docs/WORLD_PHYSICS.md`、30+ 个 `examples/`、约 200 张图与 3 份 `reports/`，198 文件 +5219/−295）——已 fetch 并在其之上 rebase 本地 12 个提交，**无冲突** |
| 推送前本地 | rebase 后 `HEAD` = T82，`main...origin/main` = **ahead 12 / behind 0**；工作树干净；复跑 `python tests/run_all.py` → **150/150 PASS (18.3s)**（上游重写 `reactor.py` 后测试数不变） |
| 推送结果 | 首轮 `bdaaff1..6aacdd9` 共 **15 个提交**（12 个本地成果/整理提交 + 并发代理的 T83 结果提交 + 2 个整理同步提交）；其后仅文档口径同步提交；远程 HEAD = 本文件同步提交（`git rev-parse HEAD`）；tag `kernel-0.2.0` 仍未推 |
| 本地提交（rebase 后新哈希） | `6c5ee49` 温度维度 v1 + 工作规则 → `894867b` 温度维度 v2 + HANDOFF §15 → `68b897b` 温度维度定稿（方案 A）→ `a9c8b44` 能力候选总目录（11 域 110 项）→ `48e7f46` 基础能力原子（6 类 36 个）→ `159a10d` T78 三轴环境实验 → `dc31dbe` T78 终产物分层图 → `371b9ae` T79 自催化生命搜索 → `69394d4` T80 组装体生长 → `1ac9603` T81 三素相互作用 → `5ccd966` 2026-11-20 整理（生成物清理 + 文档同步）→ `0e14bd5` T82 九元素环境切片（150×110 方格环面、1,599→1,425 分子、1,005 次反应、701 种分子式、188 种目录外新物质、9 元素严格守恒） |
| 本轮整理 | 删除 21 个根 `*.log`（35.9KB）、3 处 `__pycache__/`（26 pyc / 718KB）、16 个 0 字节 `t80_*.err`、5 份被 12 份 seed 版取代的 T80 首轮结果；`docs/CLEANUP_LOG.md` 加 2026-11-20 节；`INDEX.md` 整理记录 bullet；本文件 §0/§5/§6 同步；`README.md` 顶部加 T81/T80/T79 横幅并去掉"未 push"表述 |
| 测试 | `python tests/run_all.py` → **150/150 PASS**（18.3s；11 个 `test_*.py`；`c438fef` 重写 `test_attrs.py` 后由 151 变 150，README/HANDOFF 同步） |
| 已知问题 | `alchemy/emergence.py` 仍按旧 attrs 字段（density/stickiness）取值，与新 attrs（mass/state/temperature）不兼容 → Φ≈1 退化、旧标定失效，需另开任务修（详见 6.2 末行） |
| 远程核验（推送后） | `git ls-remote origin refs/heads/main` = 本文件同步提交；`git rev-list --left-right --count main...origin/main` = `0 0`；远程 tracked 1,574 文件 / 工作树 1,024.3MB，最大 tracked 文件 `_data_gz/t12b_pairs.jsonl.gz` 41,327,963B（39.4MiB） |

### 6.2 2026-11-19（物质三轴定稿同步 `c438fef` + 本地设计提交 rebase + T78 实验，未推送）

| 项目 | 内容 |
|---|---|
| 远程 HEAD | **`c438fef`** `rules: 三轴定为 质量/物态/温度（碰撞/重力/恒素富集），27 格行为表`（4 files：`alchemy/attrs.py` 重写 274 行、`docs/MATERIAL_AXES.md` 新增 155 行、`docs/TRAITS.md` 顶部加「已被取代」历史横幅、`tests/test_attrs.py`） |
| 本地同步 | 远端 `c438fef` 已同步；本地 5 个纯文档设计提交 rebase 到其之上，无冲突；随后完成 T78 三轴环境实验并提交；`main...origin/main` = **ahead 6**，HEAD 见 `git log`（T78 提交），工作树干净（`t78_smoke2.json` 中间产物已删） |
| 本地提交（未推，哈希已被 2026-11-20 rebase 重写） | `2c8798c` 温度维度 v1 设计稿 + HANDOFF 工作规则 → `85e8711` 温度维度 v2 + HANDOFF §15 → `ed4b8d1` 温度维度定稿（方案 A）→ `1c155ce` 能力候选总目录（11 域 110 项）→ `4aea764` 基础能力原子（6 类 36 个）→ **T78 提交**（三轴环境实验脚本/结果/独立分析/独立验证/图/报告 + 根文档与 docs/ 旧口径回填）；前 5 个均为纯文档，未改内核；T78 自包含不改内核 |
| 三轴口径 | 见 §0「最新成果」与 `docs/MATERIAL_AXES.md`：质量/物态/温度按层平均 → 27 格行为表（轻/中/重 × 气/液/固 × 冷/温/热 → 重力/碰撞/恒素富集）；浮力 `F=(介质质量−物体质量)×体积`；缺失层=0 必落最低档；旧「密度/粘性/温度」作废（`docs/TRAITS.md` 仅历史） |
| 根文档回填 | `README.md`（顶部同步横幅 + 物性→物质三轴 + T78 横幅）、`HANDOFF.md`（头部 + §0/§11/§13.1/§13.5/§13.7/§15 + 维护记录 + T78 条目）、`INDEX.md`（补 5 个文档条目 + 口径统一 + T78）、本文件、`NEW_CHAT_PROMPT.md`；第二轮：`docs/ABILITY.md`、`docs/APPEARANCE.md`、`docs/ABILITY_EMERGENCE.md`、`docs/THREE_AXES_FINAL.md`、`docs/PHASE_RULE.md`、`docs/INTAKE_R2.md`、`intake/*`、`alchemy/README.md` 已加新口径或历史注（+182/−48） |
| T78 实验（已完成，同一提交） | `t78_three_axis_env.py` + `t78_analysis.py` + `t78_render.py`；三臂结果 `t78_main/nogate/nochem_result.json`（main 31s / nogate 39s / nochem 2s）；分析 `t78_analysis.json`（一致性 30 项全 PASS）；图 `images/t78_overview.png`；报告 `docs/T78_THREE_AXIS_ENV.md`。关键结果：1,793 分子/18,222 原子、9 元素各约 2020；质量分层 轻/中/重 y 均值 3936.5/2330.6/91.4；局部 ρ-温度 r=0.957；main 13,329 反应、70.6% 在顶带、810 目录外新物质、607 终态、守恒全闭合；nochem ρ=0.649 vs main 0.280（化学消耗热分子→恒素稀释） |
| 未做 | 未修改 `alchemy/` 内核；T78 为单 seed/单介质/240 min；`alchemy/emergence.py` 仍按旧 attrs 字段（density/stickiness）取值，与新 attrs 不兼容（已知风险，待另开任务修） |

### 6.3 2026-11-19（第三轮：能力维度 v5 + 涌现原型 + T77b 标定，已推送）

| 项目 | 内容 |
|---|---|
| 远程 HEAD | 推送前 `cf9d01b`；**2026-11-19 整理轮已推送**：`cf9d01b..main` 共 7 个提交（含 `02b9553` T77b 与本次整理记录） |
| 本地提交 | **`b15ae4a`** `T77: 能力维度 v5（9 操作核）与涌现原型 + 过时口径清扫`（新增 `alchemy/ops.py`、`alchemy/emergence.py`、`tests/test_ops.py`、`tests/test_emergence.py`、`examples/emergence_demo.py`、`alchemy/data/emergence_params.json`、`docs/ABILITY_EMERGENCE.md`；stale-sweeper 改 35 文件；根 README 同步）；**`e9b178c`** 第三轮根文档同步；**`02b9553`** `T77b: 涌现原型参数标定（8 bug 修复 + calibration 段）+ 根文档回填 151 测试与标定结果 + intake 设计/分析报告入库`（58 文件 +8977/−211）；其前 `2916777`（第二轮分析）、`becbd06`、`3d45357` |
| tag | `kernel-0.2.0`（annotated，本地，未推） |
| 测试 | `python tests/run_all.py` → **151/151 PASS**（15.9s）；`python examples/emergence_demo.py --sample 600 --steps 600` → rc=0，13.3s |
| 参数标定 | task-10 完成：推荐参数在 `alchemy/data/emergence_params.json` 的 `calibration` 段（`contacts_per_pair=3`、`k_on0=0.25`、`W0=0.25`、`rupture_p=0.35`、`Q_min=0.3`、`theta_scale=0.8`、`maint_rate=1.15` 等），报告 `intake/calibration.md`；修掉 8 个实现缺陷 |
| 标定后实测 | 800×800 两 seed：组装率 68.5%（预注册 55~70% ✓）、器官/组装体 1.38~1.58、器官系统 1/4、四档首次出现「活性无机」10/20；2000×800：72.2%、系统 10、器官 60；demo 600×600：57.1%、系统 3、器官 22 |
| 未达项 | B（边界维持）判据恒 0（1 格 footprint 下为稀疏树状团，`shell_subgraph` 命中 0）→ 拟生命/有机生命仍 0；H 依赖 B；R 偏高；贯通巨团两态未根除（详见 `HANDOFF.md` §14.4） |

### 6.4 2026-11-19（第二轮：属性/能力改造）

| 项目 | 内容 |
|---|---|
| 远程 HEAD | **`cf9d01b`** `docs: SYNC 记录 post-commit 自动推送钩子`（+11 行，仅 `docs/SYNC.md`）；父提交 **`facb162`** `rules: 三价轴改密度、能力改类别辐条、27 格物性、能力三阶`（7 files：`alchemy/ability.py` +188、`alchemy/attrs.py` +87/−70、`docs/ABILITY.md` +85/−4、`docs/REPO_SLIM.md` 新增 118、`docs/TRAITS.md` +88/−58、`tests/test_ability.py` +136、`tests/test_attrs.py` +50/−40） |
| 自动推送钩子 | 作者本机 `.git/hooks/post-commit`：每次 commit 后自动 `git push origin <当前分支>`；失败提示 `[post-commit] 自动推送失败`，删钩子即关闭（只在本机生效，不进版本库） |
| 本地同步 | 2026-11-19 00:30 本机 `git fetch` 重试第 8 次成功，`git rebase origin/main --empty=drop` 接入（本地整理提交重放为 `3d45357`/`becbd06`，领先 origin 2 个文档提交，未 push）；复跑 `python tests/run_all.py` → **124/124 PASS** |
| 说明 | 本轮期间本机直连 GitHub `git fetch` 多次 `Connection was reset`，先用 GitHub API/raw 逐文件取回（内容与上游逐字节一致）再 fetch 成功并入正式历史；以后遇到同类情况优先重试 fetch |

### 6.5 2026-11-18（内核入库）

| 项目 | 内容 |
|---|---|
| 远程 | `https://github.com/fpg9999/alchemy`，分支 `main` |
| 远程 HEAD | **kernel 提交 `4a2e4d6`**（`kernel: 抽出 alchemy 内核（四入口 + 106 项测试）`，88 files，纯新增） |
| 上一次 | `8877e8d` — `T71-T76: 能力体系与分化形态 / 器官几何 / 分类规则 / 方块世界 / 逐骨架属性 / 桥功用标签 + 报告与图` |
| 再上 | `4c79217` — `T68-T70b: 大分子图形阶段成果入库` |
| 本地核对 | 拉取后 `main...origin/main` 同步、工作树干净；`python tests/run_all.py` → 106/106 PASS |

### 6.6 历史推送记录（T67 及以前）

| 项目 | 内容 |
|---|---|
| 推送时间 | 2026-11-17（T67 完成后追加推送） |
| 远程 | `https://github.com/fpg9999/alchemy` |
| 分支 | `main`（已建立 `origin/main` 跟踪） |
| 远程 HEAD | **T67 提交 `2221f47` 已推送**（`9c3714d..2221f47 main -> main`） |
| 本次提交 | `2221f47` — `T67: 生态群系总目录（32 群系分四类 A10/B11/C7/D4，生态位全景图+条带目录，类别由元素角色配比决定）`（8 files：报告/脚本/JSON/2 图/HANDOFF/README/TRANSFER） |
| 之前历史 | `9c3714d`（T66 TRANSFER）→ `ee77b96`（T66 数据）→ `5df6286`（T66 主提交）→ `61d4863`（T65 文档）→ `e46dc6c`（T65 TRANSFER）→ `e2b8112`（T65 主提交）→ `e9c5f19`（T64 报告结构修正）→ `9322c02`（T64 TRANSFER）→ `fb1a77d`（T64 主提交）→ `8625a94`（T63 文档）→ `233cb1c`（T63 主提交）→ `9f88d9f`（T62 文档）→ `39aeb50` → `83429a0`（T62 主提交）→ `f01e88e`（T61）→ … → T01 全部已上传 |
| 说明 | 日常同步继续用 `git add -A && git commit && git push origin main`；本环境偶发 `Failed to connect to github.com:443` / `unexpected disconnect`（网络抖动，重试即成功；T66 数据提交 92MB 曾拆为两次提交分推） |
