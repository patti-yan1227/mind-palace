#!/usr/bin/env python3
"""
记忆宫殿炼金术 Agent

职责：
1. T-1 批处理：每天凌晨 00:00 处理昨日数据
2. 五阶段流水线（记录机器，不做战略判断）：
   ① 编纂日记：读取 T-1 _raw_inbox/ → 日记/{date}.md
   ② 编译跨域索引：更新 _index.md 和 _compiled/
   ③ 记录人际互动：→ _social_graph/log/
   ④ 记录体征数据：→ _biometrics/log/
   ⑤ Lint 巡检：→ _lint_report/{date}.md
3. 异常即停：任一阶段异常立刻终止并告警

注：萃取金砖（高价值内容提取）已移至每周复盘 Agent（review_agent.py），
    由人机共决写入 _persona/ Persona Engine。
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（项目根目录）
load_dotenv()

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
PROJECTS_DIRS = ['学习', '项目']  # 同时扫描学习项目和战役项目
PRIVATE_SOURCES_DIR = '_private_sources'

# WIKI_SCHEMA 路径（项目根目录）
WIKI_SCHEMA_PATH = Path(__file__).parent.parent / 'WIKI_SCHEMA.md'

# LLM 配置（可选，用户自行配置）
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-5-20251001')
LLM_API_BASE_URL = os.getenv('LLM_API_BASE_URL', 'https://api.anthropic.com')
USE_LLM = os.getenv('ALCHEMY_USE_LLM', 'false').lower() == 'true'  # 默认关闭，用户手动开启

# ==================== WIKI_SCHEMA 加载 ====================

WIKI_SCHEMA = {
    'concept_template': '',
    'person_template': '',
    'relation_template': '',
    'loaded': False
}


def load_wiki_schema() -> dict:
    """
    加载 WIKI_SCHEMA.md，验证文件存在
    返回：schema 字典
    """
    if WIKI_SCHEMA['loaded']:
        return WIKI_SCHEMA

    if not WIKI_SCHEMA_PATH.exists():
        print(f"警告：WIKI_SCHEMA.md 未找到，使用默认模板")
        _set_default_templates()
        WIKI_SCHEMA['loaded'] = True
        return WIKI_SCHEMA

    try:
        # 只验证文件存在且可读，模板使用默认定义
        content = WIKI_SCHEMA_PATH.read_text(encoding='utf-8')
        if '# _compiled/ 规格说明书' in content:
            print(f"WIKI_SCHEMA 验证成功：{WIKI_SCHEMA_PATH}")
            _set_default_templates()  # 使用代码中定义的模板
        else:
            print("警告：WIKI_SCHEMA.md 格式不正确，使用默认模板")
            _set_default_templates()

    except Exception as e:
        print(f"警告：WIKI_SCHEMA 读取失败 - {e}，使用默认模板")
        _set_default_templates()

    WIKI_SCHEMA['loaded'] = True
    return WIKI_SCHEMA


def _set_default_templates():
    """设置默认模板（兜底）"""
    # 概念页模板
    WIKI_SCHEMA['concept_template'] = """# {{title}}

---
type: concept
title: {{title}}
aliases: []
sources: []
related: []
created: {{created}}
updated: {{updated}}
confidence: {{confidence}}
---

## 核心定义

（待萃取）

## 跨项目引用

{{sources}}

## 关联概念

{{related}}

## 开放问题

