---
name: mind-palace-diary
description: 记忆宫殿日记 Skill - 本地 Obsidian 归档
author: patti-yan1227
version: 1.0.0

# 触发条件
triggers:
  - keywords:
      - "@日记"
      - "记下来"
      - "记录下来"
      - "记一下"
      - "记录一下"
      - "记一嘴"
  - patterns:
      - ".*日记.*"

config:
  - name: OBSIDIAN_VAULT
    description: "本地 Obsidian Vault 绝对路径"
    required: true
    example: "/Users/yourname/Documents/Obsidian Vault"
  - name: RAW_INBOX_DIR
    description: "原始归档目录"
    required: false
    default: "_raw_inbox"
---

# 记忆宫殿日记 Skill

## 职责

1. 接收用户日记输入
2. 原封不动 append 到 `_raw_inbox/{date}-{hour}.md`
3. 添加时间戳 `[HH:MM]`

## 写入格式

```markdown
## 2026-04-12

[14:15] 今天状态不错，开始搞新系统
[15:30] 门房逻辑跑通了，记录一下
```

## 工程约束

- 按小时分块：`_raw_inbox/2026-04-12-14.md`
- Append-Only：严禁修改已写入内容

## 相关文件

- `../agents/portal_agent.py` - 门房核心逻辑
- `../_SYSTEM_RULES.md` - 系统统一规则

---

**Skill ID**: `mind-palace-diary`  
**Version**: 1.0.0
