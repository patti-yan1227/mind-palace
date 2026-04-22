# Review Skill — 战略复盘 Agent

## 触发方式

用户输入以下任意内容时触发：
- `/复盘`
- `开始复盘`
- `周复盘`

---

## 首次运行 vs 常规运行

- **首次运行**：`_persona/` 尚未初始化时，扫描全量历史数据，生成 Persona 基准版本（v1.0）
- **常规运行**：每周日，只扫描本周新增/变更内容，与现有 Persona 对比

---

## 完整交互流程

### 板块 0 — 矛盾预标记（2 分钟，扫描前）

在运行 scan 之前，先问用户：
> "这段时间有没有哪件事，你觉得'自己不行'或'差一点'？说 1-3 个。"

把这些作为**深挖优先级**，在扫描和对话里主动寻找与这些自评相矛盾的证据。

---

### 板块 1 — AI 摊牌（扫描）

```bash
# 首次运行
python agents/review_agent.py --action scan --first-run --start-date <起始日期> --vault "C:\Users\xulingyan\mind-palace-vault"

# 常规扫描
python agents/review_agent.py --action scan --vault "C:\Users\xulingyan\mind-palace-vault"
```

向用户展示 8 雷达发现，格式：
- `[本质理解/跨域模式/决策背景/价值观碰撞]` 高价值内容 → 引入板块 4 讨论素材
- `[A_core/B_filter/C_domain/D_trajectory]` Persona 候选更新 → 板块 4 逐维度确认
- 值得深聊的张力 → 引出 Socratic questioning

---

### 板块 2 — 本周得失（GRAI 框架）

直接在对话中进行，无需调用 agent：

| 维度 | 问题 |
|------|------|
| G（Goal） | 这周设定了什么目标？ |
| R（Result） | 实际发生了什么？差距在哪？ |
| A（Analysis） | 成败的关键因素是什么？ |
| I（Insight） | 这背后有什么规律？ |

---

### 板块 3 — 能量与状态

直接在对话中进行，无需调用 agent：
- **充电时刻**：什么事情做完后精力更足？
- **耗电时刻**：什么事情做完后很空洞？

---

### 板块 4 — Persona 更新（核心）

逐维度讨论，用户说"记下来"/"更新"/"确认"时调用：

```bash
python agents/review_agent.py --action update_persona \
  --dimension <A_core|B_filter|C_domain|D_trajectory> \
  --input "<Markdown格式内容>" \
  --source-ref "复盘 <日期>" \
  --vault "C:\Users\xulingyan\mind-palace-vault"
```

#### `--input` 必须使用以下 Markdown 格式（不得传入无结构散文）：

```markdown
### [洞察名称]
> 来源：[复盘日期 · 板块名]

**一句话：** [核心结论，一句话]

- [要点1]
- [要点2]
- **[标签]：** [补充说明]

⚠️ [可选：待深化/待验证 的标注]
```

#### 4 个维度写入规则

| 维度 | 文件 | 更新频率 | 内容类型 |
|------|------|---------|---------|
| A_core | `_persona/A_core.md` | 月级 | 核心价值观/长期目标/性格底层 |
| B_filter | `_persona/B_filter.md` | 周级微调 | 审美/品味/认知偏好/风格原则 |
| C_domain | `_persona/C_domain.md` | 半自动 | 专业身份标签/已验证判断/深入领域 |
| D_trajectory | `_persona/D_trajectory.md` | 每周重写 | 当前优先级/焦虑点/未竟之事 |

---

### 板块 5 — 下周聚焦（Stop/Start/Continue）

对话确认后，直接写入 D_trajectory：

```bash
python agents/review_agent.py --action update_persona \
  --dimension D_trajectory \
  --input "Stop：...\nStart：...\nContinue：...\n3个优先级：..." \
  --source-ref "复盘 <日期>" \
  --vault "C:\Users\xulingyan\mind-palace-vault"
```

---

### 板块 6 — 深挖张力（可选，20-30 分钟）

**触发条件：** 扫描发现"值得深挖的矛盾"不为空，或用户主动说"我想把这个挖透"。

**执行步骤：**

1. Claude 呈现"矛盾快照"——从 AI 对话和日记里提取对立论述，逐一展示
2. Claude 主导 Socratic questioning（Claude 提问，不是等用户主动说）：
   - "你在 X 地方说'...'，在 Y 地方你做了 Z。这两件事怎么共存？"
   - "如果这个判断是错的，什么证据能说服你？"
   - "这个感受最早是什么时候出现的？"
3. 持续追问，直到用户说出"对，就是这个"——那句话就是洞察
4. Claude 先说那句话，再问用户是否写入 Persona：
   > "我想把'...'写进 A_core，你看这个说法准不准？"
5. 用户确认后，格式化为标准 update_persona 格式调用 agent

---

### 结束 — 写入复盘日志

```bash
python agents/review_agent.py --action close_review --vault "C:\Users\xulingyan\mind-palace-vault"
```

---

## 核心约束

- 严禁直接用 Write/Edit 写入 `_persona/` — 必须通过 `update_persona` action
- `_persona/` 只有用户明确确认后才能写入
