#!/usr/bin/env python3
"""
记忆宫殿复盘 Agent

职责：每周日启动，进行一场高质量的"合伙人 1v1"战略复盘。

三步流程：
  Step 1 — AI 摊牌：扫描本周全量内容（8 雷达），呈现线索
  Step 2 — 人类在环：对话式 Socratic questioning，用户咀嚼顿悟
  Step 3 — Merge to Master：用户确认后写入 _persona/ + 溯源 backlink

5 个复盘板块：
  1. AI 摊牌（本周扫描发现）
  2. 本周得失（GRAI 框架）
  3. 能量与状态
  4. Persona 更新（四维度）
  5. 下周聚焦（Stop/Start/Continue）

核心约束：_persona/ 只有用户明确确认后才能写入。
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ==================== 配置 ====================

DEFAULT_VAULT = os.getenv('OBSIDIAN_VAULT', '')

DIARY_DIR = '日记'
PROJECTS_DIR = '项目'
PRIVATE_SOURCES_DIR = '_private_sources'
SOCIAL_GRAPH_LOG_DIR = '_social_graph/log'
BIOMETRICS_LOG_DIR = '_biometrics/log'
LOG_DIR = '_log'
PERSONA_DIR = '_persona'

LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-6')
LLM_API_BASE_URL = os.getenv('LLM_API_BASE_URL', 'https://api.anthropic.com')
USE_LLM = os.getenv('REVIEW_USE_LLM', 'true').lower() == 'true'


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
    # 本周周一
    this_monday = today - timedelta(days=today.weekday())
    # 目标周
    target_monday = this_monday - timedelta(weeks=weeks_ago)
    target_sunday = target_monday + timedelta(days=6)
    return target_monday.strftime('%Y-%m-%d'), target_sunday.strftime('%Y-%m-%d')


def _is_in_range(date_str: str, start: str, end: str) -> bool:
    return start <= date_str <= end


# ==================== Step 1: 扫描本周内容 ====================

SCAN_PROMPT = """
你是一位具有战略眼光的个人成长顾问。请扫描以下本周内容，用 8 个雷达同时识别有价值的信号。

## 本周内容

### 日记
{diaries}

### 学习笔记（新增）
{notes}

### 未解问题（新增）
{questions}

### 人际互动
{social}

### 体征数据
{biometrics}

### 外界素材
{sources}

## 当前 Persona Engine
{persona}

---

## 8 个扫描雷达

**高价值内容雷达（4 类）：**
- [本质理解] 对事物本质的新认知
- [跨域模式] 跨领域的通用规律
- [决策背景] 重要决策的原因与背景
- [价值观碰撞] 价值观矛盾与反思

**Persona 更新雷达（4 类）：**
- [A变化] 底层心智/价值观/长期目标的变化信号
- [B变化] 审美/品味/认知偏好的变化信号
- [C变化] 专业技能/领域认知的新增或更新
- [D变化] 当前优先级/焦虑点/未竟之事的变化

---

## 输出格式（直接输出 Markdown，不加代码块）

## 本周扫描发现

### 高价值内容

（每条格式：`[类型] 简短描述 — 来源引用`，没有则写"本周未发现"）

### Persona 候选更新

（每条格式：`[维度] 变化描述 — 与现有 Persona 的关系（新增/冲突/强化）`，没有则写"本周未发现"）

### 值得深聊的张力

