# Git 提交脚本 - Mind Palace v2.2

Write-Host "=== Mind Palace v2.2 Git 提交 ===" -ForegroundColor Green

# 1. 查看当前状态
Write-Host "`n[1/5] 检查 git 状态..." -ForegroundColor Cyan
git status

# 2. 添加文件
Write-Host "`n[2/5] 添加文件..." -ForegroundColor Cyan
git add agents/alchemy_agent.py
git add agents/learning_agent.py
git add .env.example
git add requirements.txt
git add README.md
git add claude-code-skills/

# 3. 查看将要提交的文件
Write-Host "`n[3/5] 待提交文件列表:" -ForegroundColor Cyan
git status --short

# 4. 提交
Write-Host "`n[4/5] 创建提交..." -ForegroundColor Cyan
git commit -m "feat: LLM 日记生成验证通过 + 索引结构优化 (v2.2)

主要变更:
- 炼金术 Agent: 实现 LLM 日记生成 (支持通义千问/Anthropic)
  * 添加 load_dotenv() 支持.env 配置
  * 修复 ThinkingBlock 混入日记内容的问题
  * 优化日记 prompt 禁止输出多余标题

- 索引结构优化:
  * _index.md 简化为导航层，只列出项目 map.md 入口
  * 移除项目详细文件列表，提高查询性能

- 学习 Agent: close_session 时自动更新 map.md
  * 新增 update_map_md() 函数
  * 自动生成笔记索引、开放问题、最近对话

- 配置更新:
  * .env.example 使用 Claude 官方配置示例
  * requirements.txt 新增 python-dotenv, anthropic 依赖

- 文档更新:
  * README.md 更新至 v2.2
  * 增加 LLM 配置说明和炼金术测试命令

技术细节:
- llm_generate() 跳过 thinking 块，只保留 text 块
- 支持多 LLM 服务商 (Anthropic/通义千问/Ollama)
- map.md 自动索引在'五、项目索引'章节"

# 5. 推送
Write-Host "`n[5/5] 推送到 GitHub..." -ForegroundColor Cyan
git push

Write-Host "`n=== 提交完成! ===" -ForegroundColor Green
