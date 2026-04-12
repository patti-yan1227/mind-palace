# Learning Skill — 学习读书 Agent

## 触发方式

用户输入以下任意内容时触发：
- `/学习`
- `@学习`
- 消息以 `学习` 开头且后面跟话题或模式名

此外，每次 Claude Code 对话**启动时**，自动静默执行 `check_and_notify`（见 CLAUDE.md）。

---

## 五种学习模式

| 模式 | 名称 | 适用场景 |
|------|------|----------|
| A | 画版图（MIT 领图法） | 新话题、新书第一次、旧项目重新梳理 |
| B | 回忆 + 推进（间隔重复） | 继续现有项目，距上次 >1 天 |
| C | 处理新内容（苏格拉底式） | 刚导入微信读书/PDF highlights |
| D | 复习旧笔记（测试效应） | 主动复习，距上次看笔记 >7 天 |
| E | 问题驱动探索（定向研究） | 带着具体问题来，先搜已有内容 |

---

## 完整交互流程

### Step 1 — 展示上下文，确认意图

调用：
```
python agents/learning_agent.py --vault <vault> --action recommend
```

呈现推荐 + 允许用户自由输入。

### Step 2 — 用户选择模式

Claude 给建议，用户确认。确认后调用：
```
python agents/learning_agent.py --vault <vault> --action load --project <名>
```

加载全量上下文（map + questions + notes_index + recent_dialogue + new_highlights）。

### Step 3 — 交互式学习

开启 session：
```
python agents/learning_agent.py --vault <vault> --action open_session --project <名> --mode <A/B/C/D/E>
```

**模式 A**：提问框架→用户回答→更新 map.md→生成理解题→逐题作答
**模式 B**：先不看笔记回忆→对比 notes/→推进 questions.md 未解决问题
**模式 C**：逐条过 highlights，先问"你为什么划这句"→感知是否保存
**模式 D**：随机抽 3-5 个概念名自测→对比笔记→提议更新版本
**模式 E**：用户输入问题→搜索已有内容→报告已知 + 缺口→决定归入哪个项目

### Step 4 — 记录与保存

#### 用户主动触发

| 用户说 | Claude 处理 |
|--------|-------------|
| "记下来" | 根据内容提炼名字，保存到 `notes/` |
| "存为笔记" | 同上 |
| "这个要全记录" | 完整保存（到 `dialogue/` 或单独文件） |
| "记下来，叫 XXX" | 用用户给的名字 |

#### Claude 主动感知

Claude 主动感知以下信号并提议保存：

| 信号 | Claude 的提议 |
|------|--------------|
| 用户表达了清晰理解/洞察 | "这个值得记下来——给这个洞察起个名字？" |
| 用户提出未解问题 | "这个问题记到你的问题池？" |
| 讨论到一个结论 | "要不要存成今天的笔记？" |
| 用户说"对对对就是这个意思" | "我来帮你把这个理解存下来，确认一下：<提炼版本>" |

用户只需回复 **是/好/存/不用**。

#### 归类规则

| 内容类型 | 存放位置 |
|----------|----------|
| 概念/框架/方法论 | `项目/<项目名>/notes/` |
| 对话全过程 | `项目/<项目名>/dialogue/` |
| 问题/困惑 | 追加到 `项目/<项目名>/questions.md` |
| 外部素材（视频/文章） | `_private_sources/<项目名>/` |

#### 保存命令

```bash
# 保存笔记
python agents/learning_agent.py --vault <vault> --action save_note \
  --project <名> --concept <概念名> --input "<内容>"

# 记录问题
python agents/learning_agent.py --vault <vault> --action append_question \
  --project <名> --input "<问题>"

# 保存对话
python agents/learning_agent.py --vault <vault> --action save_dialogue \
  --project <名> --input "<对话内容>"
```

### Step 5 — 关闭 Session

用户说"结束"/"今天到这"时：
```
python agents/learning_agent.py --vault <vault> --action close_session --project <名>
```

输出摘要并写入 `_raw_inbox/`。

---

## 目录结构

每个项目在 Vault 中的布局：

```
项目/<项目名>/
├── map.md            # 知识版图（共识/框架/分歧/未解问题）
├── questions.md      # 开放问题池
├── _session.json     # 当前活跃 session（存在=学习中）
├── notes/
│   └── <概念>.md     # 原子概念笔记
└── dialogue/
    └── YYYY-MM-DD.md # 每日学习对话记录

_private_sources/<项目名>/
└── *.md              # 外部素材（视频摘要/文章/highlights 等）
```

**注意：** `_private_sources/` 下的所有 `.md` 文件都会被读取，不限于特定子目录。
