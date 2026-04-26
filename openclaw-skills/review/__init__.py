#!/usr/bin/env python3
"""
复盘 Skill 入口 — 专用复盘对话窗口
"""

import subprocess
import os
import sys


def execute(input_text: str, context: dict) -> str:
    vault = context.get("OBSIDIAN_VAULT", os.getenv("OBSIDIAN_VAULT", ""))
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(skill_dir))

    result = subprocess.run(
        [sys.executable, "agents/review_agent.py",
         "--action", "scan", "--vault", vault],
        capture_output=True, text=True, cwd=project_root, timeout=300
    )
    output = (result.stdout or result.stderr or "扫描完成").strip()
    return output[-800:]


__all__ = ['execute']
