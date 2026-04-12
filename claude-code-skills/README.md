# Mind Palace - Claude Code 版本

> 帕二狗的记忆宫殿 - Claude Code 本地使用版本

---

## 目录结构说明

Mind Palace 由**两个独立部分**组成，请分开管理：

```
mind-palace/          ← 代码仓库（本 repo，clone 后得到）
├── agents/
├── claude-code-skills/
├── openclaw-skills/
├── CLAUDE.md.example  ← Claude Code 行为配置模板
└── ...

mind-palace-vault/    ← 你的 Vault（私人笔记，不进 git）
├── _raw_inbox/
├── 日记/
├── 项目/
└── ...
```

> ⚠️ **两者必须是不同目录**。代码仓库是工具，Vault 是你的数据，不要混在一起。

---

## 快速开始

### 1. Clone 代码仓库

```bash
git clone https://github.com/patti-yan1227/mind-palace.git
cd mind-palace
```

### 2. 创建 Vault 目录

在代码仓库**之外**单独创建 Vault（可放在 Obsidian 同步目录或任意位置）：

```bash
# Windows 示例
mkdir C:\Users\yourname\mind-palace-vault

# Mac/Linux 示例
mkdir ~/mind-palace-vault
```

在 Vault 目录内创建以下子目录：

```bash
# 进入 Vault 目录后执行
mkdir _raw_inbox _private_sources 日记 项目 _compiled _lint_report
mkdir -p _social_graph/log _social_graph/review
mkdir -p _biometrics/log _biometrics/review
mkdir _persona
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入 Vault 的**绝对路径**：

```bash
# Windows
OBSIDIAN_VAULT=C:\Users\yourname\mind-palace-vault

# Mac/Linux
OBSIDIAN_VAULT=/Users/yourname/mind-palace-vault

LOG_LEVEL=info
TIMEZONE=Asia/Shanghai
```

> ℹ️ diary skill 只写文件，**不需要任何 LLM API Key**。

### 4. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 5. 配置 Claude Code 行为（CLAUDE.md）

```bash
cp CLAUDE.md.example CLAUDE.md
```

编辑 `CLAUDE.md`，将 `YOUR_VAULT_PATH` 替换为你的 Vault 绝对路径。

> ℹ️ `CLAUDE.md` 含本地路径，已加入 `.gitignore`，不会被提交到 git。

### 6. 测试

```bash
python agents/portal_agent.py --input "测试消息" --vault "你的Vault路径"
```

检查归档结果：

```bash
# Windows
type "C:\Users\yourname\mind-palace-vault\_raw_inbox\2026-04-12-*.md"

# Mac/Linux
cat ~/mind-palace-vault/_raw_inbox/2026-04-12-*.md
```

之后在 Claude Code 对话中直接输入触发词即可：

```
@日记 今天测试一下日记功能
记下来 今天状态不错
```

---

## 可用 Skills

| Skill | 状态 | 触发方式 |
|-------|------|----------|
| diary-skill | ✅ 已实现 | @日记 / 记下来 / 记录下来 |
| alchemy-skill | ⏳ 待实现 | 手动触发 |

---

## 与 OpenClaw 版本的区别

| 维度 | OpenClaw 版本 | Claude Code 版本 |
|------|---------------|------------------|
| 部署位置 | 腾讯云服务器 | 本地 Mac/Windows |
| 消息入口 | 飞书/Telegram | Claude Code 对话 |
| 定时调度 | OpenClaw cron | 手动触发 |
| Vault 路径 | `/root/.openclaw/...` | 本地独立 Vault |

---

## 相关文档

- [主 README](../README.md) - 项目总览
- [_SYSTEM_RULES.md](../_SYSTEM_RULES.md) - 系统统一规则
- [OpenClaw 版本](../openclaw-skills/README.md) - 服务器部署指南
