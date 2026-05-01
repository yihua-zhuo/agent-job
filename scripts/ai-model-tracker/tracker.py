#!/usr/bin/env python3
"""
AI Model & ComfyUI Tracker - 最终版
使用 GitHub API + Raw Content + web_fetch 混合抓取
"""

import os
import json
import datetime
import sqlite3
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

DB_PATH = Path(__file__).parent / "tracker.db"
OUTPUT_DIR = Path(__file__).parent / "output"
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")

# ==================== 数据模型 ====================

@dataclass
class ModelUpdate:
    category: str
    source: str
    title: str
    url: str
    summary: str = ""
    body: str = ""
    tag: str = ""
    author: str = ""
    nodes: int = 0
    raw: Optional[dict] = None

# ==================== 数据库 ====================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS model_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            category TEXT,
            source TEXT,
            title TEXT,
            url TEXT,
            summary TEXT,
            body TEXT,
            tag TEXT,
            raw_json TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS comfy_workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            title TEXT,
            url TEXT,
            author TEXT,
            description TEXT,
            node_count INTEGER,
            raw_json TEXT
        )
    """)
    conn.commit()
    return conn

def save_updates(conn, updates):
    c = conn.cursor()
    for u in updates:
        c.execute("""
            INSERT INTO model_updates (date, category, source, title, url, summary, body, tag, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (TODAY, u.category, u.source, u.title, u.url, u.summary, u.body, u.tag,
              json.dumps(u.raw) if u.raw else None))
    conn.commit()

