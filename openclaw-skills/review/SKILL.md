---
name: mind-palace-review
description: MindPalace 复盘 Agent - 专用复盘对话窗口
author: patti-yan1227
version: 1.0.0

triggers:
  - keywords:
      - "*"

config:
  - name: OBSIDIAN_VAULT
    description: "Obsidian Vault 绝对路径"
    required: true
---

# MindPalace 复盘 Agent

## 职责

专用复盘对话窗口。第一条消息触发本周扫描，后续消息在扫描结果基础上继续深挖。

## 使用方式

在飞书里打开此 Bot 的专属对话窗口，发任意消息开始复盘。

## 相关文件

- `agents/review_agent.py` - 复盘 Agent 核心逻辑

---

**Skill ID**: `mind-palace-review`
**Version**: 1.0.0