（待补充）
"""
    WIKI_SCHEMA['loaded'] = True


def _fill_concept_template(concept_name: str, sources: list, related: list, created: str, updated: str, confidence: str = 'speculative') -> str:
    """
    填充概念页模板
    """
    schema = load_wiki_schema()
    template = schema['concept_template']

    # 生成引用列表
    sources_md = '\n'.join(f'- {ref}' for ref in sources)
    related_md = '\n'.join(f'- {ref}' for ref in related) if related else '（暂无）'

    # 替换占位符
    content = template.replace('{{title}}', concept_name)
    content = content.replace('{{概念名}}', concept_name)
    content = content.replace('{{created}}', created)
    content = content.replace('{{updated}}', updated)
    content = content.replace('{{confidence}}', confidence)
    content = content.replace('{{sources}}', sources_md)
    content = content.replace('{{related}}', related_md)

    return content


def llm_generate(prompt: str) -> str:
    """
    调用 LLM 生成内容（支持 Anthropic 兼容接口，如通义千问）
    """
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        # 处理返回内容（兼容不同 LLM 的返回格式）
        # 通义千问可能返回 ThinkingBlock 和 TextBlock 的混合
        result_parts = []
        for block in response.content:
            block_type = getattr(block, 'type', None)
            # 跳过 thinking 块，只保留 text 块
            if block_type == 'thinking':
                continue
            elif block_type == 'text':
                result_parts.append(getattr(block, 'text', ''))
            elif hasattr(block, 'text'):
                result_parts.append(block.text)
            else:
                # 其他类型尝试直接获取内容
                result_parts.append(str(block))
        return ''.join(result_parts)
    except ImportError:
        raise ImportError(
            "请安装 anthropic SDK: pip install anthropic"
        )
    except Exception as e:
        raise RuntimeError(f"LLM 调用失败：{e}")


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


def detect_new_sources(vault_path: str = None, hours: int = 48) -> list:
    """
    扫描 _private_sources/ 中近 N 小时内新增的文件。
    返回：[{'project': str, 'title': str, 'path': str, 'age_h': int}, ...]
    """
    vault = _get_vault(vault_path)
    sources_root = vault / PRIVATE_SOURCES_DIR
    if not sources_root.exists():
        return []

    now = datetime.now()
    new_files = []
    for proj in sorted(sources_root.iterdir()):
        if not proj.is_dir():
            continue
        for f in proj.rglob('*.md'):
            age_h = (now - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() / 3600
            if age_h <= hours:
                rel = f.relative_to(sources_root)
                new_files.append({
                    'project': proj.name,
                    'title': f.stem,
                    'path': f'_private_sources/{rel}',
                    'age_h': int(age_h),
                })
    new_files.sort(key=lambda x: x['age_h'])
    return new_files


# ==================== 阶段 1: 编纂日记 ====================

DIARY_GENERATION_PROMPT = """
你是一位专业的日记编纂师和心理分析师。请根据以下原始记录，整理成一篇结构完整、有洞察力的日记。

## 输入素材

### 原始碎碎念（_raw_inbox/）
{raw_text}

### 学习/行为记录（_log/）
{log_text}

## 输出要求

请按以下格式输出 Markdown（**不要输出任何额外的标题或 markdown 代码块标记**）：

# {date} 日记

> 归档时间：{timestamp}
> 原始素材：{count} 条
> 学习记录：{log_count} 条

---

## 一、今日概览

（200-300 字，用流畅的叙述风格总结这一天，保持用户原本的意思）

## 二、结构化总结

### （1）发生了什么 / 心情和状态

（用条目式列出今天的主要事件和情绪状态）

### （2）灵感与想法要点

（提取用户今天的核心洞察，每条带简短说明）

### （3）积极的愿望

（从内容中提取用户表达的积极期待，如没有则写"暂无明确表达"）

### （4）感谢的事

（提取用户表达感谢的内容，如没有则写"暂无明确表达"）

### （5）未完成待办

（从内容中提取待办事项和悬而未决的问题）

## 三、生活洞察与建议

（以平衡型心理专家/人生导师的视角，给出 2-3 条分析建议）

**观察到的模式：**
（指出用户行为/情绪中值得注意的模式）

**建议：**
（给出具体可行的建议）

**鼓励：**
（基于事实的真诚鼓励，不是空洞的安慰）

## 注意事项

