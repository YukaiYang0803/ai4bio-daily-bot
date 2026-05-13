import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests


def fetch_papers(config):
    categories = config["arxiv"]["categories"]
    max_results = config["arxiv"]["max_results"]
    recent_days = config["arxiv"]["recent_days"]

    query = "+OR+".join(f"cat:{c}" for c in categories)
    url = (
        "https://export.arxiv.org/api/query"
        f"?search_query={query}"
        f"&start=0&max_results={max_results}"
        "&sortBy=submittedDate&sortOrder=descending"
    )

    resp = _get_with_retry(url)
    resp.raise_for_status()

    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)

    cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
    papers = []

    for entry in root.findall("a:entry", ns):
        arxiv_id = _extract_id(entry, ns)
        published_dt = _extract_date(entry, "a:published", ns)
        if published_dt and published_dt < cutoff:
            continue

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": _text(entry, "a:title", ns).strip().replace("\n", " "),
                "abstract": _text(entry, "a:summary", ns).strip().replace("\n", " "),
                "authors": _extract_authors(entry, ns),
                "published": published_dt.isoformat() if published_dt else "",
                "published_raw": _text(entry, "a:published", ns),
                "categories": _extract_categories(entry, ns),
                "link": arxiv_id,
            }
        )

    return papers


def _get_with_retry(url, max_retries=3, timeout=90):
    last_error = None
    for attempt in range(max_retries):
        try:
            return requests.get(url, timeout=timeout)
        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                print(f"  ArXiv timeout, retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
    raise last_error


def _text(el, tag, ns):
    child = el.find(tag, ns)
    return child.text or "" if child is not None else ""


def _extract_id(entry, ns):
    id_text = _text(entry, "a:id", ns)
    arxiv_id = id_text.split("/abs/")[-1]
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
