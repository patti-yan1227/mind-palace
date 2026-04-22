#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记忆宫殿复盘 Agent

职责：每周日启动，进行一场高质量的"合伙人 1v1"战略复盘。

设计原则：
  - Agent 只负责数据 I/O，对话流程由 Claude Code 主导
  - 三步流程：scan → 对话(Claude) → update_persona + close_review

Actions:
  scan            扫描本周（或全部历史）内容，输出8雷达发现
  update_persona  写入 Persona Engine 指定维度（用户确认后调用）
  close_review    写入复盘日志到 _log/

5 个复盘板块：
  1. AI 摊牌（scan）
  2. 本周得失（GRAI 框架，对话在 Claude Code）
  3. 能量与状态（对话在 Claude Code）
  4. Persona 更新（update_persona × 4 维度）
  5. 下周聚焦（update_persona --dimension D_trajectory）

核心约束：_persona/ 只有用户明确确认后才能写入。
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Windows 下强制 stdout 使用 UTF-8，避免 GBK 编码错误
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()

# ==================== 配置 ====================

DEFAULT_VAULT = os.getenv('OBSIDIAN_VAULT', '')

DIARY_DIR = '日记'
PROJECTS_DIRS = ['学习', '项目']
PRIVATE_SOURCES_DIR = '_private_sources'
SOCIAL_GRAPH_LOG_DIR = '_social_graph/log'
BIOMETRICS_LOG_DIR = '_biometrics/log'
LOG_DIR = '_log'
PERSONA_DIR = '_persona'

LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-6')
LLM_API_BASE_URL = os.getenv('LLM_API_BASE_URL', 'https://api.anthropic.com')
USE_LLM = os.getenv('REVIEW_USE_LLM', 'true').lower() == 'true'

VALID_DIMENSIONS = {'A_core', 'B_filter', 'C_domain', 'D_trajectory'}

DIM_LABELS = {
    'A_core': '底层心智模型（Core Persona）',
    'B_filter': '认知与偏好过滤器（Cognitive Filter）',
    'C_domain': '专业知识版图（Domain Map）',
    'D_trajectory': '动态轨迹与未竟之事（Trajectory）',
}


# ==================== LLM 工具 ====================

def llm_generate(prompt: str, system: str = None) -> str:
    """调用 LLM（支持 Anthropic 兼容接口）"""
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
        parts = []
        for block in response.content:
            if getattr(block, 'type', None) == 'thinking':
                continue
            elif getattr(block, 'type', None) == 'text':
                parts.append(block.text)
            elif hasattr(block, 'text'):
                parts.append(block.text)
        return ''.join(parts)
    except ImportError:
        raise ImportError("请安装 anthropic SDK: pip install anthropic")
    except Exception as e:
        raise RuntimeError(f"LLM 调用失败：{e}")


# ==================== 工具函数 ====================

def _get_vault(vault_path: str = None) -> Path:
    v = vault_path or DEFAULT_VAULT
    if not v:
        raise ValueError("未指定 vault 路径")
    return Path(v)


def _now_str() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _week_range(weeks_ago: int = 0) -> tuple[str, str]:
    """返回指定周的起止日期（周一到周日）"""
    today = datetime.now().date()
    this_monday = today - timedelta(days=today.weekday())
    target_monday = this_monday - timedelta(weeks=weeks_ago)
    target_sunday = target_monday + timedelta(days=6)
    return target_monday.strftime('%Y-%m-%d'), target_sunday.strftime('%Y-%m-%d')


def _is_in_range(date_str: str, start: str, end: str) -> bool:
    return start <= date_str <= end


def _is_first_run(vault: Path) -> bool:
    """检测是否是首次复盘（_persona/A_core.md 内容含首次初始化占位符）"""
    a_core = vault / PERSONA_DIR / 'A_core.md'
    if not a_core.exists():
        return True
    content = a_core.read_text(encoding='utf-8')
    return '待首次复盘填写' in content


