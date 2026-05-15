import os
import random
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode

import requests


OAI_BASE_URL = "https://oaipmh.arxiv.org/oai"
OAI_NS = "http://www.openarchives.org/OAI/2.0/"


class ArxivFetchError(RuntimeError):
    pass


def fetch_papers(config):
    """
    Fetch recent arXiv metadata via OAI-PMH, then filter locally.

    This is intentionally different from the arXiv search API path:
    OAI-PMH is the correct interface for daily metadata harvesting.
    """
    arxiv_cfg = config["arxiv"]

    source = arxiv_cfg.get("source", "oai_pmh")
    if source != "oai_pmh":
        raise ValueError(f"Unsupported arxiv.source: {source}")

    recent_days = int(arxiv_cfg.get("recent_days", 3))
    categories = set(arxiv_cfg["categories"])

    from_date = (datetime.now(timezone.utc) - timedelta(days=recent_days)).date().isoformat()
    print(f"  OAI-PMH harvest from datestamp: {from_date}")

    records = _list_records_since(config, from_date=from_date)
    print(f"  OAI-PMH records harvested before local filtering: {len(records)}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
    papers = []
    seen_ids = set()

    for record in records:
        paper = _record_to_paper(record)
        if paper is None:
            continue

        arxiv_id = paper["arxiv_id"]
        if arxiv_id in seen_ids:
            continue

        paper_categories = set(paper.get("categories", []))
        if not paper_categories.intersection(categories):
            continue

        published_dt = _parse_arxiv_date(paper.get("published_raw", ""))
        if published_dt is not None and published_dt < cutoff:
            continue

        papers.append(paper)
        seen_ids.add(arxiv_id)

    papers.sort(key=lambda p: p.get("published", ""), reverse=True)
    return papers


def _list_records_since(config, from_date: str) -> List[ET.Element]:
    records = []
    token = None
    page = 0

    while True:
        page += 1

        if token:
            params = {
                "verb": "ListRecords",
                "resumptionToken": token,
            }
        else:
            params = {
                "verb": "ListRecords",
                "metadataPrefix": "arXiv",
                "from": from_date,
            }

        root = _oai_get_with_retry(config, params=params)

        error = root.find(f".//{{{OAI_NS}}}error")
        if error is not None:
            code = error.attrib.get("code", "")
            message = (error.text or "").strip()
            if code == "noRecordsMatch":
                print("  OAI-PMH returned noRecordsMatch.")
                return records
            raise ArxivFetchError(f"OAI-PMH error: {code}: {message}")

        page_records = root.findall(f".//{{{OAI_NS}}}record")
        print(f"  OAI-PMH page {page}: {len(page_records)} records")
        records.extend(page_records)

        token_el = root.find(f".//{{{OAI_NS}}}resumptionToken")
        token = (token_el.text or "").strip() if token_el is not None else ""

        if not token:
            break

        interval = float(config["arxiv"].get("request_interval_seconds", 3.2))
        print(f"  Sleeping {interval:.1f}s before next OAI-PMH page...")
        time.sleep(interval)

    return records


def _oai_get_with_retry(config, params: Dict[str, str]) -> ET.Element:
    arxiv_cfg = config["arxiv"]
    max_attempts = int(arxiv_cfg.get("max_attempts_per_request", 5))
    timeout = int(arxiv_cfg.get("request_timeout_seconds", 60))
    retry_base = float(arxiv_cfg.get("retry_base_seconds", 20))
    retry_max = float(arxiv_cfg.get("retry_max_seconds", 300))

    contact = os.environ.get("EMAIL_FROM", "").strip()
    if contact:
        user_agent = f"AI4Bio-Daily-Bot/1.0 (mailto:{contact})"
    else:
        user_agent = "AI4Bio-Daily-Bot/1.0"

    headers = {
        "User-Agent": user_agent,
        "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
    }

    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(
                OAI_BASE_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )

            if resp.status_code in {429, 500, 502, 503, 504}:
                last_error = requests.HTTPError(
                    f"{resp.status_code} Server Error for url: {resp.url}",
                    response=resp,
                )
                if attempt < max_attempts:
                    wait = _retry_wait_seconds(resp, attempt, retry_base, retry_max)
                    print(
                        f"  OAI-PMH HTTP {resp.status_code}; "
                        f"retrying in {wait:.1f}s "
                        f"(attempt {attempt}/{max_attempts})..."
                    )
                    time.sleep(wait)
                    continue
                resp.raise_for_status()

            resp.raise_for_status()
            return ET.fromstring(resp.text)

        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < max_attempts:
                wait = _retry_wait_seconds(None, attempt, retry_base, retry_max)
                print(
                    f"  OAI-PMH timeout; retrying in {wait:.1f}s "
                    f"(attempt {attempt}/{max_attempts})..."
                )
                time.sleep(wait)
                continue

        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < max_attempts:
                wait = _retry_wait_seconds(None, attempt, retry_base, retry_max)
                print(
                    f"  OAI-PMH request error: {e}; retrying in {wait:.1f}s "
                    f"(attempt {attempt}/{max_attempts})..."
                )
                time.sleep(wait)
                continue

        except ET.ParseError as e:
            raise ArxivFetchError(f"Could not parse OAI-PMH XML response: {e}") from e

    raise ArxivFetchError(f"OAI-PMH request failed after {max_attempts} attempts: {last_error}")


def _retry_wait_seconds(
    resp: Optional[requests.Response],
    attempt: int,
    retry_base: float,
    retry_max: float,
) -> float:
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), retry_max)
            except ValueError:
                pass

    exponential = min(retry_base * (2 ** (attempt - 1)), retry_max)
    jitter = random.uniform(0, min(10.0, exponential * 0.25))
    return exponential + jitter


