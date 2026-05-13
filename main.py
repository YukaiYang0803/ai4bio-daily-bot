#!/usr/bin/env python3
"""AI4Bio / BioFM Daily Paper Bot.

Pipeline:
  1. Fetch recent arXiv papers
  2. Broad keyword prefilter
  3. Remove already-sent papers
  4. LLM relevance judge (DeepSeek)
  5. Rank and select top N
  6. Generate Chinese summaries (2-question format)
  7. Build and send email
  8. Save state and logs
"""

import os
import sys
import traceback
from datetime import datetime, timezone

import yaml

from arxiv_fetcher import fetch_papers
from email_sender import send_email
from llm_judge import judge_papers
from ranker import rank_and_select
from state_store import (
    is_already_sent,
    load_seen,
    mark_candidates,
    mark_sent,
    save_daily_log,
)
from summarizer import summarize_papers


def load_config():
    path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def prefilter(papers, keywords):
    """Case-insensitive keyword match on title + abstract."""
    filtered = []
    seen_ids = set()
    for p in papers:
        if p["arxiv_id"] in seen_ids:
            continue
        text = (p["title"] + " " + p["abstract"]).lower()
        if any(kw.lower() in text for kw in keywords):
            filtered.append(p)
            seen_ids.add(p["arxiv_id"])
    return filtered


def build_email(selected_with_summaries, date_str):
    """Build HTML email in screenshot-like 2-question format."""
    n = len(selected_with_summaries)
    lines = []

    # Header
    lines.append(
        f'<p><b>AI4Bio / BioFM 每日精选 · {date_str}</b><br>共 {n} 篇</p>'
    )
    lines.append("<hr>")

    for i, item in enumerate(selected_with_summaries, 1):
        paper = item["paper"]
        summary = item["summary"]

        title = paper.get("title", "Unknown")
        link = paper.get("link", "")
        published = paper.get("published", "")[:10]

        lines.append(f"<p><b>#{i}</b></p>")
        lines.append(f"<p><b>标题:</b> {title}</p>")
        # Render summary with line breaks
        summary_html = summary.replace("\n", "<br>")
        lines.append(f"<p>{summary_html}</p>")
        lines.append(f"<p><b>发表时间:</b> {published}</p>")
        lines.append(f'<p>🔗 <a href="{link}">ArXiv 链接</a></p>')
        lines.append("<hr>")

    # Footer
    lines.append(
        "<p><small>"
        "筛选重点：数据构建、模型架构、representation 设计、"
        "pretraining / post-training / SFT / RL 流程、训练经验、可靠的生物任务评估。"
        "<br>由 DeepSeek 驱动 · 每日自动推送"
        "</small></p>"
    )

    return "\n".join(lines)


def build_no_paper_email(date_str):
    lines = [
        f"<p><b>AI4Bio / BioFM 每日精选 · {date_str}</b></p>",
        "<p>今日无高相关 AI4Bio / BioFM 新论文更新。</p>",
        "<p>已检查方向：</p>",
        "<ol>"
        "<li>Biological foundation model construction</li>"
        "<li>Biological representation learning</li>"
        "<li>Biological design and discovery</li>"
        "<li>Frontier ML for scientific foundation models</li>"
        "</ol>",
        "<p><small>由 DeepSeek 驱动 · 每日自动推送</small></p>",
    ]
    return "\n".join(lines)


def main():
    config = load_config()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== AI4Bio Daily Bot: {today} ===")

    # 1. Fetch
    print("[1/7] Fetching arXiv papers...")
    all_papers = fetch_papers(config)
    print(f"  Fetched {len(all_papers)} papers")

    # 2. Keyword prefilter
    keywords = config["prefilter"]["keywords"]
    candidates = prefilter(all_papers, keywords)
    print(f"  After keyword prefilter: {len(candidates)} papers")

    # 3. Remove already-sent
    fresh = [p for p in candidates if not is_already_sent(p["arxiv_id"])]
    print(f"  After dedup: {len(fresh)} papers")

    # Mark all candidates for tracking
    mark_candidates([p["arxiv_id"] for p in fresh])

    if not fresh:
        print("[*] No new candidates. Sending empty email.")
        body = build_no_paper_email(today)
        subject = f"今日无高相关 AI4Bio / BioFM 新论文，{today}"
        send_email(subject, body, config)
        save_daily_log(today, {"status": "no_candidates", "fetched": len(all_papers)})
        return

    # 4. LLM judge (DeepSeek)
    print(f"[4/7] Judging {len(fresh)} papers with DeepSeek...")
    judgments = judge_papers(fresh, config)

    # 5. Rank and select
    print("[5/7] Ranking papers...")
    selected = rank_and_select(judgments, config)
    print(f"  Selected {len(selected)} papers")

    if not selected:
        print("[*] No papers passed quality threshold. Sending empty email.")
        body = build_no_paper_email(today)
        subject = f"今日无高相关 AI4Bio / BioFM 新论文，{today}"
        send_email(subject, body, config)
        log_data = {
            "status": "none_passed",
            "fetched": len(all_papers),
            "prefiltered": len(candidates),
            "judged": len(judgments),
        }
        save_daily_log(today, log_data)
        return

    # 6. Summarize
    print(f"[6/7] Summarizing {len(selected)} papers...")
    paper_map = {p["arxiv_id"]: p for p in fresh}
    summaries = summarize_papers(selected, paper_map, config)

    # 7. Build and send email
    print("[7/7] Building and sending email...")
    body = build_email(summaries, today)
    n = len(summaries)
    subject = f"AI4Bio / BioFM 每日精选：{n} 篇，{today}"
    send_email(subject, body, config)

    # 8. Save state
    mark_sent([s["paper"]["arxiv_id"] for s in summaries])

    log_data = {
        "status": "ok",
        "fetched": len(all_papers),
        "prefiltered": len(candidates),
        "judged": len(judgments),
        "selected": len(selected),
        "papers": [
            {
                "arxiv_id": s["paper"]["arxiv_id"],
                "title": s["paper"]["title"],
                "score": next(
                    (j.get("_final_score") for j in judgments if j["arxiv_id"] == s["paper"]["arxiv_id"]),
                    None,
                ),
            }
            for s in summaries
        ],
    }
    save_daily_log(today, log_data)

    print(f"=== Done. Sent {n} papers. ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FATAL:", traceback.format_exc())
        sys.exit(1)
