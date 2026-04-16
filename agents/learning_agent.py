#!/usr/bin/env python3
"""
记忆宫殿学习 Agent

职责：
1. 启动时检查：未关闭 session / 未处理 highlights / 搁置过久的问题
2. 列出项目并推荐下一步学习方向
3. 加载项目全量上下文供 Claude 使用
4. 管理学习 session 生命周期
5. 保存笔记、对话、问题到对应项目目录
6. 搜索已有内容（模式E：问题驱动探索）
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── 导入 portal_agent 共用归档函数 ──────────────────
sys.path.insert(0, str(Path(__file__).parent))
from portal_agent import archive_to_raw


# ==================== 配置 ====================

DEFAULT_VAULT = os.getenv('OBSIDIAN_VAULT', '')
PROJECTS_DIR = '学习'
PRIVATE_SOURCES_DIR = '_private_sources'
LOG_DIR = '_log'
SESSION_FILENAME = '_session.json'
MAP_FILENAME = 'map.md'
QUESTIONS_FILENAME = 'questions.md'
NOTES_SUBDIR = 'notes'
DIALOGUE_SUBDIR = 'dialogue'
HIGHLIGHTS_SUBDIR = 'highlights'

SESSION_TIMEOUT_HOURS = 2
STALE_QUESTION_DAYS = 7
STALE_HIGHLIGHTS_HOURS = 24
STALE_SOURCES_HOURS = 24  # 新素材提醒阈值


# ==================== 工具函数 ====================

def _get_vault(vault_path: str = None) -> Path:
    v = vault_path or DEFAULT_VAULT
    if not v:
        raise ValueError("未指定 vault 路径，请设置 OBSIDIAN_VAULT 环境变量或传入 --vault 参数")
    return Path(v)


def _project_dir(project_name: str, vault_path: str = None) -> Path:
    return _get_vault(vault_path) / PROJECTS_DIR / project_name


def _sources_dir(project_name: str, vault_path: str = None) -> Path:
    return _get_vault(vault_path) / PRIVATE_SOURCES_DIR / project_name


def _now_str() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime('%H:%M')
    except Exception:
        return iso


# ==================== 入口检查 ====================

def check_and_notify(vault_path: str = None) -> str:
    """
    检查四类情况并返回提醒文本（空字符串 = 无需提醒）：
    1. 有未关闭的 session（>2小时）
    2. 有未处理的 highlights（>24小时）
    3. 有 [ ] 问题超过7天未碰
    """
    vault = _get_vault(vault_path)
    projects_root = vault / PROJECTS_DIR
    if not projects_root.exists():
        return ''

    messages = []
    now = datetime.now()

    for proj_dir in sorted(projects_root.iterdir()):
        if not proj_dir.is_dir():
            continue
        name = proj_dir.name

        # 1. 未关闭 session
        session_file = proj_dir / SESSION_FILENAME
        if session_file.exists():
            try:
                session = json.loads(session_file.read_text(encoding='utf-8'))
                last = datetime.fromisoformat(session.get('last_activity', session.get('started_at', '')))
                age_h = (now - last).total_seconds() / 3600
                if age_h > SESSION_TIMEOUT_HOURS:
                    messages.append(f"· [{name}] 上次学习 session 已超过 {int(age_h)} 小时未关闭，要补录吗？")
            except Exception:
                pass

        # 2. 未处理的 highlights
        src_highlights = _sources_dir(name, vault_path) / HIGHLIGHTS_SUBDIR
        if src_highlights.exists():
            for hfile in src_highlights.iterdir():
                if hfile.is_file():
                    age_h = (now - datetime.fromtimestamp(hfile.stat().st_mtime)).total_seconds() / 3600
                    if age_h > STALE_HIGHLIGHTS_HOURS:
                        messages.append(f"· [{name}] 有新的 highlights 已超过 {int(age_h)} 小时未处理")
                        break  # 每个项目只提示一次

        # 3. 搁置过久的开放问题
        questions_file = proj_dir / QUESTIONS_FILENAME
        if questions_file.exists():
            stale_count = 0
            try:
                text = questions_file.read_text(encoding='utf-8')
                for line in text.splitlines():
                    if line.strip().startswith('- [ ]'):
                        # 尝试解析日期（格式：- [ ] 问题内容 <!-- 2026-04-01 -->）
                        import re
                        m = re.search(r'<!--\s*(\d{4}-\d{2}-\d{2})\s*-->', line)
                        if m:
                            q_date = datetime.fromisoformat(m.group(1))
                            if (now - q_date).days > STALE_QUESTION_DAYS:
                                stale_count += 1
                        # 没有日期标注的问题无法判断时间，跳过不算
            except Exception:
                pass
            if stale_count > 0:
                messages.append(f"· [{name}] 有 {stale_count} 个开放问题超过 {STALE_QUESTION_DAYS} 天未推进")

    # 4. 新素材入库（_private_sources/）
    new_sources = check_new_sources(vault_path)
    for proj_name, files in new_sources.items():
        file_list = ', '.join([f['name'] for f in files[:3]])
        if len(files) > 3:
            file_list += f" 等 {len(files)} 个文件"
        messages.append(f"· [{proj_name}] 新素材入库：{file_list}，要现在学习吗？")

    return '\n'.join(messages) if messages else ''


def check_new_sources(vault_path: str = None) -> dict:
    """
    检测 _private_sources/ 下的新素材（文件 mtime > 24 小时）
    返回：{project_name: [file_info, ...]}
    """
    vault = _get_vault(vault_path)
    sources_root = vault / PRIVATE_SOURCES_DIR

    if not sources_root.exists():
        return {}

    new_sources = {}
    now = datetime.now()

    for proj_dir in sorted(sources_root.iterdir()):
        if not proj_dir.is_dir():
            continue

        project_name = proj_dir.name
        files = []

        # 扫描项目下的所有 .md 文件（包括子目录如 highlights/）
        for f in proj_dir.rglob('*.md'):
            if f.is_file():
                age_h = (now - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() / 3600
                if age_h <= STALE_SOURCES_HOURS:
                    # 24 小时内的新文件
                    files.append({
                        'path': str(f.relative_to(vault)),
                        'name': f.stem,
                        'size_kb': f.stat().st_size // 1024,
                        'age_h': int(age_h)
                    })

        if files:
            # 按时间排序，最新的在前
            files.sort(key=lambda x: x['age_h'])
            new_sources[project_name] = files

    return new_sources


def write_sources_log(project_name: str, files: list, vault_path: str = None):
    """
    将新素材入库记录写入 _log/
    """
    vault = _get_vault(vault_path)
    log_file = vault / LOG_DIR / f"{datetime.now().strftime('%Y-%m')}.md"

    # 准备素材表格
    table_rows = []
    for f in files[:10]:  # 最多显示 10 个
        table_rows.append(f"| {f['name']}.md | {f['size_kb']} KB |")

    if len(files) > 10:
        table_rows.append(f"| ... 还有 {len(files) - 10} 个文件 |")

    record = f"""### [{datetime.now().strftime('%Y-%m-%d')}] ingest | {project_name} 素材导入

