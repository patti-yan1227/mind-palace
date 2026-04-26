---
name: mind-palace-learning
description: MindPalace 学习 Agent - 专用学习对话窗口
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

# MindPalace 学习 Agent

## 职责

专用学习对话窗口。支持以下指令：

- 直接发消息 → 推荐 top-3 学习项目
- `学习 <项目名>` → 加载项目状态（map + 开放问题 + 笔记数）
- `搜索 <关键词>` → 跨项目全文搜索

## 使用方式

在飞书里打开此 Bot 的专属对话窗口开始学习。

## 相关文件

- `agents/learning_agent.py` - 学习 Agent 核心逻辑

---

**Skill ID**: `mind-palace-learning`
**Version**: 1.0.0
