# 帕二狗的数字岛屿 (Mind Palace)

> 一人公司认知操作系统 v2.6 — 职责澄清：炼金术记录 vs 复盘洞察

---

## 产品定位

**记忆宫殿**：打造基于本地 Markdown 的高自治数字孪生系统。所有原始输入从同一个入口流入，由 Agent 自动编译出不同维度的结构化视图。

**核心愿景**：全维度个人思维操作系统 / 数字生命孪生系统

**设计哲学**：

| 原则 | 含义 |
|------|------|
| 数据天天记，判断周末下 | 事实性数据 Agent 每天自动记录，主观判断必须经人类闭门会审批 |
| 原始记录层实时归档 | `_raw_inbox` 忠实记录原话，Append-Only，不可变 |
| 客观知识层自动编译 | 日记、跨域关联、互动事实由 Agent 自动编译维护 |
| 主观认知层人类守门 | 价值观、关系判断、体征趋势解读必须经人类亲自开门 |

**LLM Wiki 思想来源**：[karpathy/LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

---

## 系统架构

### 三层架构

```
mind-palace-vault/
├── 原始素材层（Raw Sources）
│   ├── _raw_inbox/                    ← 🔒 不可变区：实时输入档案
│   └── _private_sources/              ← 🔒 不可变区：私域素材保险箱
│
├── 编译层（Wiki）
│   ├── 日记/                          ← 🟢 开放区：T-1 结构化日记
│   ├── 学习/                          ← 🟢 开放区：人机共创学习笔记
│   ├── 项目/                          ← 🟢 开放区：战役项目推进
│   ├── 系统文档/                      ← 🟢 开放区：系统设计文档
│   ├── _compiled/                     ← 🟢 开放区：跨域交叉关联索引
│   ├── _social_graph/log/             ← 🟢 开放区：人际互动事实
│   ├── _biometrics/log/               ← 🟢 开放区：体征与精力数据
│   └── _index.md                      ← 🟢 开放区：全局知识地图
│
├── 日志层（Log）
│   └── _log/                          ← 🟢 开放区：按月分 ingest/query/lint 记录
│
└── 私人区（Review）
    ├── _persona/                      ← 🔴 私人区：核心认知与价值观
    ├── _social_graph/review/          ← 🔴 私人区：关系判断与经营策略
    └── _biometrics/review/            ← 🔴 私人区：体征趋势判断与调整策略
```

### 三级权限模型

| 级别 | 标识 | 房间 | 写入权限 | 触发时机 |
|------|------|------|----------|----------|
| 🔒 | 不可变区 | `_raw_inbox/` | 门房 Portal | 实时 Append-Only |
| 🔒 | 不可变区 | `_private_sources/` | 仅用户手动 | 手动存入 |
| 🟢 | 开放区 | `日记/` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🟢 | 开放区 | `系统文档/` | 人 + Agent | 手动/架构变更时 |
| 🟢 | 开放区 | `学习/` | 学习 Agent + 用户 | 用户主动发起 |
| 🟢 | 开放区 | `项目/` | 多 Agent + 用户 | 战役项目推进 |
| 🟢 | 开放区 | `_compiled/` `_log/` `_index.md` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🟢 | 开放区 | `_social_graph/log/` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🟢 | 开放区 | `_biometrics/log/` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🔴 | 私人区 | `_persona/` | 复盘 Agent（人类授权） | 周末闭门会 |
| 🔴 | 私人区 | `_social_graph/review/` | 复盘 Agent（人类授权） | 周末闭门会 |
| 🔴 | 私人区 | `_biometrics/review/` | 复盘 Agent（人类授权） | 周末闭门会 |

### 数据流转

```
Step 1 摄入与实时归档
  用户消息 → 门房 Portal → _raw_inbox/ (实时归档)
                      ↓
                消息总线广播

Step 1.5 主动学习（按需）
  用户主动发起深度共读 → 学习读书 Agent 激活
  → 人机对话式追加至 `项目/{课题}.md`
  → Session 关闭时扫描变更 → 写入 `_log/YYYY-MM.md`

Step 1.7 情报收集（按需/后台）
  用户设定主题 → 情报收集 Agent 后台运行
  → 自动搜索/抓取/清洗 → 存入 `_private_sources/{主题}/`
  → 通知用户处理

Step 2 T-1 静默炼金（记录机器，不做战略判断）
  午夜 00:00 启动：
  ① 读取 T-1 `_raw_inbox/` → 编纂结构化日记
  ② 编译跨域索引 → 更新 `_index.md` + `_compiled/`
  ③ 记录人际互动 → `_social_graph/log/`
  ④ 记录体征数据 → `_biometrics/log/`
  ⑤ Lint 巡检 → `_lint_report/{date}.md`

Step 3 每周日复盘（合伙人 1v1 会议）
  复盘 Agent 启动：
  → 10 雷达扫描全量（日记 + 笔记 + AI 对话全文 + 互动 + 体征；含心理考古雷达）
  → 6 板块对话式推进（矛盾预标记→AI 摊牌→GRAI→能量→Persona→下周聚焦）
  → 可选板块6 深挖张力（Socratic 考古，挖出"就是这个"的洞察）
  → 用户确认后写入 `_persona/` + 溯源 backlink
```

---

## 六大 Agent

| # | Agent | 工作模式 | 专属写入资产 | 核心动作 |
|---|-------|----------|--------------|----------|
| 1 | **门房 Portal** | 极速调度 | `_raw_inbox/` | 接收原始输入→原封不动 append 至 `_raw_inbox/{date}.md` → 领域打标 → 广播至消息总线 |
| 2 | **学习读书 Agent** | 用户主动发起 | `项目/` | 交互式学伴，NotebookLM 式深度共读。**六种模式**（A 画版图/B 回忆 + 推进/C 处理 Highlights/D 复习测试/E 问题探索/F 四步学习法） |
| 3 | **炼金术 Agent** | 凌晨 00:00 T-1 批处理 | `日记/` `_compiled/` `_social_graph/log/` `_biometrics/log/` `_index.md` `_log/` | 五阶段流水线（记录机器，不做战略判断） |
| 4 | **复盘 Agent** | 每周日用户主动触发 | `_persona/`（经用户确认） | 10 雷达扫描（含心理考古雷达）→6 板块合伙人 1v1 复盘（板块0 矛盾预标记 + 板块6 深挖张力）→Persona 写入 |
| 5 | **检索问答 Agent** | 按需触发 | 无 (全库只读) | 以 `_index.md` 为入口，读取全部房间（含私人区） |
| 6 | **情报收集 Agent** | 后台定时/按需触发 | `_private_sources/` + 临时缓冲区 | 自动搜集用户指定主题的外部信息（论文/新闻/报告） |
| 7 | **Patti 管家 Agent** | 实时 | 无（路由层） | 意图识别、任务路由、多 Agent 编排、用户确认流程 |

> 各 Agent 详细设计见 `agents/` 子目录

---

## 快速开始

### 双版本说明

Mind Palace 提供两个版本：

| 版本 | 用途 | 部署指南 |
|------|------|----------|
| **OpenClaw 版本** | 腾讯云服务器部署，飞书/Telegram 消息入口 | [openclaw-skills/README.md](openclaw-skills/README.md) |
| **Claude Code 版本** | 本地使用，Obsidian 同步 | [claude-code-skills/README.md](claude-code-skills/README.md) |

### OpenClaw 版本（服务器）

```bash
# 1. 配置环境变量
cp .env.example .env
vi .env  # 填入 OBSIDIAN_VAULT 和 API Key

# 2. 创建 symlink
cd /root/workspace/skills
ln -s mind-palace/openclaw-skills/portal mind-palace-portal

# 3. 链接到 OpenClaw
openclaw skills link /root/workspace/skills/mind-palace-portal
```

### Claude Code 版本（本地）

```bash
# 1. 配置环境变量
cp .env.example .env
vi .env  # 填入本地 Vault 路径和 API Key

# 2. 安装依赖
pip install -r requirements.txt

# 3. 链接 Skill
claude skills link ./claude-code-skills/diary-skill
```

### 测试门房

```bash
python agents/portal_agent.py --input "测试消息" --vault "/你的/Vault/路径"
```

### 测试炼金术

```bash
# 手动触发 T-1 批处理（处理昨天的数据）
python agents/alchemy_agent.py --action run --vault "/你的/Vault/路径"

# 或处理指定日期
python agents/alchemy_agent.py --action run --date 2026-04-12 --vault "/你的/Vault/路径"
```

### LLM 配置

编辑 `.env` 文件，选择你的 LLM 服务商：

**Anthropic 官方（推荐）**：
```bash
LLM_API_KEY=sk-ant-xxx
LLM_MODEL=claude-sonnet-4-5-20251001
LLM_API_BASE_URL=https://api.anthropic.com
ALCHEMY_USE_LLM=true
```

**通义千问（DashScope，性价比高）**：
```bash
LLM_API_KEY=sk-sp-xxx
LLM_MODEL=qwen3.5-plus
LLM_API_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic
ALCHEMY_USE_LLM=true
```

---

## 开发计划

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 门房 Portal + raw_inbox 归档 | ✅ 完成 |
| Phase 2 | 炼金术 Agent 五阶段流水线 | ✅ 完成（记录功能已实现） |
| Phase 3 | 复盘 Agent | ✅ 完成（10 雷达扫描 + 6 板块流程 + 心理考古 + 深挖张力 + Persona 写入） |
| Phase 4 | 自动化演进路线 | 📋 设计中 |
| Phase 5 | 学习读书 Agent（交互式学伴） | ✅ 六种模式完成 |
| Phase 6 | 情报收集 Agent | 📋 设计预留 |
| Phase 7 | Patti 管家 Agent | ✅ 完成（意图识别 + 多 Agent 编排） |

### 版本历史

| 版本 | 日期 | 里程碑 |
|------|------|--------|
| v1.0 | 2026-04-08 | 初始架构设计 |
| v1.6 | 2026-04-09 | 三级权限模型统一，log/review 分离 |
| v1.7 | 2026-04-12 | 学习读书 Agent 五种模式设计完成，项目结构重组 |
| v1.8 | 2026-04-12 | LLM Wiki 集成：_index.md 全局索引、_compiled/跨域关联 |
| v2.0 | 2026-04-12 | **学习读书 Agent V1 实现完成** + LLM Wiki 集成 |
| v2.1 | 2026-04-12 | **炼金术 Agent 框架实现**（五阶段流水线） |
| v2.2 | 2026-04-13 | **LLM 日记生成验证通过** + 索引结构优化 + map.md 自动更新 |
| v2.3 | 2026-04-13 | **复盘 Agent 设计完成** + Persona Engine 架构 |
| v2.4 | 2026-04-13 | **自动化演进路线设计** + 情报收集 Agent 设计 |
| v2.5 | 2026-04-14 | 四步学习法 (模式 F) + 素材自动检测 |
| v2.6 | 2026-04-14 | **职责澄清**：炼金术记录 vs 复盘洞察 |
| v2.7 | 2026-04-17 | **Patti 管家 Agent 实现**：意图识别、多 Agent 编排、用户确认流程 |
| v2.8 | 2026-04-23 | **复盘 Agent 深度升级**：AI 对话全文读取、心理考古雷达（反向信号/归因模式）、矛盾检测、板块0矛盾预标记、板块6 Socratic 深挖协议、Windows UTF-8 修复 |

### 下一步工作

当前待办事项按优先级排序：

1. **OpenClaw 飞书集成**（Phase 4）：
   - [ ] 复用 `openclaw-skills/portal/` 代码部署到服务器
   - [ ] 配置飞书机器人 webhook
   - [ ] 设置 cron 定时任务触发炼金术 Agent

2. **学习 Agent 端到端测试**：
   - [ ] 开启完整学习 session（模式 A-F）
   - [ ] 验证 `_log/` 变更报告、`map.md` 自动索引

3. **复盘 Agent 测试与完善**：
   - [ ] 完整测试 5 板块流程（GRAI、能量、Persona 更新、Stop/Start/Continue）
   - [ ] 验证 `_persona/` 写入机制（人类确认后追加 + backlink）

4. **Lint 规则细化**（预留）：
   - [ ] 命名冲突检测（同概念跨项目定义冲突）
   - [ ] 孤立页面检测
   - [ ] 过期引用检测

详细待办清单：[`项目/MindPalace/待办事项清单.md`](项目/MindPalace/待办事项清单.md)

---

## 核心文档

- [`_SYSTEM_RULES.md`](_SYSTEM_RULES.md) - 系统统一规则（所有 Agent 必须遵守）
- [`_index.md`](_index.md) - 全局知识地图
- [`项目/MindPalace/map.md`](项目/MindPalace/map.md) - MindPalace 完整设计文档（v2.6）
- [`项目/MindPalace/待办事项清单.md`](项目/MindPalace/待办事项清单.md) - 下一步工作计划

---

## 不可妥协原则

1. **`_raw_inbox` Append-Only 且不可变**：白天唯一实时写入点，只追加不覆盖
2. **T-1 时间隔离**：炼金术 Agent 只处理昨日数据，严禁触碰当日 raw
3. **私人区人类守门**：`_persona/`、`_social_graph/review/`、`_biometrics/review/` 的任何写入必须经闭门会人类授权
4. **`_private_sources/` 用户独占**：仅用户手动存入，Agent 只可读取不可写入
5. **compiled 只做桥不做副本**：不重复编译已成型的项目笔记，只建立跨域关联
6. **数据天天记，判断周末下**：log 层 Agent 自动写入，review 层仅闭门会写入
7. **日记由 T-1 批处理生成**：日记是 raw 的编纂产物，非实时追加产物
8. **Git 快照与回滚**：每次闭门会后自动 Commit，用户拥有最高回滚权限
9. **异常即停**：任何 Agent 遇到异常必须终止并告警，严禁输出半截数据
10. **检索 Agent 只读**：绝对禁止配置任何写入或修改权限
11. **不存公开知识**：本地只存大模型搜不到的私域内容
12. **_index.md 由炼金术 Agent 统一维护**：学习 Agent 不直接更新

---

## 相关资源

- [PRD v1.6](docs/PRD_v1.6.md) - 初始产品需求文档
- [OpenClaw 文档](https://docs.openclaw.ai/)
- [danghuangshang (AI 朝廷)](https://github.com/wanikua/danghuangshang) - 多 Agent 参考

---

**Version**: 2.8.0 (Phase 3 Complete)  
**Author**: patti-yan1227  
**License**: MIT
