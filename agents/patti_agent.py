#!/usr/bin/env python3
"""
Patti - MindPalace 管家 Agent

职责：
1. 意图识别 — 听懂用户要什么
2. 任务路由 — 调用对应的 Agent
3. 多 Agent 编排 — 复杂任务时组织多个 Agent 协作
4. 与用户确认 — 复杂任务必须先确认再执行
"""

import os
import re
import subprocess
import sys
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

def coordinate_complex_task(user_input: str, vault_path: str) -> str:
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

    # TODO: 实现多 Agent 调用逻辑
    return "多 Agent 编排功能实现中..."


# ==================== 入口 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Patti - MindPalace 管家 Agent')
    parser.add_argument('--vault', '-v', type=str, default=DEFAULT_VAULT, help='Vault 路径')
    parser.add_argument('--action', '-a', type=str, required=True,
                        choices=['classify', 'run', 'coordinate'],
                        help='执行动作')
    parser.add_argument('--input', '-i', type=str, help='用户输入')

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
            print(f"项目 '{context['project']}' 不存在，要创建吗？")
        elif intent == '炼金':
            result = run_alchemy(vault)
            print(result)
        elif intent == '复盘':
            result = run_review(vault)
            print(result)
        elif intent == '复杂任务':
            result = coordinate_complex_task(args.input, vault)
            print(result)
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

        result = coordinate_complex_task(args.input, vault)
        print(result)


if __name__ == '__main__':
    main()
