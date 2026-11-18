# 项目同步与冲突处理（SYNC）

> 本文回答两个问题：**要不要定期推 GitHub**、**冲突怎么解决**。
> 适用对象：2 台机器 / 1~2 人 / 研究型仓库（代码 + 数据 + 报告混在一起）。

---

## 0. 现状（2026-11-17 实测）

| 项 | 状态 |
|---|---|
| 本地是否有 `.git` | **否**（本轮内容是用 ZIP 导入的，不是 clone） |
| 本机是否装了 git | **否**（`git` / `gh` / `git-lfs` 都没有；`winget` 有） |
| GitHub 仓库体积 | 约 108 MB（已含 `t58_result.json` 19MB、`t59_phaseA_hf_result.json` 25MB 等大结果） |
| 大文件约定 | 超过限制的 6 个已 gzip 进 `_data_gz/` + `manifest.json`（含 SHA256） |

**结论：现在做不了任何同步**，必须先装 git。装好之前，本文的第 2 节规则可以先用来约束"哪些文件该改"。

---

## 1. 要不要"定期"推？

**不建议按时间定期（每天/每周），建议按里程碑推。**

原因：研究型仓库的价值在于**可复现的状态点**。按时间推会产出大量"实验跑到一半"的提交，
这些提交既不可复现也没有信息量；而按里程碑推，每个 commit 对应"一轮实验完成 + 结论写进文档"。

建议的提交点：

| 触发 | 提交内容 | tag |
|---|---|---|
| 每完成一个 `T*` 实验 | 脚本 + 结果（大文件走 `_data_gz`）+ `docs/T*.md` | `T64`、`T65`… |
| 内核改动 | `alchemy/` + `tests/` 一个 commit | `kernel-0.2.0` |
| 口径迁移 / 目录替换 | 单独一个 commit（便于回溯） | `catalog-v4` |
| 大改之前 | 先推一次"干净状态" | — |

合理的实际节奏：**一轮实验（几天）推 1~3 次**。不要为了"勤更新"而推半成品。

---

## 2. 什么该进 git、什么不该

这是冲突和仓库膨胀的根源，先定规矩。

| 类别 | 例子 | 体积 | 进 git？ | 理由 |
|---|---|---|---|---|
| 内核代码 | `alchemy/`, `tests/` | 小 | ✅ | 核心资产、需要 diff |
| 研究脚本 | `t*_*.py`, `pot_*.py` | 小 | ✅ | 可复现性的载体 |
| 报告文档 | `docs/*.md`, `HANDOFF.md` | 小 | ✅ | 知识资产 |
| 小块数据 | `substances.json`, `t8_forms.json`, `data/biomes/*.csv` | <1MB | ✅ | 需要版本追踪 |
| 大结果 JSON | `t*_result.json`, `t*_sensitivity.json` | 7~25MB | ⚠️ **建议改走 gz** | 现在已经进来 500MB+，但只有部分 gz 化 |
| 超大中间数据 | `t12b_pairs.jsonl`(149MB), `t4_catalog_all_validated.json`(39MB) | 大 | ❌ 只留 `_data_gz/` | 已有约定，保持 |
| 生成物 | `__pycache__`, `*.pyc`, 临时 `_patch_*.py` | — | ❌ | `.gitignore` 已覆盖 |

**建议的下一步（需你决定）**：把 `t*_result.json` 也纳入 gz 化（复用 `pack_transfer_data.py`
的思路），仓库能从 ~500MB 压到 ~60MB。**但这会改写历史提交里的文件**，所以要在"新增"上做，
不回溯旧提交。

---

## 3. 冲突解决：按文件类别，不按"谁改得多"

### 三条铁律

1. **数据不手工合并**（regenerate, don't merge）
   大 JSON / 目录 / 结果表冲突时**不要看 diff**。用"脚本 + seed"重算，然后 `git checkout --ours/theirs`
   二选一。理由：这些文件是生成物，手工合并出来的既不守恒也不可复现。

2. **代码由测试仲裁**（tests arbitrate）
   `alchemy/`、`pot_*.py` 冲突时：rebase → 跑 `python tests/run_all.py` → **测试不通过的一侧重新实现**。
   内核有 60 项测试 + 与历史实现的差分验证，这就是权威判据，不需要人工争论对错。

3. **文档单写者**（single writer）
   `HANDOFF.md` / `README.md` 指定**一个人**写。其他人只在自己的 `docs/T*.md` 里写结论，
   由写者在下一次汇总时并入。这是避免"文档冲突"最有效的一招。

### 分类对照表

