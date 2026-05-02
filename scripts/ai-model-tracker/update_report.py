#!/usr/bin/env python3
"""
处理 web_fetch 结果，更新数据库和报告
"""

import os
import json
import datetime
import sqlite3
from pathlib import Path
from dataclasses import dataclass

DB_PATH = Path(__file__).parent / "tracker.db"
OUTPUT_DIR = Path(__file__).parent / "output"
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")

# web_fetch 收集到的数据
FETCHED_DATA = [
    {
        "url": "https://openai.com/news/",
        "category": "image",
        "source": "OpenAI DALL-E",
        "title": "OpenAI News - GPT-5.5 发布",
        "summary": "Introducing GPT-5.5, GPT-5.5 System Card, GPT-5.5 Bio Bug Bounty, Making ChatGPT better for clinicians"
    },
    {
        "url": "https://stability.ai/news-updates",
        "category": "image",
        "source": "Stability AI",
        "title": "Stability AI News - Brand Studio 发布",
        "summary": "Introducing Brand Studio: The creative production platform powered by your brand"
    },
    {
        "url": "https://openai.com/sora/",
        "category": "video",
        "source": "OpenAI Sora",
        "title": "Sora - Turn your ideas into videos",
        "summary": "Turn your ideas into videos with hyperreal motion and sound. From words to worlds. Create videos with unprecedented realism in any style: cinematic, animated, photorealistic, or surreal."
    },
    {
        "url": "https://klingai.com/",
        "category": "video",
        "source": "Kling AI",
        "title": "KlingAI 3.0 - All-New Series",
        "summary": "All-New KlingAI 3.0 Series. Built on a fully upgraded architecture, VIDEO 3.0 and VIDEO 3.0 Omni natively support deep multimodal instruction parsing and cross-task integration."
    },
    {
        "url": "https://pika.art/",
        "category": "video",
        "source": "Pika Labs",
        "title": "Pika - Reality is optional",
        "summary": "Pika is hiring across different roles. Sign in to use the Pikaformance model."
    },
    {
        "url": "https://lumalabs.ai/",
        "category": "video",
        "source": "Luma AI",
        "title": "Luma - Creative agents that make you prolific",
        "summary": "Luma Agents are the force multiplier for your creative workflow."
    },
    {
        "url": "https://deepmind.google/models/veo/",
        "category": "video",
        "source": "Google Veo 2",
        "title": "Veo 3 - Introducing with expanded creative controls",
        "summary": "Introducing Veo 3, our video generation model with expanded creative controls – including native audio and extended videos. Re-designed for greater realism and fidelity."
    },
    {
        "url": "https://haiper.ai/",
        "category": "video",
        "source": "Haiper AI",
        "title": "Haiper - AI Video Generator",
        "summary": "Haiper AI video generation platform."
    },
]

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

def save_fetched(conn, data):
    c = conn.cursor()
    for item in data:
        c.execute("""
            INSERT INTO model_updates (date, category, source, title, url, summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (TODAY, item["category"], item["source"], item["title"], item["url"], item["summary"]))
    conn.commit()

def get_stats(conn):
    c = conn.cursor()
    stats = {}
    for cat in ["image", "video", "comfy"]:
        c.execute("SELECT COUNT(*) FROM model_updates WHERE date = ? AND category = ?", (TODAY, cat))
        stats[cat] = c.fetchone()[0]
    return stats

def get_all_entries(conn, limit=50):
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
        *[f"- {icon.get(c, '📦')} {c.upper()}: **{stats.get(c, 0)}** 条" for c in ["image", "video", "comfy"]],
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
        for date, cat2, source, title, url, summary, tag in by_cat[cat][:15]:
            tag_str = f"`{tag}` " if tag else ""
            lines.append(f"### {tag_str}{title}")
            lines.append(f"> 来源: **{source}**")
            if summary:
                lines.append(f">{summary[:200]}")
            if url:
                lines.append(f"> 🔗 {url}")
            lines.append("")
    
    return '\n'.join(lines)

def main():
    conn = init_db()
    save_fetched(conn, FETCHED_DATA)
    
    stats = get_stats(conn)
    entries = get_all_entries(conn)
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
            "web_fetch_sources": len(FETCHED_DATA)
        }, f, ensure_ascii=False, indent=2)
    
    print(report)

if __name__ == "__main__":
    main()
