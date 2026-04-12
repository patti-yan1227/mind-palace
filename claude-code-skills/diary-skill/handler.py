#!/usr/bin/env python3
"""
记忆宫殿日记 Skill - Claude Code 版本
"""

import sys
import os
from pathlib import Path

# 添加到路径，以便导入 agents
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.portal_agent import execute, archive_to_raw

__all__ = ['execute', 'archive_to_raw']
