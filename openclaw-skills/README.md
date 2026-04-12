# Mind Palace - OpenClaw 版本

> 帕二狗的记忆宫殿 - OpenClaw 部署版本

---

## 快速开始

### 1. 配置环境变量

```bash
cd /root/workspace/skills/mind-palace
cp .env.example .env
vi .env
```

填入：
```bash
OBSIDIAN_VAULT="/root/.openclaw/workspace/obsidian-vault"
GOOGLE_API_KEY=你的 Gemini API Key
```

### 2. 创建 symlink

```bash
cd /root/workspace/skills

# 门房 Portal
ln -s mind-palace/openclaw-skills/portal mind-palace-portal

# 炼金术（待实现）
# ln -s mind-palace/openclaw-skills/alchemy mind-palace-alchemy
```

### 3. 链接到 OpenClaw

```bash
# 门房 Portal
openclaw skills link /root/workspace/skills/mind-palace-portal

# 查看技能列表
openclaw skills list | grep portal
```

### 4. 测试

```bash
# 在飞书中发送任意消息
# 或命令行测试
python /root/workspace/skills/mind-palace/agents/portal_agent.py \
  --input "测试消息" \
  --vault "/root/.openclaw/workspace/obsidian-vault"
```

### 5. 检查归档

```bash
ls -la /root/.openclaw/workspace/obsidian-vault/_raw_inbox/
cat /root/.openclaw/workspace/obsidian-vault/_raw_inbox/2026-04-12-*.md
```

---

## 目录结构

```
openclaw-skills/
├── mind-palace-portal/       # 门房 Skill（已实现）
│   ├── SKILL.md
│   ├── __init__.py
│   └── handler.py
├── mind-palace-alchemy/      # 炼金术 Skill（待实现）
├── mind-palace-strategy/     # 战略复盘 Skill（待实现）
├── mind-palace-learning/     # 学习读书 Skill（待实现）
└── mind-palace-retrieval/    # 检索问答 Skill（待实现）
```

---

## 可用 Skills

| Skill | 状态 | 触发方式 |
|-------|------|----------|
| mind-palace-portal | ✅ 已实现 | 所有消息 |
| mind-palace-alchemy | ⏳ 待实现 | 凌晨 00:00 |
| mind-palace-strategy | ⏳ 待实现 | 周末触发 |
| mind-palace-learning | ⏳ 待实现 | 用户主动 |
| mind-palace-retrieval | ⏳ 待实现 | 按需触发 |

---

## 相关文档

- [主 README](../README.md) - 项目总览
- [_SYSTEM_RULES.md](../_SYSTEM_RULES.md) - 系统统一规则
- [PRD v1.6](../docs/PRD_v1.6.md) - 完整产品需求
