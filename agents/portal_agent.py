#!/usr/bin/env python3
"""
记忆宫殿门房 Portal Agent

职责：
1. 接收所有原始输入
2. 原封不动 append 到 _raw_inbox/{date}.md
3. 添加时间戳 [HH:MM]
4. 广播到消息总线
"""

import os
from datetime import datetime
from pathlib import Path


# ==================== 配置 ====================

DEFAULT_VAULT = os.getenv('OBSIDIAN_VAULT', '')
RAW_INBOX_DIR = os.getenv('RAW_INBOX_DIR', '_raw_inbox')


# ==================== 核心函数 ====================

def archive_to_raw(message: str, vault_path: str = None, timestamp: str = None):
    """
    将消息归档到 _raw_inbox

    Args:
        message: 原始消息内容（原封不动）
        vault_path: Obsidian Vault 路径
        timestamp: 时间戳（默认当前时间）

    Returns:
        dict: 归档结果
    """
    vault = Path(vault_path or DEFAULT_VAULT)
    raw_dir = vault / RAW_INBOX_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 生成分块文件名（按小时分块，防止 Token 爆炸）
    now = datetime.now()
    if timestamp is None:
        timestamp = now.strftime('%H:%M')
    date = now.strftime('%Y-%m-%d')
    hour = now.strftime('%H')

    # 分块策略：_raw_inbox/2026-04-09-14.md
    filename = f"{date}-{hour}.md"
    filepath = raw_dir / filename

    # 追加写入
    with open(filepath, 'a', encoding='utf-8') as f:
        # 如果是新文件，添加日期标题
        if filepath.stat().st_size == 0:
            f.write(f"## {date}\n\n")

        # 追加消息
        f.write(f"[{timestamp}] {message}\n")

    return {
        'success': True,
        'filepath': str(filepath),
        'message': f"已归档到 {filepath}"
    }


def execute(input_text: str, context: dict = None):
    """
    OpenClaw Skill 执行入口

    Args:
        input_text: 用户输入
        context: 上下文（含 vault 路径等）

    Returns:
        dict: 执行结果
    """
    vault = context.get('vault', DEFAULT_VAULT) if context else DEFAULT_VAULT
    result = archive_to_raw(input_text, vault)
    return {'text': result['message'], 'data': result}


# ==================== 命令行入口 ====================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='记忆宫殿门房 Portal')
    parser.add_argument('--input', '-i', type=str, required=True, help='消息内容')
    parser.add_argument('--vault', '-v', type=str, default=DEFAULT_VAULT, help='Vault 路径')
    args = parser.parse_args()

    result = execute(args.input, {'vault': args.vault})
    print(result['text'])


if __name__ == "__main__":
    main()
