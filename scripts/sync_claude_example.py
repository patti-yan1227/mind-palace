"""
sync_claude_example.py

每次 git commit 前由 pre-commit hook 自动调用。
把 CLAUDE.md 中的 Windows 绝对路径替换为 YOUR_VAULT_PATH，
写入 CLAUDE.md.example，供公开仓库使用。

安装 hook（新机器首次配置）：
    cp scripts/sync_claude_example.py .  # 已在项目根目录
    echo '#!/bin/sh\npython scripts/sync_claude_example.py && git add CLAUDE.md.example' > .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
"""
import re
from pathlib import Path


def sync():
    src = Path('CLAUDE.md')
    dst = Path('CLAUDE.md.example')

    if not src.exists():
        print("CLAUDE.md not found, skipping sync")
        return

    content = src.read_text(encoding='utf-8')

    # 替换 Windows 绝对路径：X:\Users\xxx\... 直到空白符或引号
    sanitized = re.sub(r'[A-Za-z]:\\Users\\[^\s"\']+', 'YOUR_VAULT_PATH', content)

    dst.write_text(sanitized, encoding='utf-8')
    print(f"CLAUDE.md.example synced ({len(sanitized)} chars)")


if __name__ == '__main__':
    sync()
