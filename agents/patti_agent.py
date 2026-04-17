#!/usr/bin/env python3
"""
Patti - MindPalace 管家 Agent

职责：
1. 意图识别 — 听懂用户要什么
2. 任务路由 — 调用对应的 Agent
3. 多 Agent 编排 — 复杂任务时组织多个 Agent 协作
4. 与用户确认 — 复杂任务必须先确认再执行
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ==================== 配置 ====================

DEFAULT_VAULT = os.getenv('OBSIDIAN_VAULT', '')
LEARNING_DIR = '学习'
PROJECTS_DIR = '项目'

# 意图关键词
DIARY_KEYWORDS = ['日记', '记下来', '记录下来', '记一下', '@日记']
LEARNING_KEYWORDS = ['学习']
ALCHEMY_KEYWORDS = ['/炼金', '批处理']
REVIEW_KEYWORDS = ['复盘', '总结']
COMPLEX_KEYWORDS = ['分析', '帮我', '我想', '规划']

# 角色 Agent 定义
ROLE_AGENTS = {
    'architect': '架构师',
    'reviewer': '批判者',
    'facilitator': '主持人',
    'researcher': '研究员',
}

# LLM 配置
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-6')
LLM_API_BASE_URL = os.getenv('LLM_API_BASE_URL', 'https://api.anthropic.com')


# ==================== LLM 工具 ====================

def get_role_system_prompt(role_name: str) -> str:
    """从角色 Agent 文件中读取 System Prompt"""
    vault = _get_vault(DEFAULT_VAULT)
    agent_file = vault / '.claude' / 'agents' / f'{role_name}.md'
    if not agent_file.exists():
        return None

    content = agent_file.read_text(encoding='utf-8')
    # 解析 Markdown 文件，提取 body（frontmatter 之后的内容）
    parts = content.split('---', 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return content.strip()


def call_llm(prompt: str, system: str = None) -> str:
    """调用 LLM API"""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)

        kwargs = dict(
            model=LLM_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        if system:
            kwargs['system'] = system

        response = client.messages.create(**kwargs)
        return response.content[0].text
    except ImportError:
        return "错误：请安装 anthropic SDK: pip install anthropic"
    except Exception as e:
        return f"LLM 调用失败：{e}"


# ==================== 工具函数 ====================

def _get_vault(vault_path: str = None) -> Path:
    v = vault_path or DEFAULT_VAULT
    if not v:
        raise ValueError("未指定 vault 路径，请设置 OBSIDIAN_VAULT 环境变量或传入 --vault 参数")
    return Path(v)


def extract_project_name(text: str) -> str:
    """从用户输入中提取项目名"""
    # 匹配 "学习 XXX" 中的 XXX
    match = re.search(r'学习\s*(.+?)(?:的 | 吗 | 吧 | 了 | ！|!|\?|？|$)', text)
    if match:
        return match.group(1).strip()
    return None


def project_exists(project_name: str, vault_path: str) -> bool:
    """检查项目是否存在"""
    vault = _get_vault(vault_path)
    # 先检查学习目录，再检查项目目录
    learning_path = vault / LEARNING_DIR / project_name
    projects_path = vault / PROJECTS_DIR / project_name
    return learning_path.exists() or projects_path.exists()


# ==================== 意图识别 ====================

def classify_intent(user_input: str, vault_path: str = None) -> tuple:
    """
    意图识别
    返回：(intent_type, context)
    """
    text = user_input.lower()

    # 1. 日记类
    for kw in DIARY_KEYWORDS:
        if kw in text:
            # 提取要记的内容（去掉触发词）
            content = user_input
            for kw in DIARY_KEYWORDS:
                content = content.replace(kw, '')
            return ('日记', {'input': content.strip()})

    # 2. 学习类
    for kw in LEARNING_KEYWORDS:
        if kw in text:
            project_name = extract_project_name(user_input)
            if project_name:
                if project_exists(project_name, vault_path):
                    return ('学习-load', {'project': project_name})
                else:
                    return ('学习-new', {'project': project_name})
            return ('学习-new', {'project': None})

    # 3. 炼金/复盘
    for kw in ALCHEMY_KEYWORDS:
        if kw in text:
            return ('炼金', {})

    for kw in REVIEW_KEYWORDS:
        if kw in text:
            return ('复盘', {})

    # 4. 复杂任务
    for kw in COMPLEX_KEYWORDS:
        if kw in text:
            return ('复杂任务', {'input': user_input})

    return ('未知', {'input': user_input})


# ==================== 路由执行 ====================

def run_portal(input_text: str, vault_path: str) -> str:
    """调用 Portal Agent"""
    cmd = [
        'python', 'agents/portal_agent.py',
        '--input', input_text,
        '--vault', vault_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


def run_learning(action: str, project: str, vault_path: str) -> str:
    """调用 Learning Agent"""
    cmd = [
        'python', 'agents/learning_agent.py',
        '--action', action,
        '--project', project,
        '--vault', vault_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


def create_learning_project(project_name: str, vault_path: str) -> str:
    """创建新的学习项目"""
    vault = _get_vault(vault_path)
    project_dir = vault / LEARNING_DIR / project_name

    if project_dir.exists():
        return f"项目 '{project_name}' 已存在：{project_dir}"

    # 创建项目目录结构
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / 'notes').mkdir(exist_ok=True)
    (project_dir / 'dialogue').mkdir(exist_ok=True)

    # 创建 map.md
    map_file = project_dir / 'map.md'
    map_file.write_text(f"""# {project_name}

