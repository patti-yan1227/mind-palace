---
name: mind-palace-portal
description: 记忆宫殿门房 - 实时归档原始输入
author: patti-yan1227
version: 1.0.0

# 触发条件：所有消息都归档
triggers:
  - keywords:
      - "*"  # 所有消息都触发

config:
  - name: OBSIDIAN_VAULT
    description: "Obsidian Vault 绝对路径"
    required: true
  - name: RAW_INBOX_DIR
    description: "原始归档目录"
    required: false
    default: "_raw_inbox"
---

# 记忆宫殿门房 Portal

## 职责

1. 接收所有原始输入（飞书/微信/Telegram 等）
2. 原封不动 append 到 `_raw_inbox/{date}.md`
3. 添加时间戳 `[HH:MM]`
4. 广播到消息总线（供其他 Agent 消费）

## 写入格式

```markdown
## 2026-04-09

[09:15] 今天状态不错，开始搞新系统
[10:30] 门房逻辑跑通了，记录一下
[14:20] 发现个问题，raw_inbox 可能会爆炸
```

## 工程约束

- 按小时分块：`_raw_inbox/2026-04-09-14.md`（防止 Token 爆炸）
- Append-Only：严禁修改已写入内容
- 时间戳格式：`[HH:MM]`

## 相关文件

- `_SYSTEM_RULES.md` - 系统统一规则
- `agents/portal_agent.py` - 门房核心逻辑

---

**Skill ID**: `mind-palace-portal`  
**Version**: 1.0.0
