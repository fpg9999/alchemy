# 跨电脑交接方案（ALCHEMY）· 最新成果版

> 最后更新：**2026-11-17**（T62 等量价数两阶段实验完成后整理）
> 工作目录：`G:\AI work\deepseek\work1\alchemy`
> 交接入口：`HANDOFF.md`（最新结论以它为准）；本文件负责"如何迁移/同步"。
> 远程仓库：**https://github.com/fpg9999/alchemy**

---

## 0. 当前状态（2026-11-17）

| 项目 | 状态 |
|---|---|
| 本地仓库 | `G:\AI work\deepseek\work1\alchemy`，分支 `main` |
| 远程仓库 | `https://github.com/fpg9999/alchemy`（已创建，空仓库） |
| 认证 | Git Credential Manager 已存 `fpg9999` 的 GitHub 凭据（`cmdkey` 中 `git:https://github.com`）；`gh` CLI 未登录，但不影响 git push |
| 推送 | **本次整理后将 `main` 推送到远程**（推送记录见 §6） |
| 最新实验 | **T62 等量价数两阶段实验**（九元素、三/二/一价≈1:1:1、0°C 后二次投放；报告 `docs/T62_EQUAL_VALENCE.md`） |
| 本地 commit 历史 | T01 → … → T59 → T60 总汇报 → T61 六边形摆放 → **T62 等量价数**（最新） |

> 如果是新电脑 clone：`git clone https://github.com/fpg9999/alchemy` → `python unpack_data.py` → 读 `HANDOFF.md`。

---

## 1. 最新成果摘要（T55 → T62，全部 2D 粒子环境实验）

| 实验 | 投料 / 环境 | 核心结论 |
|---|---|---|
| T55 | 3 元素单质，9000 分子 / 18,000 原子，L=10000 | 1000→0°C 退火到 **99.5% `OXC`**；温度标度不匹配问题暴露 |
| T56 | 六元素，价数比 3<2<1（1:1.75:3），9200 分子 | 终态同价跨类盐 **`CF`+`XA`+`OK` = 99.6%**；120 种目录外新物质 |
| T57 | 全部 29 种聚素 + 面积模型，9002 分子 | **面积不改变热力学终态**（OXC 80.9% + OX2C 19.0%）；面积是动力学旋钮 |
| T58 | 九元素随机 44 种 / 73,216 原子，L=400000，cap20 | **937 种分子式 / 1,927 新物质**；cap20 堆积是人工边界 |
| T59 | 九元素 120+120 种，三价最多（52.3:26.3:21.4），L=60000，cap40，两阶段 | A 27,431 分子/43 种 → B 38,609 分子/67 种；`CF`+`O2XP2WK2A(2)` 等；cap60 后收敛到 9/13 种 |
| T60 | T55~T59 总汇报 | 12 张图 + 67 种重要物质图鉴；跨系列机制总结 |
| T61 | T59 终态 66 种 ≥5 原子大分子 | **66/66 严格六边形棋盘格摆放**（`embed_mol2`+`validate_place`）；13 张图 |
| **T62（最新）** | **九元素 120+120 种，三/二/一价等量 ≈33.4:33.3:33.3（9 元素各 ≈11.1%），L=60000，cap40，两阶段** | **A 34,476 分子/43 种 → B 51,937 分子/230,046 原子/43 种；体系收敛到 `LF` + `OXCPWKA` 1:1 等摩尔双组分（A 88.5%、B 94.0% 分子）；二次投放只"提纯"不"洗牌"；cap40→60：A 43→41、B 43→38、max 40→19/20、capped 0.095%/0.063%→0** |

最新核心资产（T62 新增）：

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
git commit -m "T62: 九元素等量价数两阶段实验（LF+OXCPWKA 1:1 双组分、cap40/60 对照、独立验证）"
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

> ⚠️ 下面 B/C 是 **2026-11-14** 生成的快照，**不含 T55~T62 的后续实验**（T55/T56/T57/T58/T59/T60/T61/T62 都在其后完成）。
> 需要最新全量包时，可重新运行 `make_transfer_archive.py`（会重新打包 zip）或用方案 A 的 GitHub clone。
> 方案 D（直接复制目录）始终是最新最稳的。

### B. 全量 ZIP（2026-11-14 快照）
```
G:\AI work\deepseek\work1\alchemy_transfer_2026-11-14.zip
G:\AI work\deepseek\work1\alchemy_transfer_2026-11-14.sha256.txt
```
- 包含当时全部原始文件（不含 `.git`、`__pycache__`）；
- 解压即得完整 `alchemy/` 目录，无需 `unpack_data.py`。

### C. git bundle（2026-11-14 快照，离线 git 历史）
```
G:\AI work\deepseek\work1\alchemy_repo.bundle
```
- 在新电脑：`git clone alchemy_repo.bundle alchemy` → `python unpack_data.py`；
- 同样不含 T55 之后的新提交；最新历史以 GitHub 仓库为准。

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
`t62_phaseA_hf_result.json`、`t62_phaseB_hf_result.json` 等，单个 20~28MB。
其余 >16MB 的中间数据（`t12b_*` 等）仍走 `_data_gz/`。

---

## 5. 新电脑最小检查清单

1. Python 3.10+ 可运行；
2. `pip install -r requirements.txt`（Pillow）；
3. 数据文件存在（或 `python unpack_data.py`）；
4. 冒烟测试：
   ```powershell
   python -c "import pot_v4; print(pot_v4.simulate(['O','K']))"
   ```
5. 读 `HANDOFF.md` 第 0 节的新对话启动语；
6. 需要最新实验时直接跑：`python t62_two_phase.py --phase both`（或复用 `t62_analysis.py` / `t62_render.py`）。

---

## 6. 本次推送记录

| 项目 | 内容 |
|---|---|
| 推送时间 | 2026-11-17（T62 完成后整理推送） |
| 远程 | `https://github.com/fpg9999/alchemy` |
| 分支 | `main` |
| 关键提交 | `T61: 66 种大分子六边形摆放` → `T62: 九元素等量价数两阶段实验` |
| 说明 | 首次把本地 T01~T62 全部提交推送到远程；后续日常同步用 `git push origin main` |
