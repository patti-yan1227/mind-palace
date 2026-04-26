---
name: mind-palace-patti
description: MindPalace 管家 - 意图识别 + 路由到对应 Agent
author: patti-yan1227
version: 2.0.0

# 触发条件：所有消息都经过 Patti 路由
triggers:
  - keywords:
      - "*"

config:
  - name: OBSIDIAN_VAULT
    description: "Obsidian Vault 绝对路径"
    required: true
  - name: RAW_INBOX_DIR
    description: "原始归档目录"
    required: false
    default: "_raw_inbox"
---

# MindPalace 管家 Patti

## 职责

1. 接收所有消息，进行意图识别
2. 路由到对应的子 Agent：
   - 日记/随手记 → `portal_agent`，归档到 `_raw_inbox/`
   - `/炼金` → `alchemy_agent`，批处理原始输入
   - `/复盘` → `review_agent --action scan`，输出本周扫描摘要
   - 学习相关 → `learning_agent`
   - 复杂任务 → 多角色 LLM 编排

## 触发方式

所有消息均触发（catch-all）。

## 子 Agent

| Agent | 职责 | 触发关键词 |
|-------|------|------------|
| portal_agent | 归档原始输入 | 日记/记下来/随手记 |
| alchemy_agent | 批量炼金 | /炼金、/批处理 |
| review_agent | 复盘扫描 | /复盘、周复盘 |
| learning_agent | 学习路由 | /学习 |

## 相关文件

- `agents/patti_agent.py` - 管家核心逻辑
- `agents/portal_agent.py` - 门房归档
- `agents/alchemy_agent.py` - 炼金术
- `agents/review_agent.py` - 复盘扫描

---

**Skill ID**: `mind-palace-patti`  
**Version**: 2.0.0