# ==================== Step 1: 扫描内容 ====================

SCAN_PROMPT = """
你是用户的"合伙人 AI"，正在主持每周战略复盘的第一步——AI 摊牌。
请扫描以下内容，用 8 个雷达同时识别有价值的信号，呈现发现，不作评判。

## 扫描内容

### 日记
{diaries}

### 学习笔记（新增/修改）
{notes}

### 未解问题（新增/修改）
{questions}

### 人际互动
{social}

### 体征数据
{biometrics}

### 外界素材
{sources}

## 当前 Persona Engine（对比用）
{persona}

---

## 10 个扫描雷达

**高价值内容雷达（4 类）：**
- [本质理解] 对事物本质的新认知（"原来 X 的底层逻辑是..."）
- [跨域模式] 跨领域的通用规律（"这和 Y 领域的 Z 很像..."）
- [决策背景] 重要决策的原因与背景（"我选择 X 因为..."）
- [价值观碰撞] 价值观矛盾与反思（"我发现我之前的想法有点问题..."）

**Persona 更新雷达（4 类）：**
- [A_core] 底层心智/价值观/长期目标的变化信号
- [B_filter] 审美/品味/认知偏好的变化信号
- [C_domain] 专业技能/领域认知的新增或更新
- [D_trajectory] 当前优先级/焦虑点/未竟之事的变化

**心理考古雷达（2 类）：**
- [反向信号] 用户频繁提到但回避解决的问题？频繁自我否定的具体领域？（"技术差"/"啥也做不到"/"还算满意"等克制表述 = 核心信念障碍的信号）
- [归因模式] 用户如何解释失败和成功？是否把组织/时机/系统问题内化为"我不行"？（过度自责 = A_core 层面待修正信念）

**注意：** 若扫描内容包含 AI 对话记录（"外界素材"中的长文），请重点提取：
1. 对话中用户的自我评价如何随对话演进
2. 对话最终得出的核心结论句（如"你不缺X，你缺的是Y"这类定义句）
3. 用户表示认同/感动的洞察（这些是已验证的深层信念）

---

## 输出格式（直接输出 Markdown，不加代码块）

## 本周扫描发现

### 高价值内容

（每条格式：`[类型] 简短描述 — 来源引用`，没有则写"本期未发现"）

### Persona 候选更新

（每条格式：`[A_core/B_filter/C_domain/D_trajectory] 变化描述 — 与现有 Persona 的关系（新增/冲突/强化）`，没有则写"本期未发现"）

### 值得深挖的矛盾

（列出 1-3 对具体矛盾——用户在不同来源说了相反的事。格式：
`"[来源A] 的 '...' vs [来源B] 的 '...'——这个矛盾揭示了什么？"`
没有则写"本期未发现"）

### 值得深聊的张力

（列出 1-3 个看似矛盾或需要深入讨论的发现，用疑问句引导，没有则写"暂无明显张力"）
"""