**来源：** `_private_sources/{project_name}/`

**素材清单：**
| 文件名 | 大小 |
|------|------|
{chr(10).join(table_rows)}

**合计：** {len(files)} 个文件，约 {sum(f['size_kb'] for f in files)} KB

**后续处理：**
- 可通过 `/学习` 触发学习 Agent 处理这些素材
- 复盘 Agent 可从中萃取跨领域洞察

---

"""

    # 追加到 _log/文件（如果文件不存在会创建）
    if log_file.exists():
        content = log_file.read_text(encoding='utf-8')
        # 找到"## 操作记录"后面插入
        if "## 操作记录" in content:
            content = content.replace("## 操作记录\n", f"## 操作记录\n{record}")
        else:
            content += f"\n{record}"
    else:
        content = f"# {datetime.now().strftime('%Y-%m')} 操作日志\n\n> 说明：本文件记录所有 ingest（素材摄入）、query（检索问答）、lint（健康检查）操作\n\n---\n\n{record}"

    log_file.write_text(content, encoding='utf-8')


def check_and_close_stale_session(vault_path: str = None, timeout_hours: int = SESSION_TIMEOUT_HOURS) -> bool:
    """
    关闭所有超时的 session，写入补录记录到 _raw_inbox/。
    返回是否有 session 被关闭。
    """
    vault = _get_vault(vault_path)
    projects_root = vault / PROJECTS_DIR
    if not projects_root.exists():
        return False

    closed_any = False
    now = datetime.now()

    for proj_dir in sorted(projects_root.iterdir()):
        if not proj_dir.is_dir():
            continue
        session_file = proj_dir / SESSION_FILENAME
        if not session_file.exists():
            continue

        try:
            session = json.loads(session_file.read_text(encoding='utf-8'))
            started = datetime.fromisoformat(session.get('started_at', ''))
            last = datetime.fromisoformat(session.get('last_activity', session.get('started_at', '')))
            age_h = (now - last).total_seconds() / 3600
            if age_h <= timeout_hours:
                continue

            # 超时：关闭并补录
            duration_min = int((now - started).total_seconds() / 60)
            mode = session.get('mode', '?')
            new_notes = session.get('new_notes', [])
            resolved_q = session.get('resolved_questions', 0)
            new_q = session.get('new_questions', 0)

            record_session(
                project_name=proj_dir.name,
                duration_min=duration_min,
                mode=mode,
                new_notes=new_notes,
                resolved_q=resolved_q,
                new_q=new_q,
                vault_path=vault_path,
                note_suffix='[自动补录·超时关闭]'
            )
            session_file.unlink()
            closed_any = True

        except Exception as e:
            print(f"关闭 session 失败 ({proj_dir.name}): {e}", file=sys.stderr)

    return closed_any


# ==================== 意图发现 ====================

def list_projects(vault_path: str = None) -> list:
    """
    列出所有项目，含状态摘要。
    返回：[{name, last_visit, open_questions, unprocessed_highlights, has_session, mode_hint}]
    """
    vault = _get_vault(vault_path)
    projects_root = vault / PROJECTS_DIR
    if not projects_root.exists():
        return []

    projects = []
    now = datetime.now()

    for proj_dir in sorted(projects_root.iterdir()):
        if not proj_dir.is_dir():
            continue
        name = proj_dir.name

        # last_visit: 目录最新修改时间
        last_visit = datetime.fromtimestamp(proj_dir.stat().st_mtime).strftime('%Y-%m-%d')

        # open_questions
        open_q = 0
        q_file = proj_dir / QUESTIONS_FILENAME
        if q_file.exists():
            for line in q_file.read_text(encoding='utf-8').splitlines():
                if line.strip().startswith('- [ ]'):
                    open_q += 1

        # unprocessed_highlights
        unprocessed_h = 0
        src_highlights = _sources_dir(name, vault_path) / HIGHLIGHTS_SUBDIR
        if src_highlights.exists():
            for hf in src_highlights.iterdir():
                if hf.is_file():
                    age_h = (now - datetime.fromtimestamp(hf.stat().st_mtime)).total_seconds() / 3600
                    if age_h > STALE_HIGHLIGHTS_HOURS:
                        unprocessed_h += 1

        # has_session
        has_session = (proj_dir / SESSION_FILENAME).exists()

        # mode_hint
        if has_session:
            mode_hint = 'B (继续上次)'
        elif unprocessed_h > 0:
            mode_hint = 'C (处理 highlights)'
        elif open_q > 0:
            mode_hint = 'B (回忆+推进)'
        else:
            mode_hint = 'A (画版图)'

        projects.append({
            'name': name,
            'last_visit': last_visit,
            'open_questions': open_q,
            'unprocessed_highlights': unprocessed_h,
            'has_session': has_session,
            'mode_hint': mode_hint,
        })

    return projects


def recommend_next(vault_path: str = None) -> list:
    """
    返回 top-3 推荐项目，含推荐理由。
    """
    projects = list_projects(vault_path)
    if not projects:
        return []

    # 优先级：有未关闭 session > 有未处理 highlights > 有开放问题 > 按最近访问
    def priority(p):
        score = 0
        if p['has_session']:
            score += 1000
        score += p['unprocessed_highlights'] * 100
        score += p['open_questions'] * 10
        return score

    ranked = sorted(projects, key=priority, reverse=True)[:3]

    result = []
    for p in ranked:
        reasons = []
        if p['has_session']:
            reasons.append('上次 session 未关闭')
        if p['unprocessed_highlights'] > 0:
            reasons.append(f"{p['unprocessed_highlights']} 条 highlights 待处理")
        if p['open_questions'] > 0:
            reasons.append(f"{p['open_questions']} 个开放问题")
        if not reasons:
            reasons.append(f"最近访问：{p['last_visit']}")
        result.append({**p, 'reason': '，'.join(reasons)})

    return result


# ==================== 上下文加载 ====================

def load_context(project_name: str, vault_path: str = None) -> dict:
    """
    全量加载项目上下文，供 Claude 使用。
    返回：{map_content, open_questions, notes_index, recent_dialogue, new_highlights}
    """
    proj = _project_dir(project_name, vault_path)
    vault = _get_vault(vault_path)

    # map.md
    map_file = proj / MAP_FILENAME
    map_content = map_file.read_text(encoding='utf-8') if map_file.exists() else ''

    # open questions
    open_questions = []
    q_file = proj / QUESTIONS_FILENAME
    if q_file.exists():
        for line in q_file.read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('- [ ]'):
                open_questions.append(line.strip()[5:].strip())

    # notes index: 概念名 + 首行摘要
    notes_index = []
    notes_dir = proj / NOTES_SUBDIR
    if notes_dir.exists():
        for note_file in sorted(notes_dir.glob('*.md')):
            concept = note_file.stem
            lines = note_file.read_text(encoding='utf-8').splitlines()
            summary = next((l for l in lines if l.strip() and not l.startswith('#')), '')[:100]
            notes_index.append({'concept': concept, 'summary': summary})

    # recent dialogue: 最近2次，只取摘要（前200字）
    recent_dialogue = []
    dialogue_dir = proj / DIALOGUE_SUBDIR
    if dialogue_dir.exists():
        dialogue_files = sorted(dialogue_dir.glob('*.md'), reverse=True)[:2]
        for df in dialogue_files:
            text = df.read_text(encoding='utf-8')
            recent_dialogue.append({
                'date': df.stem,
                'preview': text[:200] + ('...' if len(text) > 200 else '')
            })

    # new highlights (比 last_visit 新的)
    new_highlights = []
    src_highlights = _sources_dir(project_name, vault_path) / HIGHLIGHTS_SUBDIR
    if src_highlights.exists():
        for hf in sorted(src_highlights.glob('*.md'), key=lambda f: f.stat().st_mtime, reverse=True):
            content = hf.read_text(encoding='utf-8')
            new_highlights.append({'filename': hf.name, 'content': content})

    return {
        'project': project_name,
        'map_content': map_content,
        'open_questions': open_questions,
        'notes_index': notes_index,
        'recent_dialogue': recent_dialogue,
        'new_highlights': new_highlights,
    }


def initialize_project(project_name: str, vault_path: str = None) -> None:
    """
    创建项目目录结构 + 模板文件。
    """
    proj = _project_dir(project_name, vault_path)
    (proj / NOTES_SUBDIR).mkdir(parents=True, exist_ok=True)
    (proj / DIALOGUE_SUBDIR).mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')

    # map.md 模板
    map_file = proj / MAP_FILENAME
    if not map_file.exists():
        map_file.write_text(
            f"# 知识版图 — {project_name}\n\n"
            f"> 创建：{today}\n\n"
            "---\n\n"
            "## 一、专家共识\n\n"
            "## 二、从业者框架\n\n"
            "## 三、根本分歧\n\n"
            "## 四、悬而未决\n",
            encoding='utf-8'
        )

    # questions.md 模板
    q_file = proj / QUESTIONS_FILENAME
    if not q_file.exists():
        q_file.write_text(
            f"# 开放问题 — {project_name}\n\n"
            f"> 创建：{today}\n"
            "> 格式：- [ ] 问题内容 <!-- YYYY-MM-DD -->\n\n"
            "---\n\n",
            encoding='utf-8'
        )

    print(f"项目已初始化：{proj}")


def search_existing(query: str, vault_path: str = None) -> dict:
    """
    模式E：搜索所有项目的 notes/ + map.md + _private_sources/
    返回：{results: [{project, file, snippet}], sources: [{file, snippet}]}
    """
    import re
    vault = _get_vault(vault_path)
    projects_root = vault / PROJECTS_DIR
    sources_root = vault / PRIVATE_SOURCES_DIR

    # 简单关键词匹配（分词后 OR 搜索）
    keywords = [kw.strip().lower() for kw in re.split(r'[\s，,]+', query) if kw.strip()]

    def _matches(text: str) -> bool:
        t = text.lower()
        return any(kw in t for kw in keywords)

    def _snippet(text: str, max_len: int = 200) -> str:
        for kw in keywords:
            idx = text.lower().find(kw)
            if idx >= 0:
                start = max(0, idx - 60)
                end = min(len(text), idx + 140)
                return ('...' if start > 0 else '') + text[start:end] + ('...' if end < len(text) else '')
        return text[:max_len]

    results = []

    if projects_root.exists():
        for proj_dir in sorted(projects_root.iterdir()):
            if not proj_dir.is_dir():
                continue
            name = proj_dir.name

            # map.md
            map_file = proj_dir / MAP_FILENAME
            if map_file.exists():
                text = map_file.read_text(encoding='utf-8')
                if _matches(text):
                    results.append({'project': name, 'file': MAP_FILENAME, 'snippet': _snippet(text)})

            # notes/
            notes_dir = proj_dir / NOTES_SUBDIR
            if notes_dir.exists():
                for note_file in sorted(notes_dir.glob('*.md')):
                    text = note_file.read_text(encoding='utf-8')
                    if _matches(text):
                        results.append({'project': name, 'file': f'notes/{note_file.name}', 'snippet': _snippet(text)})

    # _private_sources/
    sources = []
    if sources_root.exists():
        for src_file in sorted(sources_root.rglob('*.md')):
            try:
                text = src_file.read_text(encoding='utf-8')
                if _matches(text):
                    rel = src_file.relative_to(sources_root)
                    sources.append({'file': str(rel), 'snippet': _snippet(text)})
            except Exception:
                pass

    return {'results': results, 'sources': sources}


# ==================== Session 生命周期 ====================

def open_session(project_name: str, mode: str, vault_path: str = None) -> None:
    """开启学习 session。"""
    proj = _project_dir(project_name, vault_path)
    proj.mkdir(parents=True, exist_ok=True)
    session = {
        'project': project_name,
        'started_at': _now_str(),
        'last_activity': _now_str(),
        'mode': mode,
        'new_notes': [],
        'resolved_questions': 0,
        'new_questions': 0,
        'status': 'open',
    }
    (proj / SESSION_FILENAME).write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"学习 session 已开启：{project_name} [模式{mode}]")


def update_session_activity(project_name: str, vault_path: str = None, **kwargs) -> None:
    """更新 session 活动时间和统计数据。"""
    session_file = _project_dir(project_name, vault_path) / SESSION_FILENAME
    if not session_file.exists():
        return
    session = json.loads(session_file.read_text(encoding='utf-8'))
    session['last_activity'] = _now_str()
    for k, v in kwargs.items():
        if k in ('new_notes',) and isinstance(v, list):
            session[k] = list(set(session.get(k, []) + v))
        elif k in ('resolved_questions', 'new_questions'):
            session[k] = session.get(k, 0) + (v if isinstance(v, int) else 0)
        else:
            session[k] = v
    session_file.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')


def scan_session_changes(project_name: str, vault_path: str = None) -> dict:
    """
    扫描 session 期间的变更：
    - _private_sources/<项目>/ 新增 .md 文件
    - 项目/notes/ 新增 .md
    - 项目/dialogue/ 新增 .md
    返回：{sources: [], notes: [], dialogues: []}
    """
    proj = _project_dir(project_name, vault_path)
    sources = _sources_dir(project_name, vault_path)

    # 读取 session 开始时间
    session_file = proj / SESSION_FILENAME
    if not session_file.exists():
        return {'sources': [], 'notes': [], 'dialogues': []}

    session = json.loads(session_file.read_text(encoding='utf-8'))
    started = datetime.fromisoformat(session.get('started_at', _now_str()))

    changes = {
        'sources': [],
        'notes': [],
        'dialogues': []
    }

    # 扫描 _private_sources/<项目>/
    if sources.exists():
        for f in sources.rglob('*.md'):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > started:
                rel = f.relative_to(sources)
                changes['sources'].append(str(rel))

    # 扫描 notes/
    notes_dir = proj / NOTES_SUBDIR
    if notes_dir.exists():
        for f in notes_dir.glob('*.md'):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > started:
                changes['notes'].append(f'notes/{f.name}')

    # 扫描 dialogue/
    dialogue_dir = proj / DIALOGUE_SUBDIR
    if dialogue_dir.exists():
        for f in dialogue_dir.glob('*.md'):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > started:
                changes['dialogues'].append(f'dialogue/{f.name}')

    return changes


def write_change_log(project_name: str, changes: dict, vault_path: str = None) -> str:
    """
    将变更报告写入 _log/YYYY-MM.md
    返回：写入的文件路径
    """
    vault = _get_vault(vault_path)
    log_dir = vault / '_log'
    log_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    month_file = log_dir / f"{now.strftime('%Y-%m')}.md"

    # 读取现有内容
    existing = ''
    if month_file.exists():
        existing = month_file.read_text(encoding='utf-8')

    # 构建新记录
    timestamp = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')

    lines = [
        f"\n## [{timestamp}] ingest | {project_name} 学习 session",
        f"- 时间：{time_str}",
    ]

    if changes['sources']:
        lines.append("- 新增素材:")
        for s in changes['sources']:
            lines.append(f"  - `_private_sources/{project_name}/{s}`")

    if changes['notes']:
        lines.append("- 新增笔记:")
        for n in changes['notes']:
            lines.append(f"  - `项目/{project_name}/{n}`")

    if changes['dialogues']:
        lines.append("- 新增对话:")
        for d in changes['dialogues']:
            lines.append(f"  - `项目/{project_name}/{d}`")

    if not changes['sources'] and not changes['notes'] and not changes['dialogues']:
        lines.append("- 无新增文件")

    new_entry = '\n'.join(lines) + '\n'

    # 找到"## 操作记录"之后插入
    if '## 操作记录' in existing:
        parts = existing.split('## 操作记录', 1)
        new_content = parts[0] + '## 操作记录\n\n' + new_entry + parts[1]
    else:
        # 没有操作记录章节，在文件末尾添加
        new_content = existing.rstrip() + '\n\n' + new_entry

    month_file.write_text(new_content, encoding='utf-8')

    return str(month_file.relative_to(vault))


def update_map_md(project_name: str, vault_path: str = None) -> str:
    """
    更新项目的 map.md，自动索引项目内的笔记和关系
    返回：map.md 文件路径
    """
    proj = _project_dir(project_name, vault_path)
    map_file = proj / MAP_FILENAME
    notes_dir = proj / NOTES_SUBDIR
    dialogue_dir = proj / DIALOGUE_SUBDIR
    q_file = proj / QUESTIONS_FILENAME

    if not map_file.exists():
        return None

    # 读取现有 map.md 内容
    map_content = map_file.read_text(encoding='utf-8')

    # 扫描所有 notes
    notes_index = []
    if notes_dir.exists():
        for note_file in sorted(notes_dir.glob('*.md')):
            concept = note_file.stem
            lines = note_file.read_text(encoding='utf-8').splitlines()
            # 提取第一个非标题行作为摘要
            summary = next((l for l in lines if l.strip() and not l.startswith('#')), '')[:150]
            notes_index.append({'concept': concept, 'summary': summary})

    # 扫描开放问题
    open_questions = []
    if q_file.exists():
        for line in q_file.read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('- [ ]'):
                open_questions.append(line.strip()[5:].strip())

    # 最近对话
    recent_dialogue = []
    if dialogue_dir.exists():
        for df in sorted(dialogue_dir.glob('*.md'), reverse=True)[:3]:
            text = df.read_text(encoding='utf-8')
            recent_dialogue.append({
                'date': df.stem,
                'preview': text[:200] + ('...' if len(text) > 200 else '')
            })

    # 构建索引部分
    index_section = "## 五、项目索引（自动生成）\n\n"
    index_section += "### 笔记索引\n\n"

    if notes_index:
        index_section += "| 概念 | 摘要 |\n|------|------|\n"
        for note in notes_index:
            index_section += f"| [[notes/{note['concept']}.md]] | {note['summary']} |\n"
    else:
        index_section += "（暂无笔记）\n"

    index_section += "\n### 开放问题\n\n"
    if open_questions:
        for q in open_questions[:10]:
            index_section += f"- [ ] {q}\n"
    else:
        index_section += "（暂无开放问题）\n"

    index_section += "\n### 最近对话\n\n"
    if recent_dialogue:
        for d in recent_dialogue:
            index_section += f"- [[dialogue/{d['date']}.md]] ({d['date']}): {d['preview']}\n"
    else:
        index_section += "（暂无对话记录）\n"

    # 检查是否已有"五、项目索引"部分，有则替换，无则追加
    if "## 五、项目索引" in map_content:
        # 找到下一章节的开始
        parts = map_content.split('## 五、项目索引', 1)
        remaining = parts[1].split('\n\n## ')[1:] if '\n\n## ' in parts[1] else []
        if remaining:
            map_content = parts[0] + index_section + '\n\n## ' + '\n\n## '.join(remaining)
        else:
            map_content = parts[0] + index_section
    else:
        # 追加到末尾
        map_content = map_content.rstrip() + '\n\n' + index_section

    map_file.write_text(map_content, encoding='utf-8')
    return str(map_file.relative_to(_get_vault(vault_path)))


def close_session(project_name: str, vault_path: str = None) -> str:
    """关闭 session，扫描变更写入 _log/，同时写入 _raw_inbox/，更新 map.md，返回摘要文本。"""
    session_file = _project_dir(project_name, vault_path) / SESSION_FILENAME
    if not session_file.exists():
        return f"项目 [{project_name}] 没有进行中的 session"

    session = json.loads(session_file.read_text(encoding='utf-8'))
    started = datetime.fromisoformat(session.get('started_at', _now_str()))
    duration_min = int((datetime.now() - started).total_seconds() / 60)

    # 扫描变更并写入 _log/
    changes = scan_session_changes(project_name, vault_path)
    if changes['sources'] or changes['notes'] or changes['dialogues']:
        log_path = write_change_log(project_name, changes, vault_path)
        print(f"变更报告已写入：{log_path}")

    # 更新 map.md（自动索引项目内的笔记和关系）
    map_path = update_map_md(project_name, vault_path)
    if map_path:
        print(f"map.md 已更新：{map_path}")

    # 写入 _raw_inbox/
    summary = record_session(
        project_name=project_name,
        duration_min=duration_min,
        mode=session.get('mode', '?'),
        new_notes=session.get('new_notes', []),
        resolved_q=session.get('resolved_questions', 0),
        new_q=session.get('new_questions', 0),
        vault_path=vault_path,
    )

    session_file.unlink()
    return summary


# ==================== 输出保存 ====================

def save_note(project_name: str, concept: str, content: str, vault_path: str = None,
              confidence: str = '中') -> str:
    """保存概念笔记到 notes/<概念>.md。"""
    notes_dir = _project_dir(project_name, vault_path) / NOTES_SUBDIR
    notes_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    filename = f"{concept}.md"
    filepath = notes_dir / filename

    # 如果已有笔记，追加新版本
    if filepath.exists():
        existing = filepath.read_text(encoding='utf-8')
        new_content = existing + f"\n\n---\n\n> 更新：{today}（置信度：{confidence}）\n\n{content}\n"
    else:
        new_content = (
            f"# {concept}\n\n"
            f"> 创建：{today}  置信度：{confidence}\n\n"
            f"---\n\n{content}\n"
        )

    filepath.write_text(new_content, encoding='utf-8')

    # 更新 session
    try:
        update_session_activity(project_name, vault_path, new_notes=[concept])
    except Exception:
        pass

    msg = f"笔记已保存：{project_name}/notes/{filename}"
    print(msg)
    return msg


def save_dialogue(project_name: str, content: str, vault_path: str = None) -> str:
    """保存设计/学习对话到 dialogue/YYYY-MM-DD.md。"""
    dialogue_dir = _project_dir(project_name, vault_path) / DIALOGUE_SUBDIR
    dialogue_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    filepath = dialogue_dir / f"{today}.md"

    # append-only
    with open(filepath, 'a', encoding='utf-8') as f:
        if filepath.stat().st_size == 0:
            f.write(f"# 对话记录 — {project_name} — {today}\n\n")
        f.write(content)
        if not content.endswith('\n'):
            f.write('\n')

    msg = f"对话已保存：{project_name}/dialogue/{today}.md"
    print(msg)
    return msg


def append_question(project_name: str, question: str, vault_path: str = None,
                    q_type: str = 'open') -> str:
    """追加开放问题到 questions.md。"""
    proj = _project_dir(project_name, vault_path)
    proj.mkdir(parents=True, exist_ok=True)
    q_file = proj / QUESTIONS_FILENAME

    if not q_file.exists():
        initialize_project(project_name, vault_path)

    today = datetime.now().strftime('%Y-%m-%d')
    with open(q_file, 'a', encoding='utf-8') as f:
        f.write(f"- [ ] {question} <!-- {today} -->\n")

    # 更新 session
    try:
        update_session_activity(project_name, vault_path, new_questions=1)
    except Exception:
        pass

    msg = f"问题已记录：{project_name}/questions.md"
    print(msg)
    return msg


def mark_question_resolved(project_name: str, question_text: str, vault_path: str = None) -> str:
    """将 questions.md 中匹配的 [ ] 改为 [x]。"""
    q_file = _project_dir(project_name, vault_path) / QUESTIONS_FILENAME
    if not q_file.exists():
        return f"找不到 {project_name}/questions.md"

    text = q_file.read_text(encoding='utf-8')
    import re
    # 模糊匹配：问题文本中的关键词
    new_text, count = re.subn(
        r'- \[ \] (' + re.escape(question_text) + r'[^\n]*)',
        r'- [x] \1',
        text
    )
    if count == 0:
        # 宽松匹配
        keywords = question_text.split()[:3]
        pattern = r'- \[ \] ([^\n]*' + re.escape(keywords[0]) + r'[^\n]*)'
        new_text, count = re.subn(pattern, r'- [x] \1', text)

    if count > 0:
        q_file.write_text(new_text, encoding='utf-8')
        try:
            update_session_activity(project_name, vault_path, resolved_questions=1)
        except Exception:
            pass
        msg = f"问题已标记完成：{project_name}/questions.md（{count} 条）"
    else:
        msg = f"未找到匹配问题：{question_text}"

    print(msg)
    return msg


def import_highlights(project_name: str, content: str, vault_path: str = None) -> str:
    """
    将 highlights 内容保存到 _private_sources/<project>/highlights/ 下。
    文件名按时间戳命名。
    """
    highlights_dir = _sources_dir(project_name, vault_path) / HIGHLIGHTS_SUBDIR
    highlights_dir.mkdir(parents=True, exist_ok=True)

    now_str = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    filepath = highlights_dir / f"{now_str}.md"
    filepath.write_text(content, encoding='utf-8')

    msg = f"Highlights 已导入：{filepath.name}"
    print(msg)
    return msg


def record_session(project_name: str, duration_min: int, mode: str,
                   new_notes: list, resolved_q: int, new_q: int,
                   vault_path: str = None, note_suffix: str = '') -> str:
    """将学习 session 摘要写入 _raw_inbox/。"""
    now = datetime.now()
    time_str = now.strftime('%H:%M')

    mode_names = {
        'A': '模式A·画版图',
        'B': '模式B·间隔回忆',
        'C': '模式C·处理Highlights',
        'D': '模式D·复习测试',
        'E': '模式E·问题探索',
        'F': '模式 F·四步学习法',
    }
    mode_label = mode_names.get(mode, f'模式{mode}')
    if note_suffix:
        mode_label += f' {note_suffix}'

    lines = [f"[{time_str}] 学习session: {project_name} (~{duration_min}分钟) [{mode_label}]"]
    if new_notes:
        lines.append(f"· 新笔记: {', '.join(new_notes)}")
    if resolved_q:
        lines.append(f"· 解决问题: {resolved_q}个")
    if new_q:
        lines.append(f"· 新问题: {new_q}个")

    summary = '\n'.join(lines)
    archive_to_raw(summary, vault_path, timestamp=time_str)
    return summary


# ==================== CLI ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='记忆宫殿学习 Agent')
    parser.add_argument('--vault', '-v', type=str, default=DEFAULT_VAULT, help='Vault 路径')
    parser.add_argument('--action', '-a', type=str, required=True,
                        choices=[
                            'check_and_notify',
                            'check_and_close_stale_session',
                            'check_sources',
                            'list',
                            'recommend',
                            'load',
                            'init',
                            'search',
                            'open_session',
                            'close_session',
                            'save_note',
                            'save_dialogue',
                            'append_question',
                            'mark_resolved',
                            'import',
                            'record_session',
                        ],
                        help='执行动作')
    parser.add_argument('--project', '-p', type=str, help='项目名称')
    parser.add_argument('--mode', '-m', type=str, default='A', help='学习模式 (A/B/C/D/E/F)')
    parser.add_argument('--input', '-i', type=str, help='输入内容（highlights / 笔记 / 问题）')
    parser.add_argument('--concept', '-c', type=str, help='概念名称（save_note 用）')
    parser.add_argument('--confidence', type=str, default='中', help='置信度（高/中/低）')
    parser.add_argument('--query', '-q', type=str, help='搜索关键词（search 用）')
    parser.add_argument('--json', dest='output_json', action='store_true', help='以 JSON 格式输出')
    args = parser.parse_args()

    vault = args.vault or DEFAULT_VAULT

    if args.action == 'check_and_notify':
        msg = check_and_notify(vault)
        if msg:
            print(msg)
        else:
            print("✓ 无待处理提醒")

    elif args.action == 'check_and_close_stale_session':
        closed = check_and_close_stale_session(vault)
        print("已关闭超时 session" if closed else "无超时 session")

    elif args.action == 'check_sources':
        new_sources = check_new_sources(vault)
        if not new_sources:
            print("✓ 无新素材")
        else:
            for proj_name, files in new_sources.items():
                print(f"[{proj_name}] 新素材入库：")
                for f in files[:5]:
                    print(f"  · {f['name']}.md ({f['size_kb']} KB, {f['age_h']}小时前)")
                if len(files) > 5:
                    print(f"  ... 还有 {len(files) - 5} 个文件")
                # 自动写入 _log/
                write_sources_log(proj_name, files, vault)
                print(f"  → 已记录到 _log/")

    elif args.action == 'list':
        projects = list_projects(vault)
        if args.output_json:
            print(json.dumps(projects, ensure_ascii=False, indent=2))
        else:
            for p in projects:
                sess = '[session中] ' if p['has_session'] else ''
                print(f"  {sess}{p['name']} | 问题:{p['open_questions']} highlights:{p['unprocessed_highlights']} | 建议:{p['mode_hint']}")

    elif args.action == 'recommend':
        recs = recommend_next(vault)
        if args.output_json:
            print(json.dumps(recs, ensure_ascii=False, indent=2))
        else:
            for r in recs:
                print(f"  [{r['name']}] {r['reason']} → {r['mode_hint']}")

    elif args.action == 'load':
        if not args.project:
            parser.error('--load 需要 --project')
        ctx = load_context(args.project, vault)
        # 自动开启 session（如果尚未开启）
        session_file = _project_dir(args.project, vault) / SESSION_FILENAME
        if not session_file.exists():
            open_session(args.project, args.mode, vault)
        if args.output_json:
            print(json.dumps(ctx, ensure_ascii=False, indent=2))
        else:
            print(f"=== 项目：{ctx['project']} ===")
            print(f"\n[map.md] ({len(ctx['map_content'])} 字)")
            print(ctx['map_content'][:500] + ('...' if len(ctx['map_content']) > 500 else ''))
            print(f"\n[开放问题] {len(ctx['open_questions'])} 个")
            for q in ctx['open_questions']:
                print(f"  · {q}")
            print(f"\n[笔记索引] {len(ctx['notes_index'])} 条")
            for n in ctx['notes_index']:
                print(f"  · {n['concept']}: {n['summary']}")

    elif args.action == 'init':
        if not args.project:
            parser.error('--init 需要 --project')
        initialize_project(args.project, vault)

    elif args.action == 'search':
        if not args.query:
            parser.error('--search 需要 --query')
        results = search_existing(args.query, vault)
        if args.output_json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"搜索「{args.query}」结果：")
            if results['results']:
                print(f"\n[项目内容] {len(results['results'])} 个匹配：")
                for r in results['results']:
                    print(f"  [{r['project']}] {r['file']}: {r['snippet'][:100]}...")
            if results['sources']:
                print(f"\n[原始素材] {len(results['sources'])} 个匹配：")
                for s in results['sources']:
                    print(f"  {s['file']}: {s['snippet'][:100]}...")
            if not results['results'] and not results['sources']:
                print("  未找到相关内容")

    elif args.action == 'open_session':
        if not args.project:
            parser.error('--open_session 需要 --project')
        open_session(args.project, args.mode, vault)

    elif args.action == 'close_session':
        if not args.project:
            parser.error('--close_session 需要 --project')
        print(close_session(args.project, vault))

    elif args.action == 'save_note':
        if not args.project or not args.concept or not args.input:
            parser.error('--save_note 需要 --project --concept --input')
        save_note(args.project, args.concept, args.input, vault, args.confidence)

    elif args.action == 'save_dialogue':
        if not args.project or not args.input:
            parser.error('--save_dialogue 需要 --project --input')
        save_dialogue(args.project, args.input, vault)

    elif args.action == 'append_question':
        if not args.project or not args.input:
            parser.error('--append_question 需要 --project --input')
        append_question(args.project, args.input, vault)

    elif args.action == 'mark_resolved':
        if not args.project or not args.input:
            parser.error('--mark_resolved 需要 --project --input')
        mark_question_resolved(args.project, args.input, vault)

    elif args.action == 'import':
        if not args.project or not args.input:
            parser.error('--import 需要 --project --input')
        import_highlights(args.project, args.input, vault)

    elif args.action == 'record_session':
        if not args.project:
            parser.error('--record_session 需要 --project')
        print(record_session(
            project_name=args.project,
            duration_min=int(args.input or '0'),
            mode=args.mode,
            new_notes=[],
            resolved_q=0,
            new_q=0,
            vault_path=vault,
        ))


if __name__ == '__main__':
    main()
