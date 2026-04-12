#!/usr/bin/env python3
"""
Learning Skill Handler — Claude Code 版本

供 CLAUDE.md 行为指令使用的辅助函数封装。
可直接 import，也可作为 CLI 使用。
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'agents'))
from learning_agent import (
    check_and_notify,
    check_and_close_stale_session,
    recommend_next,
    load_context,
    initialize_project,
    search_existing,
    open_session,
    close_session,
    save_note,
    save_dialogue,
    append_question,
    mark_question_resolved,
    import_highlights,
    record_session,
)

DEFAULT_VAULT = os.getenv('OBSIDIAN_VAULT', '')


def handle_startup_check(vault_path: str = None) -> str:
    """
    每次对话启动时调用。
    关闭超时 session + 返回待处理提醒（空字符串 = 无提醒）。
    """
    vault = vault_path or DEFAULT_VAULT
    check_and_close_stale_session(vault)
    return check_and_notify(vault)


def handle_learn_command(user_input: str = '', vault_path: str = None) -> dict:
    """
    /学习 命令主入口。
    返回：{recommendations, prompt_for_user}
    """
    vault = vault_path or DEFAULT_VAULT
    recs = recommend_next(vault)

    if not recs:
        prompt = "你还没有任何学习项目。告诉我你想学什么，我来帮你初始化一个项目。"
    else:
        lines = ["你可以继续这些项目：\n"]
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. **{r['name']}** — {r['reason']} | 建议模式：{r['mode_hint']}")
        lines.append("\n或者告诉我你想学的新话题 / 带着具体问题来探索。")
        prompt = '\n'.join(lines)

    return {'recommendations': recs, 'prompt': prompt}


if __name__ == '__main__':
    # 简单测试入口
    vault = os.getenv('OBSIDIAN_VAULT', '')
    if not vault:
        print("请设置 OBSIDIAN_VAULT 环境变量")
        sys.exit(1)

    print("=== 启动检查 ===")
    notify = handle_startup_check(vault)
    if notify:
        print(notify)
    else:
        print("无待处理提醒")

    print("\n=== 推荐项目 ===")
    result = handle_learn_command(vault_path=vault)
    print(result['prompt'])