（列出 1-3 个看似矛盾或需要深入讨论的发现，用疑问句引导，没有则写"暂无明显张力"）
"""


def scan_week(vault: Path, start_date: str, end_date: str) -> dict:
    """扫描本周所有内容，返回结构化数据"""
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

    # 学习笔记 & 问题（按修改时间过滤）
    projects_dir = vault / PROJECTS_DIR
    if projects_dir.exists():
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
                        'content': f.read_text(encoding='utf-8')[:500]
                    })

    return data


def load_persona(vault: Path) -> dict:
    """读取现有 Persona Engine 四个维度"""
    persona_dir = vault / PERSONA_DIR
    persona = {}
    for dim in ['A_core', 'B_filter', 'C_domain', 'D_trajectory']:
        f = persona_dir / f"{dim}.md"
        persona[dim] = f.read_text(encoding='utf-8') if f.exists() else "（尚未初始化）"
    return persona


def format_scan_data(data: dict) -> dict:
    """将扫描数据格式化为字符串，供 LLM 使用"""
    def fmt_list(items, key='content'):
        if not items:
            return "（本周无记录）"
        if isinstance(items[0], dict):
            return '\n\n'.join(f"**{i.get('project', i.get('date', ''))} / {i.get('file', '')}**\n{i.get(key, '')}" for i in items)
        return '\n\n'.join(items)

    return {
        'diaries': '\n\n---\n\n'.join(
            f"### {d['date']}\n{d['content'][:2000]}" for d in data['diaries']
        ) or "（本周无日记）",
        'notes': fmt_list(data['notes']),
        'questions': fmt_list(data['questions']),
        'social': '\n\n'.join(data['social']) or "（本周无记录）",
        'biometrics': '\n\n'.join(data['biometrics']) or "（本周无记录）",
        'sources': fmt_list(data['sources']),
    }


def ai_scan(vault: Path, start_date: str, end_date: str) -> str:
    """执行 AI 扫描，返回扫描结果 Markdown"""
    print(f"扫描范围：{start_date} ~ {end_date}")
    data = scan_week(vault, start_date, end_date)
    persona = load_persona(vault)

    total = sum(len(v) for v in data.values())
    if total == 0:
        return "本周无任何内容记录，请先完善日记和学习笔记。"

    if not USE_LLM:
        # 非 LLM 模式：输出统计摘要
        return (
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

    return llm_generate(prompt)


# ==================== Step 3: Merge to Master ====================

def write_persona_dimension(vault: Path, dimension: str, content: str, source_ref: str = None) -> str:
    """
    将内容写入 Persona Engine 指定维度文件。
    dimension: 'A_core' | 'B_filter' | 'C_domain' | 'D_trajectory'
    返回：文件路径
    """
    valid = {'A_core', 'B_filter', 'C_domain', 'D_trajectory'}
    if dimension not in valid:
        raise ValueError(f"无效维度：{dimension}，有效值：{valid}")

    persona_dir = vault / PERSONA_DIR
    persona_dir.mkdir(parents=True, exist_ok=True)

    dim_file = persona_dir / f"{dimension}.md"

    # 追加新内容（带时间戳和溯源）
    timestamp = _now_str()
    backlink = f"\n> 来源：{source_ref}" if source_ref else ""
    update_block = f"\n\n---\n\n<!-- 更新于 {timestamp}{backlink} -->\n\n{content}"

    if dim_file.exists():
        existing = dim_file.read_text(encoding='utf-8')
        dim_file.write_text(existing + update_block, encoding='utf-8')
    else:
        # 初始化文件
        dim_names = {
            'A_core': '底层心智模型（Core Persona）',
            'B_filter': '认知与偏好过滤器（Cognitive Filter）',
            'C_domain': '专业知识版图（Domain Map）',
            'D_trajectory': '动态轨迹与未竟之事（Trajectory）',
        }
        header = f"# {dim_names[dimension]}\n\n> 首次初始化：{timestamp}\n> 维护者：复盘 Agent（每周日人机共决）\n\n---\n"
        dim_file.write_text(header + update_block, encoding='utf-8')

    return str(dim_file.relative_to(vault))


# ==================== 完整复盘流程 ====================

REVIEW_SYSTEM_PROMPT = """你是用户的"合伙人 AI"，正在主持一场每周战略复盘。

你的风格：
- 直接、犀利、有洞察力——不说废话，不给空洞鼓励
- 善用 Socratic questioning——用问题引导用户自己想明白
- 发现矛盾时大方摊牌，但保持尊重
- 每次只聚焦一个话题，不要同时抛出太多问题

你正在按 5 个板块推进复盘：
1. AI 摊牌（已完成扫描）
2. 本周得失（GRAI）
3. 能量与状态
4. Persona 更新
5. 下周聚焦