def scan_week(vault: Path, start_date: str, end_date: str) -> dict:
    """扫描指定时间范围内的所有内容，返回结构化数据"""
    data = {
        'diaries': [],
        'notes': [],
        'questions': [],
        'social': [],
        'biometrics': [],
        'sources': [],
    }

    # 日记
    diary_dir = vault / DIARY_DIR
    if diary_dir.exists():
        for f in sorted(diary_dir.glob('*.md')):
            if _is_in_range(f.stem, start_date, end_date):
                data['diaries'].append({
                    'date': f.stem,
                    'content': f.read_text(encoding='utf-8')
                })

    # 学习笔记 & 问题
    for proj_dir_name in PROJECTS_DIRS:
        projects_dir = vault / proj_dir_name
        if not projects_dir.exists():
            continue
        for proj in projects_dir.iterdir():
            if not proj.is_dir():
                continue
            notes_dir = proj / 'notes'
            if notes_dir.exists():
                for note in notes_dir.glob('*.md'):
                    mtime = datetime.fromtimestamp(note.stat().st_mtime).strftime('%Y-%m-%d')
                    if _is_in_range(mtime, start_date, end_date):
                        data['notes'].append({
                            'project': proj.name,
                            'file': note.name,
                            'content': note.read_text(encoding='utf-8')[:1000]
                        })
            questions_file = proj / 'questions.md'
            if questions_file.exists():
                mtime = datetime.fromtimestamp(questions_file.stat().st_mtime).strftime('%Y-%m-%d')
                if _is_in_range(mtime, start_date, end_date):
                    data['questions'].append({
                        'project': proj.name,
                        'content': questions_file.read_text(encoding='utf-8')[:500]
                    })

    # 人际互动
    social_dir = vault / SOCIAL_GRAPH_LOG_DIR
    if social_dir.exists():
        for f in sorted(social_dir.glob('*.md')):
            if _is_in_range(f.stem, start_date, end_date):
                data['social'].append(f.read_text(encoding='utf-8'))

    # 体征数据
    bio_dir = vault / BIOMETRICS_LOG_DIR
    if bio_dir.exists():
        for f in sorted(bio_dir.glob('*.md')):
            if _is_in_range(f.stem, start_date, end_date):
                data['biometrics'].append(f.read_text(encoding='utf-8'))

    # 外界素材
    sources_dir = vault / PRIVATE_SOURCES_DIR
    if sources_dir.exists():
        for proj in sources_dir.iterdir():
            if not proj.is_dir():
                continue
            for f in proj.rglob('*.md'):
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d')
                if _is_in_range(mtime, start_date, end_date):
                    data['sources'].append({
                        'project': proj.name,
                        'file': f.name,
                        'content': f.read_text(encoding='utf-8')
                    })

    return data


def load_persona(vault: Path) -> dict:
    """读取现有 Persona Engine 四个维度"""
    persona_dir = vault / PERSONA_DIR
    persona = {}
    for dim in VALID_DIMENSIONS:
        f = persona_dir / f"{dim}.md"
        persona[dim] = f.read_text(encoding='utf-8') if f.exists() else "（尚未初始化）"
    return persona


def format_scan_data(data: dict) -> dict:
    """将扫描数据格式化为字符串，供 LLM 使用"""
    def fmt_list(items, key='content'):
        if not items:
            return "（此期间无记录）"
        if isinstance(items[0], dict):
            return '\n\n'.join(
                f"**{i.get('project', i.get('date', ''))} / {i.get('file', '')}**\n{i.get(key, '')}"
                for i in items
            )
        return '\n\n'.join(items)

    return {
        'diaries': '\n\n---\n\n'.join(
            f"### {d['date']}\n{d['content'][:2000]}" for d in data['diaries']
        ) or "（此期间无日记）",
        'notes': fmt_list(data['notes']),
        'questions': fmt_list(data['questions']),
        'social': '\n\n'.join(data['social']) or "（此期间无记录）",
        'biometrics': '\n\n'.join(data['biometrics']) or "（此期间无记录）",
        'sources': fmt_list(data['sources']),
    }