| 冲突文件 | 风险 | 处理 |
|---|---|---|
| `alchemy/`, `tests/`, `pot_*.py` | 中 | rebase + 跑测试；不通过一侧重写 |
| `t6x_*.py`（研究脚本） | 低 | 一个任务一个新文件，天然不冲突；同名说明重复劳动 → 保留一个，另一个改名 `_alt` |
| `docs/T6x_*.md` | 低 | 一人一文件；同一任务两人写 → 合并后删一份 |
| `docs/HANDOFF.md` | **最高** | 单写者；冲突时以写者版本为准，另一侧把要补充的内容贴给写者 |
| `t4_catalog_*.json` | **最高** | 视为构建产物：以 `pot_v4` + 生成脚本重算，禁止 diff 合并 |
| `t*_result.json` | 高 | 同上，重跑（同 seed 应当逐字节一致） |
| `data/biomes/*.csv` | 低 | 重算即可 |

### 跨机器一致性检查

同一个脚本 + 同一个 seed，两台机器应当得到**完全相同**的结果。如果不一致，按顺序查：

1. Python 版本（项目用 3.12）；
2. 规则口径（`pot_all` / `pot_v3` / `pot_v4`）——见 `docs/CALIBER_DIVERGENCE.md`；
3. `set` / `dict` 迭代顺序相关的隐式依赖（Python 3.7+ 字典有序，通常没问题）；
4. 浮点累加顺序（`t55_kinetic_env.py` 的碰撞积分受浮点影响，同 seed 同机器才严格可复现）。

**第 4 条很重要**：粒子模拟对浮点/BLAS/CPU 差异敏感，**跨机器不必追求逐字节一致**，
追求"统计结论一致"即可。真正需要逐字节的是内核（`simulate`），它只用整数运算，跨机器必然一致。

---

## 4. 一次性接入步骤

```powershell
# 1) 装 git（winget 已可用）
winget install --id Git.Git -e --source winget
# 装完必须新开一个 shell，PATH 才会刷新

# 2) 配置（core.autocrlf=false 很重要：避免 Windows/Linux 混用产生全文件 diff）
git config --global user.name  "你的名字"
git config --global user.email "你的邮箱"
git config --global core.autocrlf false

# 3) 克隆到干净目录（不要在原地 git init，避免历史分叉）
cd D:\
git clone https://github.com/fpg9999/alchemy.git alchemy-repo

# 4) 把本轮新增内容复制进去
#    （内核 / 测试 / 示例 / 文档 / 物种表）
Copy-Item -Recurse "D:\Alchemistry DeepSeek工作区\alchemy\alchemy"   "D:\alchemy-repo\" -Force
Copy-Item -Recurse "D:\Alchemistry DeepSeek工作区\alchemy\tests"     "D:\alchemy-repo\" -Force
Copy-Item -Recurse "D:\Alchemistry DeepSeek工作区\alchemy\examples"  "D:\alchemy-repo\" -Force
Copy-Item -Recurse "D:\Alchemistry DeepSeek工作区\alchemy\data"      "D:\alchemy-repo\" -Force
Copy-Item "D:\Alchemistry DeepSeek工作区\alchemy\pyproject.toml"     "D:\alchemy-repo\" -Force
Copy-Item "D:\Alchemistry DeepSeek工作区\alchemy\docs\*.md"          "D:\alchemy-repo\docs\" -Force

# 5) 恢复大数据（clone 后只有 _data_gz/）
cd D:\alchemy-repo
python unpack_data.py

# 6) 提交并推送
git add -A
git status --short          # 先看清楚要提交什么
git commit -m "kernel: 抽出 alchemy.core（四入口+60项测试）、口径审计、物种表管线"
git push
```

> 为什么不直接在当前目录 `git init`：当前目录没有 `.git`，`git init` 后会得到一条全新的
> 空历史，和 GitHub 上的历史分叉，第一次 push 会被拒绝（或需要 `--force` 覆盖远端）。
> clone-fresh 是唯一安全做法。

---

## 5. 日常流程（建议）

```
写代码/跑实验
  → 本地测试跑绿（python tests/run_all.py）
  → git add -A && git commit -m "<范围>: <做了什么>"
  → 一轮实验结束 / 内核改动完成 → git push
```

分支策略（2 人以内够用）：

- `main`：只放**已验证**的状态（测试绿 + 实验完成 + 文档已写）
- `exp/T64` 之类短分支：跑实验期间用；完成后 squash merge 进 `main`
- 打 tag 标记里程碑：`T64`、`kernel-0.2.0`

## 6. 冲突实操（遇到时才需要看）

```powershell
git pull --rebase            # 线性历史，冲突少
# 若冲突：
git status                   # 看清哪一类文件冲突
#  代码冲突 -> 手工解决 -> python tests/run_all.py -> git add -A; git rebase --continue
#  数据冲突 -> 选一侧：git checkout --ours <file>  或重跑脚本生成
git push
```

实在乱了（rebase 到一半想放弃）：`git rebase --abort`，回到 pull 之前。

---

## 7. 需要你确认的三个决定

1. **要不要现在装 git 并把本轮内容推上去？**（需要你授权安装软件 + 向你的 GitHub 推送）
2. **`t*_result.json` 要不要改走 gz？**（仓库 500MB → 60MB，但改变现有习惯）
3. **`HANDOFF.md` 的单写者是谁？**（不定这个，文档冲突迟早发生）