## 状态
- 创建日期：{datetime.now().strftime('%Y-%m-%d')}
- 当前模式：未设置

## 核心概念
<!-- 概念笔记索引 -->

## 未解问题
<!-- 问题列表 -->

## 地图
<!-- 项目全景图 -->
""", encoding='utf-8')

    # 创建 questions.md
    questions_file = project_dir / 'questions.md'
    questions_file.write_text("""# 问题清单

<!-- 格式：
## 问题描述
- 提出时间：YYYY-MM-DD
- 状态：未解决
- 相关概念：[]
-->
""", encoding='utf-8')

    # 记录到 _log/
    log_dir = vault / '_log'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f'{project_name}_created.md'
    log_file.write_text(f"""# 项目创建日志

- 项目名称：{project_name}
- 创建日期：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 目录：{project_dir.relative_to(vault)}
- 初始化文件：map.md, questions.md
""", encoding='utf-8')

    return f"""项目 '{project_name}' 创建成功！

**目录结构：**
```
{LEARNING_DIR}/{project_name}/
├── map.md          # 项目地图
├── questions.md    # 问题清单
├── notes/          # 概念笔记
└── dialogue/       # 对话记录
```

**下一步：**
1. 运行 `/学习 {project_name}` 开始学习
2. 选择学习模式（A-画版图 / B-回忆 + 推进 / C-处理 Highlights / D-复习 / E-问题驱动）"""


def run_alchemy(vault_path: str) -> str:
    """调用 Alchemy Agent"""
    cmd = [
        'python', 'agents/alchemy_agent.py',
        '--action', 'run',
        '--vault', vault_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


def run_review(vault_path: str) -> str:
    """调用 Review Agent"""
    cmd = [
        'python', 'agents/review_agent.py',
        '--action', 'run',
        '--vault', vault_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


# ==================== 角色 Agent 管理 ====================

def check_role_exists(role_name: str, vault_path: str) -> bool:
    """检查角色 Agent 是否存在"""
    vault = _get_vault(vault_path)
    agent_file = vault / '.claude' / 'agents' / f'{role_name}.md'
    return agent_file.exists()


def get_missing_roles(required_roles: list, vault_path: str) -> list:
    """返回缺失的角色列表"""
    return [role for role in required_roles if not check_role_exists(role, vault_path)]


def prompt_create_role(role_name: str) -> str:
    """提示用户创建角色 Agent"""
    return f"""角色 **{role_name}** 不存在，需要创建。

请在 Claude Code 中运行：
```
/agents → Create new agent → {role_name}
```

或者我可以帮你创建一个模板，确认吗？"""


# ==================== 复杂任务编排 ====================

def coordinate_complex_task(user_input: str, vault_path: str, skip_confirm: bool = False) -> str:
    """
    协调多 Agent 完成复杂任务
    """
    # 默认需要的角色
    required_roles = ['architect', 'reviewer', 'facilitator']

    # 检查缺失的角色
    missing = get_missing_roles(required_roles, vault_path)

    if missing:
        # 返回缺失提示，让用户确认
        status_lines = []
        for role in required_roles:
            if role not in missing:
                status_lines.append(f"- {role}: 已存在")
            else:
                status_lines.append(f"- {role}: 不存在，需要创建")

        return f"""我理解你的需求：{user_input}

这是一个复杂任务，我建议启动多 Agent 讨论：

**需要的角色：**
- Architect（架构师）：画框架、给选项
- Reviewer（批判者）：挑战假设、找漏洞
- Facilitator（主持人）：总结共识

**当前状态：**
{chr(10).join(status_lines)}

**请先创建缺失的角色：**
运行 `/agents` → Create new agent → <角色名>

创建完成后，我们可以继续。"""

    # 用户确认（除非跳过）
    if not skip_confirm:
        confirm_prompt = f"""我理解你的需求：{user_input}

