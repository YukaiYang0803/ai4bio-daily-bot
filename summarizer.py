import os

from openai import OpenAI


def load_summary_prompt():
    prompt_path = os.path.join(
        os.path.dirname(__file__), "prompts", "summary_generator.txt"
    )
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def summarize_paper(paper, paper_data, config):
    """Generate 2-question Chinese digest for one paper.

    paper: dict with arxiv_id, title, abstract, authors, published, link
    paper_data: the full metadata (for extra fields if needed)
    config: full config dict
    """
    llm_cfg = config["llm"]
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=llm_cfg["api_base"],
    )
    prompt_template = load_summary_prompt()

    prompt = prompt_template
    prompt = prompt.replace("{title}", paper["title"])
    prompt = prompt.replace("{authors}", ", ".join(paper["authors"][:8]))
    prompt = prompt.replace("{abstract}", paper["abstract"][:2000])
    prompt = prompt.replace("{link}", paper["link"])
    prompt = prompt.replace("{published}", paper.get("published", ""))

    try:
        response = client.chat.completions.create(
            model=llm_cfg["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=llm_cfg.get("temperature_summary", 0.3),
            max_tokens=llm_cfg.get("max_tokens_summary", 600),
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Summary error for {paper['arxiv_id']}: {e}")
        return f"1. 这篇论文要解决的核心问题是什么？\n（摘要生成失败：{e}）\n\n2. 它的关键思路或结论是什么？\n（摘要生成失败）"


def summarize_papers(selected, paper_map, config):
    summaries = []
    for p in selected:
        aid = p["arxiv_id"]
        full = paper_map.get(aid, {})
        summary = summarize_paper(full, p, config)
        summaries.append({"paper": full, "summary": summary})
    return summaries