def ai_scan(vault: Path, start_date: str, end_date: str, first_run: bool = False) -> str:
    """执行 AI 扫描，返回扫描结果 Markdown"""
    label = "全量历史" if first_run else "本周"
    print(f"扫描范围：{start_date} ~ {end_date}（{label}）")

    data = scan_week(vault, start_date, end_date)
    persona = load_persona(vault)

    header = ""
    if first_run:
        header = (
            "## [首次运行]\n\n"
            f"> 这是你的第一次复盘，扫描范围：{start_date} 至 {end_date} 的全量历史数据。\n"
            "> 本次生成的 Persona 将作为基准版本（v1.0）。\n\n---\n\n"
        )

    total = sum(len(v) for v in data.values())
    if total == 0:
        return header + f"扫描范围内（{start_date} ~ {end_date}）暂无任何内容记录，请先完善日记和学习笔记。"

    if not USE_LLM:
        return (
            header +
            f"## 本周扫描发现\n\n"
            f"- 日记：{len(data['diaries'])} 篇\n"
            f"- 学习笔记：{len(data['notes'])} 条\n"
            f"- 未解问题：{len(data['questions'])} 个项目有更新\n"
            f"- 人际互动：{len(data['social'])} 天有记录\n"
            f"- 体征数据：{len(data['biometrics'])} 天有记录\n"
            f"- 外界素材：{len(data['sources'])} 条\n\n"
            f"（REVIEW_USE_LLM=false，跳过 AI 分析）\n"
        )

    formatted = format_scan_data(data)
    persona_str = '\n\n'.join(f"**{k}**\n{v}" for k, v in persona.items())

    prompt = SCAN_PROMPT.format(
        diaries=formatted['diaries'],
        notes=formatted['notes'],
        questions=formatted['questions'],
        social=formatted['social'],
        biometrics=formatted['biometrics'],
        sources=formatted['sources'],
        persona=persona_str,
    )

    return header + llm_generate(prompt)


# ==================== Step 3: Merge to Master ====================

def write_persona_dimension(vault: Path, dimension: str, content: str, source_ref: str = None) -> str:
    """
    将内容写入 Persona Engine 指定维度文件。
    dimension: 'A_core' | 'B_filter' | 'C_domain' | 'D_trajectory'
    返回：文件路径（相对于 vault）
    """
    if dimension not in VALID_DIMENSIONS:
        raise ValueError(f"无效维度：{dimension}，有效值：{VALID_DIMENSIONS}")

    persona_dir = vault / PERSONA_DIR
    persona_dir.mkdir(parents=True, exist_ok=True)

    dim_file = persona_dir / f"{dimension}.md"

    timestamp = _now_str()
    backlink = f"\n> 来源：{source_ref}" if source_ref else ""
    update_block = f"\n\n---\n\n<!-- 更新于 {timestamp}{backlink} -->\n\n{content}"

    if dim_file.exists():
        existing = dim_file.read_text(encoding='utf-8')
        dim_file.write_text(existing + update_block, encoding='utf-8')
    else:
        header = (
            f"# {DIM_LABELS[dimension]}\n\n"
            f"> 首次初始化：{timestamp}\n"
            f"> 维护者：复盘 Agent（每周日人机共决）\n\n---"
        )
        dim_file.write_text(header + update_block, encoding='utf-8')

    return str(dim_file.relative_to(vault))


# ==================== close_review ====================

def close_review(vault: Path, weeks_ago: int = 0) -> str:
    """
    写入复盘日志到 _log/review_YYYY-MM-DD.md。
    统计各维度本次复盘后的更新条数（通过计数 <!-- 更新于 实现）。
    """
    start_date, end_date = _week_range(weeks_ago)
    today = datetime.now().strftime('%Y-%m-%d')
    timestamp = _now_str()

    # 统计各维度更新条数
    persona_dir = vault / PERSONA_DIR
    dim_counts = {}
    for dim in VALID_DIMENSIONS:
        f = persona_dir / f"{dim}.md"
        if f.exists():
            content = f.read_text(encoding='utf-8')
            dim_counts[dim] = content.count('<!-- 更新于')
        else:
            dim_counts[dim] = 0

    log_content = (
        f"# 复盘日志 — {today}\n\n"
        f"> 完成时间：{timestamp}\n"
        f"> 扫描范围：{start_date} ~ {end_date}\n\n"
        f"## Persona Engine 更新摘要\n\n"
        f"| 维度 | 累计更新条数 |\n"
        f"|------|-----------|\n"
    )
    for dim, count in sorted(dim_counts.items()):
        log_content += f"| {dim} ({DIM_LABELS[dim]}) | {count} |\n"

    log_content += f"\n## 状态\n\n复盘已完成。\n"

    log_dir = vault / LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"review_{today}.md"
    log_file.write_text(log_content, encoding='utf-8')

    return str(log_file.relative_to(vault))


