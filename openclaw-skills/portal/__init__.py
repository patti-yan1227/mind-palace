#!/usr/bin/env python3
"""
Patti 管家 Skill 入口 — 意图识别 + 路由到对应 Agent
"""

import subprocess
import os
import sys


def execute(input_text: str, context: dict) -> str:
    vault = context.get("OBSIDIAN_VAULT", os.getenv("OBSIDIAN_VAULT", ""))
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(skill_dir))

    result = subprocess.run(
        [sys.executable, "agents/patti_agent.py",
         "--action", "run", "--input", input_text, "--vault", vault],
        capture_output=True, text=True, cwd=project_root, timeout=120
    )
    output = (result.stdout or result.stderr or "已处理").strip()
    return output[-500:]


# 保留 archive_to_raw 供兼容
from agents.portal_agent import archive_to_raw

__all__ = ['execute', 'archive_to_raw']