def _record_to_paper(record: ET.Element) -> Optional[Dict]:
    header = _first_child_by_localname(record, "header")
    if header is not None and header.attrib.get("status") == "deleted":
        return None

    metadata = _first_child_by_localname(record, "metadata")
    if metadata is None:
        return None

    arxiv_meta = None
    for child in list(metadata):
        if _localname(child.tag) == "arXiv":
            arxiv_meta = child
            break

    if arxiv_meta is None:
        return None

    arxiv_id = _first_text(arxiv_meta, "id").strip()
    if not arxiv_id:
        return None

    title = _clean_text(_first_text(arxiv_meta, "title"))
    abstract = _clean_text(_first_text(arxiv_meta, "abstract"))

    categories_raw = _first_text(arxiv_meta, "categories")
    categories = [c.strip() for c in categories_raw.split() if c.strip()]

    created = _first_text(arxiv_meta, "created").strip()
    updated = _first_text(arxiv_meta, "updated").strip()
    published_raw = created or updated

    published_dt = _parse_arxiv_date(published_raw)
    published = published_dt.isoformat() if published_dt else published_raw

    authors = _extract_authors(arxiv_meta)

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "published": published,
        "published_raw": published_raw,
        "categories": categories,
        "link": f"https://arxiv.org/abs/{arxiv_id}",
    }


def _extract_authors(arxiv_meta: ET.Element) -> List[str]:
    authors_el = _first_child_by_localname(arxiv_meta, "authors")
    if authors_el is None:
        return []

    authors = []
    for author_el in list(authors_el):
        if _localname(author_el.tag) != "author":
            continue

        forenames = _first_text(author_el, "forenames").strip()
        keyname = _first_text(author_el, "keyname").strip()
        suffix = _first_text(author_el, "suffix").strip()

        parts = [p for p in [forenames, keyname, suffix] if p]
        if parts:
            authors.append(" ".join(parts))

    return authors


def _parse_arxiv_date(text: str) -> Optional[datetime]:
    text = (text or "").strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first_text(root: ET.Element, local_name: str) -> str:
    child = _first_child_by_localname(root, local_name)
    if child is None or child.text is None:
        return ""
    return child.text


def _first_child_by_localname(root: ET.Element, local_name: str) -> Optional[ET.Element]:
    for child in root.iter():
        if child is root:
            continue
        if _localname(child.tag) == local_name:
            return child
    return None


def _localname(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())