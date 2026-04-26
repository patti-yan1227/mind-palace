#!/usr/bin/env python3
"""
学习 Skill 入口 — 专用学习对话窗口
"""

import subprocess
import os
import sys


def execute(input_text: str, context: dict) -> str:
    vault = context.get("OBSIDIAN_VAULT", os.getenv("OBSIDIAN_VAULT", ""))
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(skill_dir))

    text = input_text.strip()

    if text.startswith("搜索 "):
        query = text[3:].strip()
        cmd = [sys.executable, "agents/learning_agent.py",
               "--action", "search", "--query", query, "--vault", vault]
    elif text.startswith("学习 "):
        project = text[3:].strip()
        cmd = [sys.executable, "agents/learning_agent.py",
               "--action", "load", "--project", project, "--vault", vault]
    else:
        cmd = [sys.executable, "agents/learning_agent.py",
               "--action", "recommend", "--vault", vault]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, timeout=120)
    output = (result.stdout or result.stderr or "完成").strip()
    return output[-800:]


__all__ = ['execute']