这是一个复杂任务，我建议启动多 Agent 讨论：

**需要的角色：**
- Architect（架构师）：画框架、给选项
- Reviewer（批判者）：挑战假设、找漏洞
- Facilitator（主持人）：总结共识

**执行后会：**
1. Architect 先分析并输出框架
2. Reviewer 挑战 Architect 的观点
3. Facilitator 汇总共识并给出建议

确认启动？（回复"是"或"确认"继续）"""
        return confirm_prompt

    # 多 Agent 编排流程
    print("启动多 Agent 讨论...")

    # 1. Architect 先输出框架
    print("Architect 正在分析...")
    architect_system = get_role_system_prompt('architect')
    architect_output = call_llm(
        prompt=f"请从架构师视角分析以下问题，给出结构化的框架和多个选项：\n\n{user_input}",
        system=architect_system
    )

    # 2. Reviewer 挑战 Architect 的观点
    print("Reviewer 正在挑战...")
    reviewer_system = get_role_system_prompt('reviewer')
    reviewer_output = call_llm(
        prompt=f"以下是 Architect 的观点，请挑战其中的假设，找出漏洞和风险：\n\n{architect_output}",
        system=reviewer_system
    )

    # 3. Facilitator 汇总共识
    print("Facilitator 正在汇总...")
    facilitator_system = get_role_system_prompt('facilitator')
    facilitator_output = call_llm(
        prompt=f"""请汇总以下讨论并提炼共识：

Architect 观点：
{architect_output}

Reviewer 挑战：
{reviewer_output}

请输出：
1. 各方观点摘要
2. 共识
3. 分歧
4. 建议用户下一步做什么""",
        system=facilitator_system
    )

    # 输出完整报告
    report = f"""# 多 Agent 讨论报告

## 用户问题
{user_input}

---

## Architect（架构师）观点
{architect_output}

---

## Reviewer（批判者）挑战
{reviewer_output}

---

## Facilitator（主持人）总结
{facilitator_output}

---

*报告由 Patti Agent 生成，{datetime.now().strftime('%Y-%m-%d %H:%M')}*"""

    return report


# ==================== 入口 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Patti - MindPalace 管家 Agent')
    parser.add_argument('--vault', '-v', type=str, default=DEFAULT_VAULT, help='Vault 路径')
    parser.add_argument('--action', '-a', type=str, required=True,
                        choices=['classify', 'run', 'coordinate'],
                        help='执行动作')
    parser.add_argument('--input', '-i', type=str, help='用户输入')
    parser.add_argument('--confirm', '-c', type=bool, default=False, help='是否已确认执行')

    args = parser.parse_args()

    vault = args.vault or DEFAULT_VAULT
    if not vault:
        print("错误：请设置 OBSIDIAN_VAULT 环境变量或传入 --vault 参数")
        sys.exit(1)

    if args.action == 'classify':
        if not args.input:
            print("错误：--input 是必需的")
            sys.exit(1)

        intent, context = classify_intent(args.input, vault)
        print(f"意图：{intent}")
        print(f"上下文：{context}")

    elif args.action == 'run':
        if not args.input:
            print("错误：--input 是必需的")
            sys.exit(1)

        intent, context = classify_intent(args.input, vault)

        if intent == '日记':
            result = run_portal(context['input'], vault)
            print(result)
        elif intent == '学习-load':
            result = run_learning('load', context['project'], vault)
            print(result)
        elif intent == '学习-new':
            if context['project']:
                result = create_learning_project(context['project'], vault)
                print(result)
                # 自动加载项目
                print("\n---\n")
                result = run_learning('load', context['project'], vault)
                print(result)
            else:
                print("请指定要学习的项目名称，例如：学习 机器学习")
        elif intent == '炼金':
            result = run_alchemy(vault)
            print(result)
        elif intent == '复盘':
            result = run_review(vault)
            print(result)
        elif intent == '复杂任务':
            # 第一次调用时先确认，用户确认后再执行
            result = coordinate_complex_task(args.input, vault, skip_confirm=False)
            print(result)
            # 如果返回的是确认提示，告知用户如何确认
            if '确认启动' in result:
                print('\n→ 请回复"确认"或"是"以启动多 Agent 讨论')
        else:
            print(f"未知意图：{intent}")
            print("请换一种说法，例如：")
            print("  - 记下来：...")
            print("  - 学习 XXX")
            print("  - 帮我分析 XXX")

    elif args.action == 'coordinate':
        if not args.input:
            print("错误：--input 是必需的")
            sys.exit(1)

        # 检查是否已经确认
        confirmed = args.confirm or False
        result = coordinate_complex_task(args.input, vault, skip_confirm=confirmed)
        print(result)


if __name__ == '__main__':
    main()
