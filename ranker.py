def rank_and_select(papers_with_judgments, config):
    sel = config["selection"]
    weights = config["scoring"]
    max_papers = sel["max_papers"]

    candidates = []
    for p in papers_with_judgments:
        # Reject if LLM judge had error
        if p.get("_error"):
            continue
        # Reject if send=false
        if not p.get("send", False):
            continue
        # Reject if quality_risk is high
        if p.get("quality_risk") == "high":
            continue

        # SMILES penalty
        smiles_penalty = 0
        if p.get("is_mostly_smiles_llm", False):
            smiles_penalty = -2
            # Reject if both eval and novelty are low
            if p.get("evaluation_quality", 0) < 4 and p.get("novelty", 0) < 4:
                continue

        # Compute final score
        score = (
            weights.get("topic_relevance", 2.0) * p.get("topic_relevance", 0)
            + weights.get("learning_value", 2.0) * p.get("learning_value", 0)
            + weights.get("data_pipeline_value", 1.5) * p.get("data_pipeline_value", 0)
            + weights.get("architecture_value", 1.5) * p.get("architecture_value", 0)
            + weights.get("training_pipeline_value", 1.5) * p.get("training_pipeline_value", 0)
            + weights.get("representation_value", 1.3) * p.get("representation_value", 0)
            + weights.get("evaluation_quality", 1.2) * p.get("evaluation_quality", 0)
            + weights.get("biological_relevance", 1.0) * p.get("biological_relevance", 0)
            + weights.get("novelty", 1.0) * p.get("novelty", 0)
            + (_quality_penalty(p.get("quality_risk")))
            + smiles_penalty
        )

        p["_final_score"] = round(score, 1)
        candidates.append(p)

    # Sort by score descending
    candidates.sort(key=lambda x: x["_final_score"], reverse=True)

    # Select top N
    selected = candidates[:max_papers]
    return selected


def _quality_penalty(risk):
    if risk == "medium":
        return -2
    return 0