记住：你是引导者，不是报告机器。"""


def run_review_session(vault_path: str = None, weeks_ago: int = 0, non_interactive: bool = False) -> dict:
    """
    启动复盘 session。

    non_interactive=True 时只执行扫描并返回结果（适合测试）。
    """
    vault = _get_vault(vault_path)
    start_date, end_date = _week_range(weeks_ago)

    print(f"\n{'='*60}")
    print(f"  记忆宫殿 · 周复盘 Agent")
    print(f"  扫描周期：{start_date} ~ {end_date}")
    print(f"{'='*60}\n")

    results = {'start_date': start_date, 'end_date': end_date, 'persona_updates': []}

    # ---- 板块 1: AI 摊牌 ----
    print("【板块 1 — AI 摊牌】正在扫描本周内容...\n")
    scan_result = ai_scan(vault, start_date, end_date)
    print(scan_result)
    results['scan'] = scan_result

    if non_interactive:
        return results

    print("\n" + "─"*60)
    input("按 Enter 继续进入板块 2（本周得失）...")

    # ---- 板块 2: 本周得失（GRAI）----
    print("\n【板块 2 — 本周得失（GRAI）】\n")
    grai_questions = (
        "我想问你几个关于这周的问题，不用一次性全答，一条一条来：\n\n"
        "**G（Goal）：** 这周开始时你给自己设定了什么目标，或者你期待完成什么？\n"
    )
    print(grai_questions)
    goal = input("你的回答：").strip()

    if goal:
        result_q = "\n**R（Result）：** 实际发生了什么？和预期的差距在哪里？\n"
        print(result_q)
        result = input("你的回答：").strip()

        analysis_q = "\n**A（Analysis）：** 成功或失败，你觉得最关键的因素是什么？\n"
        print(analysis_q)
        analysis = input("你的回答：").strip()

        insight_q = "\n**I（Insight）：** 这背后有什么规律？下次遇到类似情况，你会怎么做不同的事？\n"
        print(insight_q)
        insight = input("你的回答：").strip()

        results['grai'] = {'goal': goal, 'result': result, 'analysis': analysis, 'insight': insight}

    print("\n" + "─"*60)
    input("按 Enter 继续进入板块 3（能量与状态）...")

    # ---- 板块 3: 能量与状态 ----
    print("\n【板块 3 — 能量与状态】\n")
    energy_q = (
        "回顾这周，有没有某个时刻你特别**充电**（做完后精力更足）？\n"
        "反过来，有没有某件事让你特别**耗电**（做完后很空洞）？\n"
    )
    print(energy_q)
    energy = input("你的回答：").strip()
    results['energy'] = energy

    print("\n" + "─"*60)
    input("按 Enter 继续进入板块 4（Persona 更新）...")

    # ---- 板块 4: Persona 更新 ----
    print("\n【板块 4 — Persona 更新】\n")
    print("基于扫描结果，我们逐维度讨论。说"记下来"或"更新"时，我会写入 Persona Engine。\n")

    dim_labels = {
        'A_core': 'A — 底层心智模型',
        'B_filter': 'B — 认知与偏好过滤器',
        'C_domain': 'C — 专业知识版图',
        'D_trajectory': 'D — 动态轨迹',
    }

    for dim, label in dim_labels.items():
        print(f"\n--- {label} ---\n")
        current = load_persona(vault).get(dim, "（尚未初始化）")
        print(f"当前内容摘要：\n{current[:300]}{'...' if len(current) > 300 else ''}\n")
        update_input = input(f"这周有什么要更新到 {label} 的？（直接回答，或按 Enter 跳过）：").strip()

        if update_input and update_input.lower() not in ('n', 'no', '跳过', '没有', '无'):
            source_ref = f"周复盘 {start_date}~{end_date}"
            path = write_persona_dimension(vault, dim, update_input, source_ref)
            print(f"  ✓ 已写入 {path}")
            results['persona_updates'].append({'dimension': dim, 'content': update_input, 'path': path})

    print("\n" + "─"*60)
    input("按 Enter 进入最后一个板块（下周聚焦）...")

    # ---- 板块 5: 下周聚焦 ----
    print("\n【板块 5 — 下周聚焦（Stop / Start / Continue）】\n")
    stop_q = "**Stop：** 下周有什么事情要停下来不再做的（无效的、消耗的）？\n"
    print(stop_q)
    stop = input("你的回答：").strip()

    start_q = "\n**Start：** 下周有什么新的事情要开始尝试的？\n"
    print(start_q)
    start_new = input("你的回答：").strip()

    continue_q = "\n**Continue：** 这周做得好，下周要继续坚持的是什么？\n"
    print(continue_q)
    cont = input("你的回答：").strip()

    focus_q = "\n最后：下周你的 **3 个最高优先级** 是什么？（用 / 分隔）\n"
    print(focus_q)
    focus = input("你的回答：").strip()

    results['next_week'] = {
        'stop': stop, 'start': start_new, 'continue': cont, 'focus': focus
    }

    # 将下周聚焦写入 D_trajectory
    if any([stop, start_new, cont, focus]):
        trajectory_update = (
            f"## 下周计划（{end_date} 复盘）\n\n"
            f"**Stop：** {stop}\n"
            f"**Start：** {start_new}\n"
            f"**Continue：** {cont}\n"
            f"**3 个优先级：** {focus}\n"
        )
        path = write_persona_dimension(vault, 'D_trajectory', trajectory_update, f"周复盘 {start_date}~{end_date}")
        print(f"\n  ✓ 下周计划已写入 {path}")
        results['persona_updates'].append({'dimension': 'D_trajectory', 'content': trajectory_update, 'path': path})

    print(f"\n{'='*60}")
    print("  复盘完成！本次更新摘要：")
    print(f"  - Persona 更新：{len(results['persona_updates'])} 条")
    print(f"{'='*60}\n")

    return results


# ==================== CLI ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='记忆宫殿复盘 Agent')
    parser.add_argument('--vault', '-v', type=str, default=DEFAULT_VAULT, help='Vault 路径')
    parser.add_argument('--action', '-a', type=str, required=True,
                        choices=['run', 'scan'],
                        help='run=完整复盘 session，scan=仅扫描不交互')
    parser.add_argument('--weeks-ago', type=int, default=0, help='复盘几周前（0=本周，1=上周）')
    parser.add_argument('--json', dest='output_json', action='store_true', help='JSON 格式输出')
    args = parser.parse_args()

    vault = args.vault or DEFAULT_VAULT

    if args.action == 'scan':
        vault_path = _get_vault(vault)
        start_date, end_date = _week_range(args.weeks_ago)
        result = ai_scan(vault_path, start_date, end_date)
        print(result)

    elif args.action == 'run':
        results = run_review_session(vault, args.weeks_ago)
        if args.output_json:
            print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