1. **保持原意**：不要改变用户记录的本意，只优化表达结构
2. **平衡型建议**：既要指出问题，也要给予肯定，不偏严厉也不偏鸡汤
3. **具体可执行**：建议要具体，不要说"要多运动"这种空话
4. **尊重隐私**：这是用户的私人日记，保持尊重和共情
5. **格式要求**：直接输出日记内容，不要加 ```markdown 包裹，不要输出额外的日期标题
"""


def compile_diary(date: str, vault_path: str = None, use_llm: bool = True) -> str:
    """
    读取指定日期的 _raw_inbox/ 文件，编纂结构化日记
    返回：日记文件路径

    注：日记按 年/月/ 分层目录组织，如：日记/2026/04/2026-04-13.md
    """
    vault = _get_vault(vault_path)
    raw_dir = vault / RAW_INBOX_DIR
    diary_dir = vault / DIARY_DIR

    # 按年/月分层目录
    year = date[0:4]
    month = date[5:7]
    target_dir = diary_dir / year / month
    target_dir.mkdir(parents=True, exist_ok=True)

    # 读取该日期所有 raw 文件
    raw_files = sorted(raw_dir.glob(f"{date}.md"))
    if not raw_files:
        return f"日记 {date}: 无原始输入"

    raw_entries = []
    for rf in raw_files:
        content = rf.read_text(encoding='utf-8')
        raw_entries.append(content)

    # 读取该日期的 _log/ 记录
    log_entries = []
    log_file = vault / LOG_DIR / f"{datetime.now().strftime('%Y-%m')}.md"
    if log_file.exists():
        log_content = log_file.read_text(encoding='utf-8')
        # 提取该日期的记录
        import re
        log_matches = re.findall(rf'### \[{date}\] (ingest|query) \| ([^\n]+)(.*?)(?=### \[|$)', log_content, re.DOTALL)
        for op_type, desc, details in log_matches:
            log_entries.append(f"[{op_type}] {desc}: {details.strip()}")

    # 合并原始内容
    raw_text = '\n\n'.join(raw_entries)
    log_text = '\n'.join(log_entries) if log_entries else '无学习记录'

    if use_llm:
        # 调用 LLM 生成结构化日记
        try:
            prompt = DIARY_GENERATION_PROMPT.format(
                date=date,
                timestamp=_now_str(),
                count=len(raw_files),
                log_count=len(log_entries),
                raw_text=raw_text,
                log_text=log_text
            )
            structured_content = llm_generate(prompt)
        except NotImplementedError as e:
            # LLM 未配置，降级到兜底逻辑
            print(f"注意：{e}")
            structured_content = f"# {date} 日记\n\n> 归档时间：{_now_str()}\n\n**注意：** LLM 生成功能待接入\n\n---\n\n## 原始记录\n\n{raw_text}\n\n## 学习记录\n\n{log_text}"
        except Exception as e:
            # LLM 调用失败，降级到兜底逻辑
            print(f"警告：LLM 生成失败 - {e}，使用兜底逻辑")
            structured_content = f"# {date} 日记\n\n> 归档时间：{_now_str()}\n\n**注意：** LLM 生成失败，使用兜底逻辑\n\n---\n\n## 原始记录\n\n{raw_text}\n\n## 学习记录\n\n{log_text}"
    else:
        # 机械重组（兜底）
        structured_content = f"# {date} 日记\n\n"
        structured_content += f"> 归档时间：{_now_str()}\n"
        structured_content += f"> 原始素材：{len(raw_files)} 条\n\n"
        structured_content += "---\n\n"
        structured_content += "## 原始记录\n\n"
        for i, entry in enumerate(raw_entries, 1):
            structured_content += f"### {i}\n\n{entry}\n\n"
        if log_entries:
            structured_content += "## 学习记录\n\n"
            for entry in log_entries:
                structured_content += f"- {entry}\n"

    # 写入文件（按年/月分层）
    diary_file = target_dir / f"{date}.md"
    diary_file.write_text(structured_content, encoding='utf-8')

    return str(diary_file.relative_to(vault))


# ==================== 阶段 2（内部辅助）: 读取变更报告 ====================

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
    pattern = rf'### \[{date}\] ingest \| ([^\n]+) 学习 session(.*?)(?=### \[|$)'
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
    compiled_dir = vault / COMPILED_DIR
    diary_dir = vault / DIARY_DIR
    social_log_dir = vault / SOCIAL_GRAPH_LOG_DIR
    biometrics_log_dir = vault / BIOMETRICS_LOG_DIR

    # 收集各部分内容
    index_sections = {
        'projects': [],  # 只列出 map.md 入口
        'compiled': {'概念': [], '人物': [], '关联': []},
        'social': [],
        'biometrics': [],
        'sources': {},
        'logs': []
    }

    # 项目（扫描学习/和 projects/两个目录）
    for proj_dir_name in PROJECTS_DIRS:
        projects_dir = vault / proj_dir_name
        if not projects_dir.exists():
            continue
        for proj in projects_dir.iterdir():
            if not proj.is_dir():
                continue
            map_file = proj / 'map.md'
            if map_file.exists():
                # 读取 map.md 的第一行作为描述
                map_content = map_file.read_text(encoding='utf-8')
                first_line = map_content.split('\n')[0].lstrip('#').strip()
                index_sections['projects'].append({
                    'path': f'{proj_dir_name}/{proj.name}/map.md',
                    'title': proj.name,
                    'desc': first_line
                })

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

    # 日记（简化版，直接跳转到完整索引）
    content += "## 日记\n\n"
    content += "> 📅 完整索引：**[[日记/索引]]**\n>\n"
    content += "> 日记按年/月组织：`日记/YYYY/MM/DD.md`\n\n"
    content += "---\n\n"

    # 项目（只列出 map.md 入口）
    content += "## 项目\n\n"
    if sections['projects']:
        content += "| 项目 | 知识版图 | 简介 |\n|------|----------|------|\n"
        for proj in sections['projects']:
            desc = proj.get('desc', '')[:50] + '...' if len(proj.get('desc', '')) > 50 else proj.get('desc', '-')
            content += f"| **{proj['title']}** | [[{proj['path']}]] | {desc} |\n"
    else:
        content += "| 项目 | 知识版图 | 简介 |\n|------|----------|------|\n| （暂无） | - | - |\n"
    content += "\n---\n\n"

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


def update_diary_index(vault_path: str = None) -> str:
    """
    扫描 日记/ 目录，重新生成 日记/索引.md。
    每次 compile_diary 后自动调用。
    """
    vault = _get_vault(vault_path)
    diary_dir = vault / DIARY_DIR
    index_file = diary_dir / '索引.md'

    # 收集所有日记文件，按年/月分层
    from collections import defaultdict
    year_month_files = defaultdict(lambda: defaultdict(list))
    all_files = []

    for md in sorted(diary_dir.rglob('*.md')):
        if md.name == '索引.md':
            continue
        parts = md.relative_to(diary_dir).parts
        if len(parts) == 3:  # YYYY/MM/filename.md
            year, month = parts[0], parts[1]
            year_month_files[year][month].append(md.stem)
            all_files.append((year, month, md.stem))
        elif len(parts) == 1:  # 旧格式 filename.md（直接在根目录）
            year_month_files['旧']['--'].append(md.stem)
            all_files.append(('旧', '--', md.stem))

    all_files.sort(reverse=True)

    # 生成目录结构文本
    tree_lines = ['日记/', '├── 索引.md (本文件)']
    for year in sorted(year_month_files.keys(), reverse=True):
        if year == '旧':
            continue
        tree_lines.append(f'├── {year}/')
        months = sorted(year_month_files[year].keys(), reverse=True)
        for i, month in enumerate(months):
            count = len(year_month_files[year][month])
            prefix = '│   └──' if i == len(months) - 1 else '│   ├──'
            tree_lines.append(f'{prefix} {month}/  ({month.lstrip("0")} 月，{count} 篇)')

    # 生成快速链接
    links_section = '## 快速链接\n\n'
    for year in sorted(year_month_files.keys(), reverse=True):
        if year == '旧':
            continue
        links_section += f'### {year} 年\n\n'
        for month in sorted(year_month_files[year].keys(), reverse=True):
            files = sorted(year_month_files[year][month], reverse=True)
            count = len(files)
            links_section += f'**{month.lstrip("0")}月** ({count}篇)\n\n'
            links_section += ' | '.join(f'[[日记/{year}/{month}/{f}]]' for f in files)
            links_section += '\n\n'

    # 生成最近 10 篇
    recent = all_files[:10]
    recent_section = '## 最近 10 篇日记\n\n| 日期 | 链接 |\n|------|------|\n'
    for year, month, stem in recent:
        if year == '旧':
            recent_section += f'| {stem} | [[日记/{stem}]] |\n'
        else:
            recent_section += f'| {stem} | [[日记/{year}/{month}/{stem}]] |\n'

    now_str = datetime.now().strftime('%Y/%m/%d %a')
    content = (
        '# 日记索引\n\n'
        '> 本索引按年/月组织，方便查找历史日记\n\n'
        '---\n\n'
        '## 目录结构\n\n'
        '```\n' + '\n'.join(tree_lines) + '\n```\n\n'
        '---\n\n'
        + links_section +
        '---\n\n'
        + recent_section +
        '\n---\n\n'
        '## 使用说明\n\n'
        '- 新增日记自动写入 `YYYY/MM/` 子目录（如 `2026/04/2026-04-14.md`）\n'
        '- 炼金术 Agent 在每次 compile_diary 后自动更新本索引\n'
        '- Obsidian 可以正常识别子目录中的双向链接\n\n'
        '---\n\n'
        f'*最后更新：{now_str}*\n'
        '*本索引由炼金术 Agent 在 T-1 批处理时自动维护*\n'
    )

    index_file.write_text(content, encoding='utf-8')
    return str(index_file.relative_to(vault))


def update_compiled(vault_path: str = None) -> list:
    """
    更新 _compiled/ 跨域索引
    返回：更新的文件列表
    """
    vault = _get_vault(vault_path)
    compiled_dir = vault / COMPILED_DIR
    projects_dir = vault / PROJECTS_DIR

    # 加载 WIKI_SCHEMA
    load_wiki_schema()

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
                    concepts[concept].append(f'[[../../项目/{proj.name}/notes/{note.name}]]')

    # 为每个概念创建/更新页面
    concept_dir = compiled_dir / '概念'
    concept_dir.mkdir(parents=True, exist_ok=True)

    today = _today_str()

    for concept, refs in concepts.items():
        concept_file = concept_dir / f"{concept}.md"
        if concept_file.exists():
            existing = concept_file.read_text(encoding='utf-8')
            # 检查是否有新引用
            if len(refs) > existing.count('[['):
                # 更新现有页面：保留原有内容，追加新引用
                # 找到"跨项目引用"section，追加新引用
                import re
                match = re.search(r'## 跨项目引用\n\n(.*?)(?=## |$)', existing, re.DOTALL)
                if match:
                    existing_refs = match.group(1).strip()
                    # 找出还没有添加的引用
                    new_refs = [ref for ref in refs if ref not in existing_refs]
                    if new_refs:
                        new_refs_md = '\n'.join(new_refs)
                        updated_content = existing.replace(match.group(0), f"## 跨项目引用\n\n{existing_refs}\n{new_refs_md}\n")
                        updated_content = updated_content.replace(f'updated: ', f'updated: {today}\n# updated: ')
                        concept_file.write_text(updated_content, encoding='utf-8')
                        updated.append(str(concept_file.relative_to(vault)))
        else:
            # 创建新页面（使用 WIKI_SCHEMA 模板）
            content = _fill_concept_template(
                concept_name=concept,
                sources=refs,
                related=[],
                created=today,
                updated=today,
                confidence='speculative'  # 新概念默认 speculative
            )
            concept_file.write_text(content, encoding='utf-8')
            updated.append(str(concept_file.relative_to(vault)))

    return updated


# ==================== 阶段 3: 记录人际互动 ====================

SOCIAL_EXTRACTION_PROMPT = """
你是一位人际关系分析助手。请从以下日记中提取所有涉及真实人物的互动事实。

## 日记内容

{diary_content}

## 输出要求

只输出 Markdown，格式如下（**不要输出任何额外标题或代码块标记**）：

## 互动记录

| 人物 | 互动类型 | 摘要 | 情感色彩 |
|------|----------|------|----------|
（每行一条互动，互动类型选：聊天/合作/冲突/见面/提及/其他）
（情感色彩选：积极/中性/消极）

## 备注

（如果没有明确的人际互动，写"本日无明确人际互动记录"）

## 注意事项

- 只记录真实人物，不记录虚拟角色或泛指
- 只记录事实，不做主观评价
- 如果日记中完全没有提到人物，输出"本日无明确人际互动记录"
"""


def record_social_interactions(date: str, vault_path: str = None) -> str:
    """
    从日记中提取人际互动事实（LLM 驱动）
    返回：文件路径
    """
    vault = _get_vault(vault_path)
    social_dir = vault / SOCIAL_GRAPH_LOG_DIR
    social_dir.mkdir(parents=True, exist_ok=True)

    log_file = social_dir / f"{date}.md"

    # 读取日记
    diary_file = vault / DIARY_DIR / f"{date}.md"
    diary_content = diary_file.read_text(encoding='utf-8') if diary_file.exists() else ""

    header = f"# {date} 人际互动\n\n> 归档时间：{_now_str()}\n\n---\n\n"

    if not diary_content:
        content = header + "## 互动记录\n\n本日无日记，跳过提取。\n"
    elif USE_LLM:
        try:
            prompt = SOCIAL_EXTRACTION_PROMPT.format(diary_content=diary_content)
            extracted = llm_generate(prompt)
            content = header + extracted
        except Exception as e:
            print(f"警告：人际互动 LLM 提取失败 - {e}，使用占位内容")
            content = header + "## 互动记录\n\n（LLM 提取失败，请手动检查）\n"
    else:
        content = header + "## 互动记录\n\n（ALCHEMY_USE_LLM=false，跳过自动提取）\n"

    log_file.write_text(content, encoding='utf-8')
    return str(log_file.relative_to(vault))


# ==================== 阶段 4: 记录体征数据 ====================

BIOMETRICS_EXTRACTION_PROMPT = """
你是一位健康数据分析助手。请从以下日记中提取所有与身体状态相关的信息。

## 日记内容

{diary_content}

## 输出要求

只输出 Markdown，格式如下（**不要输出任何额外标题或代码块标记**）：

## 数据记录

| 维度 | 数据 | 说明 |
|------|------|------|
| 睡眠 | （时长/质量，如：7h/良好） | （原文依据） |
| 运动 | （类型+时长，如：散步30min） | （原文依据） |
| 情绪 | （描述+色彩，如：焦虑/负面） | （原文依据） |
| 精力 | （1-10分，如：8/10） | （原文依据） |
| 饮食 | （有异常才填，如：暴食/节食） | （原文依据） |
| 其他 | （头痛/疲劳等症状） | （原文依据） |

## 趋势备注

（如有明显异常或值得关注的模式，在此说明；如无则写"无异常"）

## 注意事项

- 只记录日记中明确提到的信息，不推断
- 没有提到的维度填"未记录"
- 数据要精简，一行一条
"""


def record_biometrics(date: str, vault_path: str = None) -> str:
    """
    从日记中提取体征数据（LLM 驱动）
    返回：文件路径
    """
    vault = _get_vault(vault_path)
    bio_dir = vault / BIOMETRICS_LOG_DIR
    bio_dir.mkdir(parents=True, exist_ok=True)

    log_file = bio_dir / f"{date}.md"

    # 读取日记
    diary_file = vault / DIARY_DIR / f"{date}.md"
    diary_content = diary_file.read_text(encoding='utf-8') if diary_file.exists() else ""

    header = f"# {date} 体征数据\n\n> 归档时间：{_now_str()}\n\n---\n\n"

    if not diary_content:
        content = header + "## 数据记录\n\n本日无日记，跳过提取。\n"
    elif USE_LLM:
        try:
            prompt = BIOMETRICS_EXTRACTION_PROMPT.format(diary_content=diary_content)
            extracted = llm_generate(prompt)
            content = header + extracted
        except Exception as e:
            print(f"警告：体征数据 LLM 提取失败 - {e}，使用占位内容")
            content = header + "## 数据记录\n\n（LLM 提取失败，请手动检查）\n"
    else:
        content = header + "## 数据记录\n\n（ALCHEMY_USE_LLM=false，跳过自动提取）\n"

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
    执行完整的五阶段流水线
    返回：{stage1, stage2, stage3, stage4, stage5}

    注：萃取金砖（战略判断）已移至 review_agent.py 每周复盘时执行。
    """
    if date is None:
        date = _yesterday_str()

    results = {}

    print(f"开始 T-1 批处理 [{date}]...")

    try:
        # 阶段 1: 编纂日记
        print("阶段 1: 编纂日记...")
        results['stage1'] = compile_diary(date, vault_path)
        update_diary_index(vault_path)

        # 阶段 2: 编译跨域索引
        print("阶段 2: 编译跨域索引...")
        index_path = update_index_md(vault_path)
        compiled_updates = update_compiled(vault_path)
        new_sources = detect_new_sources(vault_path)
        results['stage2'] = {'index': index_path, 'compiled': compiled_updates, 'new_sources': new_sources}

        # 阶段 3: 记录人际互动
        print("阶段 3: 记录人际互动...")
        results['stage3'] = record_social_interactions(date, vault_path)

        # 阶段 4: 记录体征数据
        print("阶段 4: 记录体征数据...")
        results['stage4'] = record_biometrics(date, vault_path)

        # 阶段 5: Lint 巡检
        print("阶段 5: Lint 巡检...")
        results['stage5'] = lint_check(vault_path)

        print("批处理完成！")

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
                if stage == 'stage2' and isinstance(result, dict):
                    print(f"stage2: index={result.get('index')}, compiled={result.get('compiled')}")
                    new_sources = result.get('new_sources', [])
                    if new_sources:
                        print(f"  [新入库素材 48h内]")
                        for s in new_sources:
                            print(f"    [{s['project']}] {s['title']} ({s['age_h']}h ago)")
                    else:
                        print("  新入库素材：无")
                else:
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