def save_workflows(conn, workflows):
    c = conn.cursor()
    for w in workflows:
        c.execute("""
            INSERT INTO comfy_workflows (date, title, url, author, description, node_count, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (TODAY, w.title, w.url, w.author, w.description, w.nodes,
              json.dumps(w.raw) if w.raw else None))
    conn.commit()

# ==================== HTTP 工具 ====================

def fetch_url(url: str, max_age: int = 3600) -> Optional[dict]:
    """带 User-Agent 的 HTTP GET，JSON 解析"""
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AI-Model-Tracker/1.0)",
        "Accept": "application/vnd.github.v3+json, application/json, */*"
    })
    with urlopen(req, timeout=15) as r:
        data = r.read()
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None

# ==================== ComfyUI 工作流 ====================

COMFY_BUNDLES_URL = "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/bundles.json"

def fetch_comfy_templates() -> List[ModelUpdate]:
    """获取 ComfyUI 官方工作流模板列表"""
    data = fetch_url(COMFY_BUNDLES_URL)
    if not data or isinstance(data, str):
        return []
    
    updates = []
    
    # bundles.json 结构: {"media-api": [...], "media-image": [...], ...}
    for category, items in data.items():
        cat = "comfy"
        for item in items:
            # 分类标签
            if item.startswith("api_"):
                source = "ComfyAPI"
                title = item.replace("api_", "").replace("_", " ").title()
            elif item.startswith("templates-"):
                source = "ComfyTemplate"
                title = item.replace("templates-", "").replace("_", " ").title()
            elif item.startswith("template-"):
                source = "ComfyTemplate"
                title = item.replace("template-", "").replace("_", " ").title()
            elif item.startswith("utility"):
                source = "ComfyUtility"
                title = item.replace("_", " ").title()
            elif item.startswith("video_"):
                source = "ComfyVideo"
                title = item.replace("_", " ").title()
            elif item.startswith("image_"):
                source = "ComfyImage"
                title = item.replace("_", " ").title()
            else:
                source = "ComfyWorkflow"
                title = item.replace("_", " ").title()
            
            url = f"https://comfy.org/workflows/{item}"
            
            updates.append(ModelUpdate(
                category=cat,
                source=source,
                title=title,
                url=url,
                summary=f"[{category}] {item}",
                raw={"bundle_category": category, "item_name": item}
            ))
    
    return updates

# ==================== GitHub repos ====================

GITHUB_REPOS = {
    "image": [
        "black-forest-labs/FLUX.1",
        "CompVis/stable-diffusion",
        "stability-aws/stable-diffusion",
        "Shakker-Labs/FLUX.1-dev",
    ],
    "video": [
        "Tencent/HunyuanVideo",
        "bytedance/Janus",
        "Higgsfield/mmdirect",
        "minimax-video/minimax-video01",
        "Wiserez/Sora",
        "luosiallen/latent-dialogue",
    ],
    "comfy": [
        "comfyanonymous/ComfyUI",
        "cubiq/ComfyUI_essentials",
        "Fannovel16/ComfyUI-3d-pack",
        "WASasquatch/was-node-suite-comfyui",
        "Dr.LtData/SDXL-ComfyUI-Workflows",
        "Kijai/comfyui-wrapped-sdxl",
    ]
}

def fetch_github_releases(repo: str, max_count: int = 3) -> List[dict]:
    try:
        api_url = f"https://api.github.com/repos/{repo}/releases"
        data = fetch_url(api_url)
        if not data or isinstance(data, str):
            return [{"error": "no data"}]
        
        results = []
        for rel in data[:max_count]:
            results.append({
                "tag": rel.get('tag_name', ''),
                "name": rel.get('name', rel.get('tag_name', '')) or rel.get('tag_name', 'Unnamed'),
                "body": rel.get('body', ''),
                "date": rel.get('published_at', ''),
                "url": rel.get('html_url', ''),
                "author": rel.get('author', {}).get('login', '')
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]

def fetch_github_commits(repo: str, max_count: int = 5) -> List[dict]:
    try:
        api_url = f"https://api.github.com/repos/{repo}/commits"
        data = fetch_url(api_url)
        if not data or isinstance(data, str):
            return [{"error": "no data"}]
        
        results = []
        for commit in data[:max_count]:
            results.append({
                "sha": commit.get('sha', '')[:7],
                "message": commit.get('commit', {}).get('message', '').split('\n')[0],
                "date": commit.get('commit', {}).get('author', {}).get('date', ''),
                "url": commit.get('html_url', ''),
                "author": commit.get('author', {}).get('login', '')
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]

def fetch_github_sources() -> List[ModelUpdate]:
    all_updates = []
    
    for cat, repos in GITHUB_REPOS.items():
        for repo in repos:
            # 先尝试 releases
            releases = fetch_github_releases(repo, max_count=3)
            has_releases = False
            
            for rel in releases:
                if "error" not in rel and rel.get("name") and rel.get("url"):
                    has_releases = True
                    all_updates.append(ModelUpdate(
                        category=cat,
                        source=repo.split('/')[1],
                        title=rel.get("name", "Unnamed"),
                        url=rel.get("url", ""),
                        summary=(rel.get("body") or "")[:300],
                        body=rel.get("body", ""),
                        tag=rel.get("tag", ""),
                        raw=rel
                    ))
            
            # 如果没有 releases，尝试 commits
            if not has_releases:
                commits = fetch_github_commits(repo, max_count=3)
                for c in commits:
                    if "error" not in c and c.get("message"):
                        all_updates.append(ModelUpdate(
                            category=cat,
                            source=repo.split('/')[1],
                            title=c.get("message", "commit")[:80],
                            url=c.get("url", ""),
                            summary=f"Commit {c.get('sha', '')}",
                            body="",
                            raw=c
                        ))
    
    return all_updates

# ==================== 报告 ====================

def get_stats(conn):
    c = conn.cursor()
    stats = {}
    for cat in ["image", "video", "comfy"]:
        c.execute("SELECT COUNT(*) FROM model_updates WHERE date = ? AND category = ?", (TODAY, cat))
        stats[cat] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM comfy_workflows WHERE date = ?", (TODAY,))
    stats["workflows"] = c.fetchone()[0]
    return stats

def get_entries(conn, limit=50):
    c = conn.cursor()
    c.execute("""
        SELECT date, category, source, title, url, summary, tag
        FROM model_updates
        WHERE date = ?
        ORDER BY id DESC LIMIT ?
    """, (TODAY, limit))
    return c.fetchall()

def format_report(stats, entries):
    icon = {"image": "🖼️", "video": "🎬", "comfy": "⚙️"}
    
    lines = [
        f"# 🤖 AI Model & ComfyUI Tracker",
        f"**日期**: {TODAY} | **运行时**: {datetime.datetime.now().strftime('%H:%M:%S')}",
        f"",
        f"## 📊 今日统计",
        f"- 🖼️ IMAGE: **{stats.get('image', 0)}** 条",
        f"- 🎬 VIDEO: **{stats.get('video', 0)}** 条",
        f"- ⚙️ COMFY: **{stats.get('comfy', 0)}** 条",
        f"- 📦 Workflows: **{stats.get('workflows', 0)}** 条",
        f"",
    ]
    
    by_cat = {}
    for e in entries:
        cat = e[1]
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(e)
    
    for cat in ["image", "video", "comfy"]:
        if cat not in by_cat or not by_cat[cat]:
            continue
        lines.append(f"## {icon.get(cat, '📦')} {cat.upper()}")
        for date, cat2, source, title, url, summary, tag in by_cat[cat][:20]:
            tag_str = f"[{tag}] " if tag else ""
            lines.append(f"### {tag_str}{title}")
            lines.append(f"> 来源: **{source}**")
            if summary:
                lines.append(f">{summary[:200]}")
            if url:
                lines.append(f"> 🔗 {url}")
            lines.append("")
    
    return '\n'.join(lines)

# ==================== 主流程 ====================

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    conn = init_db()
    
    print("=" * 55)
    print("🤖 AI Model & ComfyUI Tracker (Final)")
    print("=" * 55)
    
    # 1. ComfyUI 工作流（主要来源）
    print("\n📡 抓取 ComfyUI 官方工作流...")
    comfy_updates = fetch_comfy_templates()
    print(f"   → 获得 {len(comfy_updates)} 条工作流模板")
    
    # 2. GitHub sources
    print("\n📡 抓取 GitHub repos...")
    github_updates = fetch_github_sources()
    print(f"   → 获得 {len(github_updates)} 条更新")
    
    # 3. 保存
    all_updates = comfy_updates + github_updates
    save_updates(conn, all_updates)
    save_workflows(conn, [])
    
    # 4. 报告
    stats = get_stats(conn)
    entries = get_entries(conn)
    report = format_report(stats, entries)
    
    report_path = OUTPUT_DIR / f"report-{TODAY}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    json_path = OUTPUT_DIR / f"data-{TODAY}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "date": TODAY,
            "stats": stats,
            "entries": [list(e) for e in entries],
            "comfy_templates": len(comfy_updates),
            "github_updates": len(github_updates)
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 报告: {report_path}")
    print("\n" + report)

if __name__ == "__main__":
    main()
