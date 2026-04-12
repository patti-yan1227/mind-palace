#!/usr/bin/env python3
"""
记忆宫殿炼金术 Agent

职责：
1. T-1 批处理：每天凌晨 00:00 处理昨日数据
2. 六阶段流水线：
   ① 编纂日记：读取 T-1 _raw_inbox/ → 日记/{date}.md
   ② 萃取金砖：从日记/项目变动提取核心洞察 → 暂存区
   ③ 读取变更报告：从 _log/ 读取昨日学习 session 的变更
   ④ 编译跨域索引：更新 _index.md 和 _compiled/
   ⑤ 记录人际互动：→ _social_graph/log/
   ⑥ 记录体征数据：→ _biometrics/log/
   ⑦ Lint 巡检：→ _lint_report/{date}.md
3. 异常即停：任一阶段异常立刻终止并告警
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ==================== 配置 ====================

DEFAULT_VAULT = os.getenv('OBSIDIAN_VAULT', '')
RAW_INBOX_DIR = '_raw_inbox'
DIARY_DIR = '日记'
COMPILED_DIR = '_compiled'
INDEX_FILE = '_index.md'
LOG_DIR = '_log'
SOCIAL_GRAPH_LOG_DIR = '_social_graph/log'
BIOMETRICS_LOG_DIR = '_biometrics/log'
LINT_REPORT_DIR = '_lint_report'
PROJECTS_DIR = '项目'
PRIVATE_SOURCES_DIR = '_private_sources'


# ==================== 工具函数 ====================

def _get_vault(vault_path: str = None) -> Path:
    v = vault_path or DEFAULT_VAULT
    if not v:
        raise ValueError("未指定 vault 路径，请设置 OBSIDIAN_VAULT 环境变量或传入 --vault 参数")
    return Path(v)


def _now_str() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _yesterday_str() -> str:
    return (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


def _today_str() -> str:
    return datetime.now().strftime('%Y-%m-%d')


# ==================== 阶段 1: 编纂日记 ====================

def compile_diary(date: str, vault_path: str = None) -> str:
    """
    读取指定日期的 _raw_inbox/ 文件，编纂结构化日记
    返回：日记文件路径
    """
    vault = _get_vault(vault_path)
    raw_dir = vault / RAW_INBOX_DIR
    diary_dir = vault / DIARY_DIR

    diary_dir.mkdir(parents=True, exist_ok=True)

    # 读取该日期所有 raw 文件
    raw_files = sorted(raw_dir.glob(f"{date}*.md"))
    if not raw_files:
        return f"日记 {date}: 无原始输入"

    entries = []
    for rf in raw_files:
        content = rf.read_text(encoding='utf-8')
        entries.append(content)

    # 生成结构化日记
    diary_content = f"# {date} 日记\n\n"
    diary_content += f"> 归档时间：{_now_str()}\n"
    diary_content += f"> 原始素材：{len(raw_files)} 条\n\n"
    diary_content += "---\n\n"

    # TODO: 这里可以加 LLM 提炼总结
    diary_content += "## 原始记录\n\n"
    for i, entry in enumerate(entries, 1):
        diary_content += f"### {i}\n\n{entry}\n\n"

    # 写入文件
    diary_file = diary_dir / f"{date}.md"
    diary_file.write_text(diary_content, encoding='utf-8')

    return str(diary_file.relative_to(vault))


# ==================== 阶段 2: 萃取金砖 ====================

def extract_insights(date: str, vault_path: str = None) -> list:
    """
    从日记和项目变动中提取核心洞察（金砖）
    返回：[{concept, summary, source}]
    """
    vault = _get_vault(vault_path)
    diary_dir = vault / DIARY_DIR
    projects_dir = vault / PROJECTS_DIR

    insights = []

    # 读取日记
    diary_file = diary_dir / f"{date}.md"
    if diary_file.exists():
        # TODO: 用 LLM 萃取洞察
        pass

    # 扫描项目 notes/ 的新文件
    if projects_dir.exists():
        for proj in projects_dir.iterdir():
            if not proj.is_dir():
                continue
            notes_dir = proj / 'notes'
            if notes_dir.exists():
                for note in notes_dir.glob('*.md'):
                    mtime = datetime.fromtimestamp(note.stat().st_mtime)
                    if mtime.strftime('%Y-%m-%d') == date:
                        # 新笔记，提取首段作为洞察
                        content = note.read_text(encoding='utf-8')
                        lines = [l for l in content.splitlines() if l.strip() and not l.startswith('#')]
                        summary = lines[0][:200] if lines else ''
                        insights.append({
                            'concept': note.stem,
                            'summary': summary,
                            'source': f'项目/{proj.name}/notes/{note.name}'
                        })

    return insights


# ==================== 阶段 3: 读取变更报告 ====================

def read_change_log(date: str, vault_path: str = None) -> dict:
    """
    从 _log/ 读取指定日期的变更报告
    返回：{projects: [{name, sources, notes, dialogues}]}
    """
    vault = _get_vault(vault_path)
    log_file = vault / LOG_DIR / f"{datetime.now().strftime('%Y-%m')}.md"

    if not log_file.exists():
        return {'projects': []}

    content = log_file.read_text(encoding='utf-8')
    changes = []

    # 简单解析：查找 [date] ingest 条目
    import re
    pattern = rf'## \[{date}\] ingest \| ([^\n]+) 学习 session(.*?)(?=## \[|$)'
    matches = re.findall(pattern, content, re.DOTALL)

    for project_name, section in matches:
        project = {'name': project_name.strip(), 'sources': [], 'notes': [], 'dialogues': []}
        for line in section.splitlines():
            if '新增素材:' in line:
                mode = 'sources'
            elif '新增笔记:' in line:
                mode = 'notes'
            elif '新增对话:' in line:
                mode = 'dialogues'
            elif line.strip().startswith('- `_'):
                path = line.strip().lstrip('- `').rstrip('`')
                project[mode].append(path)
        changes.append(project)

    return {'projects': changes}


# ==================== 阶段 4: 编译跨域索引 ====================

def update_index_md(vault_path: str = None) -> str:
    """
    更新 _index.md 全局知识地图
    返回：文件路径
    """
    vault = _get_vault(vault_path)
    index_file = vault / INDEX_FILE
    projects_dir = vault / PROJECTS_DIR
    compiled_dir = vault / COMPILED_DIR
    diary_dir = vault / DIARY_DIR
    social_log_dir = vault / SOCIAL_GRAPH_LOG_DIR
    biometrics_log_dir = vault / BIOMETRICS_LOG_DIR

    # 收集各部分内容
    index_sections = {
        'diary': [],
        'projects': {},
        'compiled': {'概念': [], '人物': [], '关联': []},
        'social': [],
        'biometrics': [],
        'sources': {},
        'logs': []
    }

    # 日记
    if diary_dir.exists():
        for f in sorted(diary_dir.glob('*.md'), reverse=True)[:30]:
            index_sections['diary'].append({
                'path': f'日记/{f.name}',
                'title': f.stem
            })

    # 项目
    if projects_dir.exists():
        for proj in projects_dir.iterdir():
            if not proj.is_dir():
                continue
            proj_files = []
            # map.md
            map_file = proj / 'map.md'
            if map_file.exists():
                proj_files.append({'path': f'项目/{proj.name}/map.md', 'title': '知识版图'})
            # notes/
            notes_dir = proj / 'notes'
            if notes_dir.exists():
                for note in sorted(notes_dir.glob('*.md')):
                    proj_files.append({'path': f'项目/{proj.name}/notes/{note.name}', 'title': note.stem})
            # dialogue/
            dialogue_dir = proj / 'dialogue'
            if dialogue_dir.exists():
                for d in sorted(dialogue_dir.glob('*.md'), reverse=True)[:5]:
                    proj_files.append({'path': f'项目/{proj.name}/dialogue/{d.name}', 'title': d.stem})
            if proj_files:
                index_sections['projects'][proj.name] = proj_files

    # _compiled/
    if compiled_dir.exists():
        for cat in ['概念', '人物', '关联']:
            cat_dir = compiled_dir / cat
            if cat_dir.exists():
                for f in cat_dir.glob('*.md'):
                    if f.name != '索引.md':
                        index_sections['compiled'][cat].append({
                            'path': f'_compiled/{cat}/{f.name}',
                            'title': f.stem
                        })

    # _social_graph/log/
    if social_log_dir.exists():
        for f in sorted(social_log_dir.glob('*.md'), reverse=True)[:10]:
            index_sections['social'].append({
                'path': f'_social_graph/log/{f.name}',
                'title': f.stem
            })

    # _biometrics/log/
    if biometrics_log_dir.exists():
        for f in sorted(biometrics_log_dir.glob('*.md'), reverse=True)[:10]:
            index_sections['biometrics'].append({
                'path': f'_biometrics/log/{f.name}',
                'title': f.stem
            })

    # _private_sources/
    sources_root = vault / PRIVATE_SOURCES_DIR
    if sources_root.exists():
        for proj in sources_root.iterdir():
            if not proj.is_dir():
                continue
            src_files = []
            for f in proj.rglob('*.md'):
                rel = f.relative_to(sources_root)
                src_files.append({'path': f'_private_sources/{rel}', 'title': f.stem})
            if src_files:
                index_sections['sources'][proj.name] = src_files

    # _log/
    log_dir = vault / LOG_DIR
    if log_dir.exists():
        for f in sorted(log_dir.glob('*.md'), reverse=True)[:12]:
            index_sections['logs'].append({
                'path': f'_log/{f.name}',
                'title': f.stem
            })

    # 生成 _index.md
    index_content = generate_index_content(index_sections)
    index_file.write_text(index_content, encoding='utf-8')

    return str(index_file.relative_to(vault))


def generate_index_content(sections: dict) -> str:
    """生成 _index.md 内容"""
    content = "# 全局知识地图\n\n"
    content += f"> 最后更新：{_today_str()}\n"
    content += "> 维护者：炼金术 Agent（T-1 批处理自动更新）\n\n"
    content += "---\n\n"

    # 日记
    content += "## 日记\n\n"
    if sections['diary']:
        content += "| 日期 | 摘要 |\n|------|------|\n"
        for d in sections['diary'][:10]:
            content += f"| [[{d['path']}]] | {d['title']} |\n"
    else:
        content += "| 日期 | 摘要 |\n|------|------|\n| （暂无） | - |\n"
    content += "\n---\n\n"

    # 项目
    content += "## 项目\n\n"
    for proj_name, files in sections['projects'].items():
        content += f"### {proj_name}\n\n"
        content += "| 页面 | 摘要 |\n|------|------|\n"
        for f in files[:10]:
            content += f"| [[{f['path']}]] | {f['title']} |\n"
        content += "\n"

    # 编译索引
    content += "## 编译索引 (_compiled)\n\n"
    for cat, items in sections['compiled'].items():
        content += f"### {cat}\n\n"
        if items:
            content += "| 概念 | 引用页面 |\n|------|----------|\n"
            for item in items:
                content += f"| [[{item['path']}]] | - |\n"
        else:
            content += "| 概念 | 引用页面 |\n|------|----------|\n| （暂无） | - |\n"
        content += "\n"

    # 人际互动
    content += "## 人际互动 (_social_graph)\n\n"
    content += "### log/互动事实\n\n"
    if sections['social']:
        content += "| 人物 | 最近互动 |\n|------|----------|\n"
        for s in sections['social'][:5]:
            content += f"| [[{s['path']}]] | {s['title']} |\n"
    else:
        content += "| 人物 | 最近互动 |\n|------|----------|\n| （暂无） | - |\n"
    content += "\n"

    content += "### review/关系判断\n\n"
    content += "> 注：以下内容需周末闭门会人类授权后可见\n\n"
    content += "| 人物 | 判断与策略 |\n|------|----------|\n| （暂无） | - |\n\n"

    # 体征数据
    content += "## 体征数据 (_biometrics)\n\n"
    content += "### log/数据记录\n\n"
    if sections['biometrics']:
        content += "| 时间段 | 数据摘要 |\n|--------|----------|\n"
        for b in sections['biometrics'][:5]:
            content += f"| [[{b['path']}]] | {b['title']} |\n"
    else:
        content += "| 时间段 | 数据摘要 |\n|--------|----------|\n| （暂无） | - |\n"
    content += "\n"

    content += "### review/趋势判断\n\n"
    content += "> 注：以下内容需周末闭门会人类授权后可见\n\n"
    content += "| 时间段 | 判断与策略 |\n|--------|----------|\n| （暂无） | - |\n\n"

    # 核心认知
    content += "## 核心认知 (_persona)\n\n"
    content += "> 注：以下内容需周末闭门会人类授权后可见\n\n"
    content += "| 维度 | 内容 |\n|------|------|\n| （暂无） | - |\n\n"

    # 素材索引
    content += "## 素材索引 (_private_sources)\n\n"
    for proj_name, files in sections['sources'].items():
        content += f"### {proj_name}\n\n"
        content += "| 素材 | 类型 | 日期 |\n|------|------|------|\n"
        for f in files[:10]:
            content += f"| [[{f['path']}]] | - | - |\n"
        content += "\n"

    # 操作日志
    content += "## 操作日志 (_log)\n\n"
    content += "| 月份 | 记录 |\n|------|------|\n"
    for log in sections['logs']:
        content += f"| [[{log['path']}]] | {log['title']} |\n"
    content += "\n"

    content += "*本索引由炼金术 Agent 在每日 T-1 批处理时自动维护*\n"

    return content


def update_compiled(vault_path: str = None) -> list:
    """
    更新 _compiled/ 跨域索引
    返回：更新的文件列表
    """
    vault = _get_vault(vault_path)
    compiled_dir = vault / COMPILED_DIR
    projects_dir = vault / PROJECTS_DIR

    updated = []

    # 扫描所有 notes/ 提取概念
    concepts = {}
    if projects_dir.exists():
        for proj in projects_dir.iterdir():
            if not proj.is_dir():
                continue
            notes_dir = proj / 'notes'
            if notes_dir.exists():
                for note in notes_dir.glob('*.md'):
                    concept = note.stem
                    if concept not in concepts:
                        concepts[concept] = []
                    concepts[concept].append(f'[[项目/{proj.name}/notes/{note.name}]]')

    # 为每个概念创建/更新页面
    concept_dir = compiled_dir / '概念'
    concept_dir.mkdir(parents=True, exist_ok=True)

    for concept, refs in concepts.items():
        concept_file = concept_dir / f"{concept}.md"
        if concept_file.exists():
            existing = concept_file.read_text(encoding='utf-8')
            # 检查是否有新引用
            if len(refs) > existing.count('[['):
                # 更新
                pass
        else:
            # 创建新页面
            content = f"# {concept}\n\n"
            content += f"> 创建：{_today_str()}\n"
            content += "> 维护者：炼金术 Agent（T-1 批处理自动更新）\n\n"
            content += "---\n\n"
            content += "## 核心定义\n\n（待萃取）\n\n"
            content += "## 跨项目引用\n\n"
            for ref in refs:
                content += f"- {ref}\n"
            concept_file.write_text(content, encoding='utf-8')
            updated.append(str(concept_file.relative_to(vault)))

    return updated


# ==================== 阶段 5: 记录人际互动 ====================

def record_social_interactions(date: str, vault_path: str = None) -> str:
    """
    从日记/raw 中提取人际互动事实
    返回：文件路径
    """
    vault = _get_vault(vault_path)
    social_dir = vault / SOCIAL_GRAPH_LOG_DIR
    social_dir.mkdir(parents=True, exist_ok=True)

    # TODO: 从日记中提取人物互动
    # 这里先创建占位文件

    log_file = social_dir / f"{date}.md"
    content = f"# {date} 人际互动\n\n"
    content += f"> 归档时间：{_now_str()}\n\n"
    content += "---\n\n"
    content += "## 互动记录\n\n（待提取）\n"
    log_file.write_text(content, encoding='utf-8')

    return str(log_file.relative_to(vault))


# ==================== 阶段 6: 记录体征数据 ====================

def record_biometrics(date: str, vault_path: str = None) -> str:
    """
    从日记/raw 中提取体征数据
    返回：文件路径
    """
    vault = _get_vault(vault_path)
    bio_dir = vault / BIOMETRICS_LOG_DIR
    bio_dir.mkdir(parents=True, exist_ok=True)

    # TODO: 从日记中提取身体数据
    # 这里先创建占位文件

    log_file = bio_dir / f"{date}.md"
    content = f"# {date} 体征数据\n\n"
    content += f"> 归档时间：{_now_str()}\n\n"
    content += "---\n\n"
    content += "## 数据记录\n\n（待提取）\n"
    log_file.write_text(content, encoding='utf-8')

    return str(log_file.relative_to(vault))


# ==================== 阶段 7: Lint 巡检 ====================

def lint_check(vault_path: str = None) -> str:
    """
    扫描全库，检测矛盾信息、孤立页面、过期引用、概念空洞
    返回：lint 报告路径
    """
    vault = _get_vault(vault_path)
    lint_dir = vault / LINT_REPORT_DIR
    lint_dir.mkdir(parents=True, exist_ok=True)

    today = _today_str()
    report_file = lint_dir / f"{today}.md"

    issues = {
        'orphan': [],  # 孤立页面
        'broken_link': [],  # 过期引用
        'empty_concept': [],  # 概念空洞
        'conflict': []  # 矛盾信息
    }

    # 检查孤立页面（没有 wikilink 指向的 notes/）
    projects_dir = vault / PROJECTS_DIR
    if projects_dir.exists():
        for proj in projects_dir.iterdir():
            if not proj.is_dir():
                continue
            notes_dir = proj / 'notes'
            if notes_dir.exists():
                for note in notes_dir.glob('*.md'):
                    # TODO: 检查是否有其他地方引用这个 note
                    pass

    # 检查 _compiled/ 中的空洞概念
    compiled_dir = vault / COMPILED_DIR
    concept_dir = compiled_dir / '概念'
    if concept_dir.exists():
        for f in concept_dir.glob('*.md'):
            content = f.read_text(encoding='utf-8')
            if '待萃取' in content and content.count('[[') < 2:
                issues['empty_concept'].append(f'_compiled/概念/{f.name}')

    # 生成报告
    report = f"# {today} Lint 报告\n\n"
    report += f"> 生成时间：{_now_str()}\n\n---\n\n"

    report += f"## 概览\n\n"
    report += f"- 孤立页面：{len(issues['orphan'])}\n"
    report += f"- 过期引用：{len(issues['broken_link'])}\n"
    report += f"- 空洞概念：{len(issues['empty_concept'])}\n"
    report += f"- 矛盾信息：{len(issues['conflict'])}\n\n"

    if issues['empty_concept']:
        report += "## 空洞概念\n\n"
        for item in issues['empty_concept']:
            report += f"- `{item}`\n"
        report += "\n"

    if not any(issues.values()):
        report += "✓ 未发现问题\n"

    report_file.write_text(report, encoding='utf-8')
    return str(report_file.relative_to(vault))


# ==================== 完整流水线 ====================

def run_full_pipeline(date: str = None, vault_path: str = None) -> dict:
    """
    执行完整的六阶段流水线
    返回：{stage1, stage2, stage3, stage4, stage5, stage6, stage7}
    """
    if date is None:
        date = _yesterday_str()

    results = {}

    print(f"开始 T-1 批处理 [{date}]...")

    try:
        # 阶段 1
        print("阶段 1: 编纂日记...")
        results['stage1'] = compile_diary(date, vault_path)

        # 阶段 2
        print("阶段 2: 萃取金砖...")
        results['stage2'] = extract_insights(date, vault_path)

        # 阶段 3
        print("阶段 3: 读取变更报告...")
        results['stage3'] = read_change_log(date, vault_path)

        # 阶段 4
        print("阶段 4: 编译跨域索引...")
        index_path = update_index_md(vault_path)
        compiled_updates = update_compiled(vault_path)
        results['stage4'] = {'index': index_path, 'compiled': compiled_updates}

        # 阶段 5
        print("阶段 5: 记录人际互动...")
        results['stage5'] = record_social_interactions(date, vault_path)

        # 阶段 6
        print("阶段 6: 记录体征数据...")
        results['stage6'] = record_biometrics(date, vault_path)

        # 阶段 7
        print("阶段 7: Lint 巡检...")
        results['stage7'] = lint_check(vault_path)

        print(f"批处理完成！")

    except Exception as e:
        print(f"ERROR: 批处理失败 - {e}", file=sys.stderr)
        raise

    return results


# ==================== CLI ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='记忆宫殿炼金术 Agent')
    parser.add_argument('--vault', '-v', type=str, default=DEFAULT_VAULT, help='Vault 路径')
    parser.add_argument('--action', '-a', type=str, required=True,
                        choices=['run', 'compile_diary', 'update_index', 'lint'],
                        help='执行动作')
    parser.add_argument('--date', '-d', type=str, default=None, help='处理日期 (YYYY-MM-DD, 默认昨天)')
    parser.add_argument('--json', dest='output_json', action='store_true', help='以 JSON 格式输出')
    args = parser.parse_args()

    vault = args.vault or DEFAULT_VAULT

    if args.action == 'run':
        results = run_full_pipeline(args.date, vault)
        if args.output_json:
            print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        else:
            for stage, result in results.items():
                print(f"{stage}: {result}")

    elif args.action == 'compile_diary':
        result = compile_diary(args.date or _yesterday_str(), vault)
        print(result)

    elif args.action == 'update_index':
        result = update_index_md(vault)
        print(result)

    elif args.action == 'lint':
        result = lint_check(vault)
        print(result)


if __name__ == '__main__':
    main()
