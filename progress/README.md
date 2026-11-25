# 双机协作进展区（progress/）

本仓库目前由**两台主机上的作者**共同推进（同一个 GitHub 仓库）。为避免两边同时改共享文档产生冲突，约定：
**每台机器在 `progress/<机器名>/` 下维护自己的进展**，共享根文档（`HANDOFF.md` / `INDEX.md` / `README.md` / `TRANSFER.md`）只做必要的小幅改动。

## 目录约定

```
progress/
├── README.md              # 本文件：协作约定 + 机器登记表
├── _TEMPLATE.md           # 新机器初始化模板（复制成 progress/<机器名>/CURRENT.md）
└── laojiu/                # 牢⑨（本机）
    ├── CURRENT.md         # 滚动状态：在做什么 / 下一步 / 阻塞 / 已知坑
    └── log/YYYY-MM-DD.md  # 每次开工、收工各追加一条，不改旧条目
```

## 机器登记

| 机器名（目录） | 昵称 | 工作目录 | 负责人 | 状态 |
|---|---|---|---|---|
| `laojiu` | 牢⑨ | `G:\AI work\deepseek\work1\alchemy` | 本机 | 活跃 |
| `<your-machine>` | 待登记 | — | 另一台主机 | 对方建好自己的子目录后在此加一行 |

## 冲突规避规则

1. **只写自己的目录**：`progress/<自己机器>/` 之外的改动尽量小，绝不修改对方的子目录。
2. **共享文档只追加、不改对方段落**：`HANDOFF.md` 末尾「维护记录」按日期追加；`INDEX.md` 的「最新补充」追加 bullet；`README.md` 顶部横幅保留最近一两轮即可，旧轮次压成一行。
3. **每次推送前先 `git fetch` + `git rebase origin/main`**；若被拒（`rejected ... fetch first`）就再 fetch / rebase 后重推；**不做 force push**。
4. **开工、收工各写一条 log**：开工记「打算做什么 / 看到什么状态」，收工记「做完什么 / 当前 HEAD / 下一步」。
5. **长任务先在自己的 `CURRENT.md` 登记**，避免两台机器同时改同一批文件；共享脚本、共享数据如要改动，先在当天 log 里说明再动手。
6. 需要更强隔离时，可各用 `machine/laojiu`、`machine/<other>` 分支并行，只把文档类改动合回 `main`；默认仍建议在 `main` 上按目录隔离（简单、可直接看到全局进展）。

## 每日例行（牢⑨）

定时任务（每日 08:30）：拉取远端 → 删除无用生成物 → 更新文档 → 提交推送 → 核验远程结构与 HEAD，并顺带更新 `progress/laojiu/CURRENT.md`、向 `log/` 追加当日记录。

## 同步规则补充（2026-11-25，两台机器都请遵守）

> 背景：本机常有尚未推送的新成果，远端还有对方的工作分支；历史上出现过「拉取/整理时把本地新成果覆盖掉」的风险点。

1. **只同步 `main`**：用 `git fetch origin main` 取主分支最新改动即可，不做 `git fetch --all --prune`，避免把对方其它分支（如 `minimal-force`）的更新引入本地判断。
2. **先算落后量再动手**：`git rev-list --left-right --count HEAD...origin/main`、`git log --oneline HEAD..origin/main`；落后 0 就不需要任何拉取动作。
3. **本地领先时只 rebase**：`git rebase origin/main` 把本地提交搬到远端之上（线性、不丢成果）；本地领先且远端也前进时同样先 fetch 再 rebase。
4. **禁止覆盖式操作**：不 `git reset --hard origin/main`、不 `git checkout -- .`、不 `git clean -fd`、不 force push —— 这些都可能抹掉本地未推送的新成果。
5. **删除前先确认归属**：清理生成物/日志前，先 `git status` 与 `git log` 确认它不是「尚未提交/尚未推送的新成果」；只删缓存、运行日志、明确的重复或废弃文件。
