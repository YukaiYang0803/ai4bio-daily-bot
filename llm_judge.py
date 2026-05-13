import json
import os
import re

from openai import OpenAI


def load_judge_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "relevance_judge.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def judge_papers(papers, config):
    llm_cfg = config["llm"]
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=llm_cfg["api_base"],
    )
    prompt_template = load_judge_prompt()

    results = []
    for paper in papers:
        prompt = prompt_template.format(
            title=paper["title"],
            authors=", ".join(paper["authors"][:10]),
            abstract=paper["abstract"],
            arxiv_id=paper["arxiv_id"],
            categories=", ".join(paper.get("categories", [])),
            published=paper.get("published", ""),
            link=paper["link"],
        )

        try:
            response = client.chat.completions.create(
                model=llm_cfg["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=llm_cfg.get("temperature_judge", 0.0),
                max_tokens=llm_cfg.get("max_tokens_judge", 800),
            )
            raw = response.choices[0].message.content
            parsed = _parse_json(raw)
            parsed["arxiv_id"] = paper["arxiv_id"]
            parsed["_raw_judge"] = raw
            results.append(parsed)
        except Exception as e:
            print(f"Judge error for {paper['arxiv_id']}: {e}")
            results.append(
                {
                    "arxiv_id": paper["arxiv_id"],
                    "send": False,
                    "primary_channel": "not_relevant",
                    "topic_relevance": 0,
                    "learning_value": 0,
                    "data_pipeline_value": 0,
                    "architecture_value": 0,
                    "training_pipeline_value": 0,
                    "representation_value": 0,
                    "evaluation_quality": 0,
                    "biological_relevance": 0,
                    "novelty": 0,
                    "quality_risk": "high",
                    "is_mostly_smiles_llm": False,
                    "reason_to_skip": f"LLM judge error: {e}",
                    "_error": True,
                }
            )

    return results


def _parse_json(raw):
    raw = raw.strip()
    # Remove ```json fences
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    # Find JSON object
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"Could not parse JSON from: {raw[:200]}")
