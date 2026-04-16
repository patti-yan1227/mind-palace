# 记忆宫殿系统规则

> 版本：v1.6.0  
> 所有 Agent 启动时必须先读取此文件

---

## 不可妥协原则（写入即死）

### 1. raw_inbox Append-Only
- 只追加不覆盖
- 任何 Agent 严禁修改已写入内容
- 白天唯一实时写入点

### 2. T-1 时间隔离
- 炼金术只处理昨日数据
- 严禁触碰当日 raw_inbox

### 3. log/review 分离
- log 层：事实，Agent 自动写入
- review 层：判断，仅闭门会人类授权后写入

### 4. compiled 只做桥不做副本
- 不重复编译已成型的项目笔记
- 只建立跨域关联（实体页 + 关系页）

### 5. 检索 Agent 只读
- 绝对禁止配置任何写入权限
- 可读取全部房间（含私人区）用于校准回答

### 6. _private_sources 用户独占
- 仅用户手动存入
- Agent 只可读取，不可写入

### 7. 数据天天记，判断周末下
- social_graph/log、biometrics/log：每天自动记录
- social_graph/review、biometrics/review：仅周末闭门会写入

### 8. 日记由 T-1 批处理生成
- 日记是 raw 的编纂产物，非实时追加

### 9. Git 快照与回滚
- 每次闭门会后自动 Commit
- 用户拥有最高回滚权限

### 10. 异常即停
- 任何 Agent 遇到异常必须终止并告警
- 严禁输出半截数据

### 11. 不存公开知识
- 本地只存大模型搜不到的私域内容

---

## 工程约束（防止系统爆炸）

### 12. raw_inbox 分段归档
- 按小时分块：`{date}-{HH}.md`
- 或按条数分块：每 50 条新文件
- 防止午夜批处理 Token 爆炸

### 13. compiled 结构约束
- 只允许：实体页（人/公司/概念）+ 关系页（A↔B）
- 禁止：多层嵌套分析、长文本总结

### 14. Lint 增量扫描
- 只扫描 T-1 变更影响范围
- 禁止全库扫描（性能瓶颈）

### 15. review 版本控制
- 每条判断必须带：version + confidence + expire_date
- 防止认知固化

---

## 目录权限矩阵

| 目录 | 写入权限 | 触发时机 |
|------|----------|----------|
| `_raw_inbox/` | 门房 Portal | 实时 |
| `_private_sources/` | 用户手动 | 手动 |
| `日记/` | 炼金术 Agent | 凌晨 00:00 T-1 |
| `系统文档/` | 人 + Agent | 手动/架构变更时 |
| `学习/` | 学习读书 Agent + 用户 | 用户主动发起 |
| `项目/` | 多 Agent + 用户 | 战役项目推进 |
| `_compiled/` | 炼金术 Agent | 凌晨 00:00 T-1 |
| `_social_graph/log/` | 炼金术 Agent | 凌晨 00:00 T-1 |
| `_social_graph/review/` | 战略复盘 Agent | 周末闭门会 |
| `_biometrics/log/` | 炼金术 Agent | 凌晨 00:00 T-1 |
| `_biometrics/review/` | 战略复盘 Agent | 周末闭门会 |
| `_persona/` | 战略复盘 Agent | 周末闭门会 |
| `_lint_report/` | 炼金术 Agent | 凌晨 00:00 T-1 |

---

## Agent 启动检查清单

每个 Agent 启动时必须确认：
- [ ] 已读取 `_SYSTEM_RULES.md`
- [ ] 已配置 OBSIDIAN_VAULT 路径
- [ ] 已确认自己的写入权限范围
- [ ] 已配置 LLM API Key
