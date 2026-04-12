# Mind Palace - Claude Code 版本

> 帕二狗的记忆宫殿 - Claude Code 本地使用版本

---

## 快速开始

### 1. Clone 仓库

```bash
git clone git@github.com:patti-yan1227/mind-palace.git
cd mind-palace
```

### 2. 配置环境变量

```bash
cp .env.example .env
vi .env
```

填入：
```bash
OBSIDIAN_VAULT="/Users/yourname/Documents/Obsidian Vault"
GOOGLE_API_KEY=你的 Gemini API Key
```

### 3. 链接 Skill 到 Claude Code

```bash
# 在 Claude Code 中
claude skills link ./claude-code-skills/diary-skill
```

### 4. 测试

```bash
# 在 Claude Code 中输入
@日记 今天测试一下日记功能
```

### 5. 检查归档

```bash
ls -la /Users/yourname/Documents/Obsidian\ Vault/_raw_inbox/
cat /Users/yourname/Documents/Obsidian\ Vault/_raw_inbox/2026-04-12-*.md
```

---

## 可用 Skills

| Skill | 状态 | 触发方式 |
|-------|------|----------|
| diary-skill | ✅ 已实现 | @日记 / 记下来 |
| alchemy-skill | ⏳ 待实现 | 手动触发 |

---

## 目录结构

```
claude-code-skills/
├── diary-skill/          # 日记 Skill（已实现）
│   ├── SKILL.md
│   └── handler.py
├── alchemy-skill/        # 炼金术 Skill（待实现）
└── ...
```

---

## 与 OpenClaw 版本的区别

| 维度 | OpenClaw 版本 | Claude Code 版本 |
|------|---------------|------------------|
| 部署位置 | 腾讯云服务器 | 本地 Mac/Windows |
| 消息入口 | 飞书/Telegram | Claude Code 对话 |
| 定时调度 | OpenClaw cron | 手动触发 |
| Vault 路径 | `/root/.openclaw/...` | 本地 Vault |

---

## 相关文档

- [主 README](../README.md) - 项目总览
- [_SYSTEM_RULES.md](../_SYSTEM_RULES.md) - 系统统一规则
- [OpenClaw 版本](../openclaw-skills/README.md) - 服务器部署指南
