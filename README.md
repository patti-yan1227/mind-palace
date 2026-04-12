# 帕二狗的数字岛屿 (Mind Palace)

> 一人公司认知操作系统 v2.0 - 学习 Agent V1 完成 + 炼金术 Agent 框架就绪

---

## 产品定位

**记忆宫殿**：所有原始输入从同一个入口流入，由 Agent 自动编译出不同维度的结构化视图。

**核心哲学**：
- 数据天天记，判断周末下
- 事实自动记录，主观判断需人类审批
- 原始记录不可变，编译产物可更新

---

## 系统架构

### 三级权限模型

| 层级 | 房间 | 写入权限 | 触发时机 |
|------|------|----------|----------|
| 🔒 不可变区 | `_raw_inbox/` | 门房 Portal | 实时 |
| 🔒 不可变区 | `_private_sources/` | 用户手动 | 手动 |
| 🟢 开放区 | `日记/` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🟢 开放区 | `项目/` | 学习读书 Agent + 用户 | 用户主动发起 |
| 🟢 开放区 | `_compiled/` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🟢 开放区 | `_social_graph/log/` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🟢 开放区 | `_biometrics/log/` | 炼金术 Agent | 凌晨 T-1 批处理 |
| 🔴 私人区 | `_persona/` | 战略复盘 Agent | 周末闭门会 |
| 🔴 私人区 | `_social_graph/review/` | 战略复盘 Agent | 周末闭门会 |
| 🔴 私人区 | `_biometrics/review/` | 战略复盘 Agent | 周末闭门会 |

### 数据流转

```
用户消息 → 门房 Portal → _raw_inbox/ (实时归档)
                    ↓
              消息总线广播
                    ↓
        炼金术 Agent (凌晨 00:00)
        ├── 编纂日记 → 日记/
        ├── 萃取金砖 → _pending_pointers/
        ├── 编译索引 → _compiled/
        ├── 记录人际 → _social_graph/log/
        ├── 记录体征 → _biometrics/log/
        └── Lint 巡检 → _lint_report/
                    ↓
        战略复盘 Agent (周末)
        ├── 身体复盘 → _biometrics/review/
        ├── 关系复盘 → _social_graph/review/
        └── 认知复盘 → _persona/
```

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

# 2. 链接 Skill
claude skills link ./claude-code-skills/diary-skill
```

### 测试门房

```bash
python agents/portal_agent.py --input "测试消息" --vault "/你的/Vault/路径"
```

---

## 开发计划

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 门房 Portal + raw_inbox 归档 | ✅ 完成 |
| Phase 2 | 炼金术 Agent 七阶段流水线 | 🚧 框架完成，LLM 萃取待填充 |
| Phase 3 | 战略复盘 Agent 三议程闭门会 | ⏳ 待开发 |
| Phase 4 | 检索问答 Agent（全库只读） | ⏳ 待开发 |
| Phase 5 | 学习读书 Agent（交互式学伴） | ✅ V1 完成 |

### 版本历史

| 版本 | 日期 | 里程碑 |
|------|------|--------|
| v1.0 | 2026-04-08 | 初始架构设计 |
| v1.6 | 2026-04-09 | 三级权限模型统一，log/review 分离 |
| v1.7 | 2026-04-12 | 学习读书 Agent 五种模式设计完成 |
| v2.0 | 2026-04-12 | **学习读书 Agent V1 实现完成** + LLM Wiki 集成 |
| v2.1 | 2026-04-12 | **炼金术 Agent 框架实现**（七阶段流水线 + _index.md + _compiled/） |

### 下一步工作

1. **完善炼金术 Agent**：
   - [ ] LLM 萃取金砖逻辑（从日记中提取核心洞察）
   - [ ] 人际互动提取（从日记中识别人物和事件）
   - [ ] 体征数据提取（睡眠、运动、情绪结构化）
   - [ ] Lint 规则细化（孤立页面、过期引用、矛盾检测）

2. **战略复盘 Agent**：
   - [ ] 周日闭门会三议程交互流程
   - [ ] 人类授权写入私人区
   - [ ] Git 自动快照与回滚

3. **检索问答 Agent**：
   - [ ] 以 `_index.md` 为入口的全库检索
   - [ ] 读取私人区偏好校准回答视角

---

## 核心文档

- [`_SYSTEM_RULES.md`](_SYSTEM_RULES.md) - 系统统一规则（所有 Agent 必须遵守）
- [`_index.md`](_index.md) - 全局知识地图（已创建初始框架）
- [`项目/MindPalace/map.md`](项目/MindPalace/map.md) - MindPalace 完整设计文档（v1.9）

---

## 相关资源

- [PRD v1.6](docs/PRD_v1.6.md) - 完整产品需求文档
- [OpenClaw 文档](https://docs.openclaw.ai/)
- [danghuangshang (AI 朝廷)](https://github.com/wanikua/danghuangshang) - 多 Agent 参考

---

**Version**: 1.0.0 (Phase 1)  
**Author**: patti-yan1227  
**License**: MIT
