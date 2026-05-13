import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests


def fetch_papers(config):
    categories = config["arxiv"]["categories"]
    max_results = config["arxiv"]["max_results"]
    recent_days = config["arxiv"]["recent_days"]

    query = "+OR+".join(f"cat:{c}" for c in categories)
    url = (
        "http://export.arxiv.org/api/query"
        f"?search_query={query}"
        f"&start=0&max_results={max_results}"
        "&sortBy=submittedDate&sortOrder=descending"
    )

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)

    cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
    papers = []

    for entry in root.findall("a:entry", ns):
        arxiv_id = _extract_id(entry, ns)
        published = _extract_date(entry, "a:published", ns)
        if published and published < cutoff:
            continue

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": _text(entry, "a:title", ns).strip().replace("\n", " "),
                "abstract": _text(entry, "a:summary", ns).strip().replace("\n", " "),
                "authors": _extract_authors(entry, ns),
                "published": published.isoformat() if published else "",
                "categories": _extract_categories(entry, ns),
                "link": arxiv_id,
            }
        )

    return papers


def _text(el, tag, ns):
    child = el.find(tag, ns)
    return child.text or "" if child is not None else ""


def _extract_id(entry, ns):
    id_text = _text(entry, "a:id", ns)
    # "http://arxiv.org/abs/XXXX.XXXXXvN" -> "XXXX.XXXXX"
    arxiv_id = id_text.split("/abs/")[-1]
    # Remove version suffix if present
    if "v" in arxiv_id:
        arxiv_id = arxiv_id.rsplit("v", 1)[0]
    return arxiv_id


def _extract_date(entry, tag, ns):
    text = _text(entry, tag, ns)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_authors(entry, ns):
    return [a.find("a:name", ns).text for a in entry.findall("a:author", ns)]


def _extract_categories(entry, ns):
    return [c.get("term") for c in entry.findall("a:category", ns)]
