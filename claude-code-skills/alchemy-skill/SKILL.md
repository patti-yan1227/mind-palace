# Alchemy Skill — 炼金术 Agent

## 触发方式

用户输入以下任意内容时触发：
- `/炼金`
- `/批处理`
- `运行炼金术`

---

## 执行命令

```bash
# 默认处理昨天的数据
python agents/alchemy_agent.py --action run --vault "C:\Users\xulingyan\mind-palace-vault"
```

---

## 六阶段流水线

| 阶段 | 操作 | 输出位置 |
|------|------|---------|
| 1. 编纂日记 | 读取 T-1 `_raw_inbox/` | `日记/{date}.md` |
| 2. 萃取金砖 | 从日记/项目变动提取核心洞察 | — |
| 3. 读取变更报告 | 从 `_log/` 读取昨日学习 session 的变更 | — |
| 4. 编译跨域索引 | 更新全局索引 | `_index.md` + `_compiled/` |
| 5. 记录人际互动 | 提取社交记录 | `_social_graph/log/` |
| 6. 记录体征数据 | 提取健康数据 | `_biometrics/log/` |
| 7. Lint 巡检 | 检查 Vault 健康状态 | `_lint_report/{date}.md` |

---

## 手动触发子任务

```bash
# 仅编纂日记
python agents/alchemy_agent.py --action compile_diary --vault "C:\Users\xulingyan\mind-palace-vault"

# 仅更新全局索引
python agents/alchemy_agent.py --action update_index --vault "C:\Users\xulingyan\mind-palace-vault"

# 仅 Lint 检查
python agents/alchemy_agent.py --action lint --vault "C:\Users\xulingyan\mind-palace-vault"
```

---

## 目录写入权限

炼金术 Agent 是唯一可写入以下目录的角色：

| 目录 | 触发时机 |
|------|---------|
| `日记/` | 凌晨 T-1 批处理 |
| `_compiled/` | 凌晨 T-1 批处理 |
| `_index.md` | 凌晨 T-1 批处理 |
| `_log/` | 批处理 + session 关闭时 |