# ==================== CLI ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='记忆宫殿复盘 Agent')
    parser.add_argument('--vault', '-v', type=str, default=DEFAULT_VAULT, help='Vault 路径')
    parser.add_argument('--action', '-a', type=str, required=True,
                        choices=['scan', 'update_persona', 'close_review'],
                        help=(
                            'scan=扫描内容并输出8雷达发现；'
                            'update_persona=写入Persona维度（需 --dimension --input）；'
                            'close_review=写入复盘日志'
                        ))
    parser.add_argument('--weeks-ago', type=int, default=0, help='复盘几周前（0=本周，1=上周）')
    # scan 专用
    parser.add_argument('--first-run', action='store_true',
                        help='首次运行：扫描全部历史数据（配合 --start-date 使用）')
    parser.add_argument('--start-date', type=str, default=None,
                        help='首次运行的起始日期，格式 YYYY-MM-DD')
    # update_persona 专用
    parser.add_argument('--dimension', type=str, default=None,
                        choices=list(VALID_DIMENSIONS),
                        help='Persona 维度：A_core / B_filter / C_domain / D_trajectory')
    parser.add_argument('--input', dest='input_content', type=str, default=None,
                        help='写入内容')
    parser.add_argument('--source-ref', type=str, default=None,
                        help='来源引用（溯源 backlink）')
    parser.add_argument('--json', dest='output_json', action='store_true', help='JSON 格式输出')
    args = parser.parse_args()

    vault_path = args.vault or DEFAULT_VAULT
    vault = _get_vault(vault_path)

    if args.action == 'scan':
        if args.first_run:
            # 首次运行：扫描全量历史
            start_date = args.start_date or '2000-01-01'
            end_date = datetime.now().strftime('%Y-%m-%d')
            # 自动检测并提示
            if _is_first_run(vault):
                print(f"[首次运行检测] _persona/ 尚未初始化，将扫描全量历史数据（{start_date} 至今）。\n")
            result = ai_scan(vault, start_date, end_date, first_run=True)
        else:
            start_date, end_date = _week_range(args.weeks_ago)
            # 自动检测首次运行
            if _is_first_run(vault):
                print("[提示] 检测到 _persona/ 尚未初始化。建议使用 --first-run 扫描全量历史数据。\n")
            result = ai_scan(vault, start_date, end_date, first_run=False)
        print(result)

    elif args.action == 'update_persona':
        if not args.dimension:
            print("错误：update_persona 需要 --dimension 参数", file=sys.stderr)
            print(f"可选值：{', '.join(sorted(VALID_DIMENSIONS))}", file=sys.stderr)
            sys.exit(1)
        if not args.input_content:
            print("错误：update_persona 需要 --input 参数", file=sys.stderr)
            sys.exit(1)
        # 格式检查：input 应包含 ### 标题结构
        if '### ' not in args.input_content:
            print("[格式警告] --input 缺少 ### 标题结构，请按规范格式传入：", file=sys.stderr)
            print("  ### [洞察名称]", file=sys.stderr)
            print("  > 来源：[日期·板块]", file=sys.stderr)
            print("  **一句话：** [核心结论]", file=sys.stderr)
            print("  - 要点", file=sys.stderr)
        path = write_persona_dimension(vault, args.dimension, args.input_content, args.source_ref)
        result = {'dimension': args.dimension, 'path': path, 'status': 'ok'}
        if args.output_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"[ok] 已写入 {path}")

    elif args.action == 'close_review':
        path = close_review(vault, args.weeks_ago)
        result = {'log_path': path, 'status': 'ok'}
        if args.output_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"[ok] 复盘日志已写入 {path}")


if __name__ == '__main__':
    main()
