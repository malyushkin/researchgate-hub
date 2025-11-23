# src/researchgate_hub/publications.py

import csv
import json
from pathlib import Path
from typing import List, Dict, Any

BASE_URL = "https://www.researchgate.net"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def is_publication_node(key: str, value: Dict[str, Any]) -> bool:
    """Return True if this store entry looks like a Publication node."""
    return key.startswith("publication(") and isinstance(value, dict) and value.get("__typename") == "Publication"


def extract_year(publication_date: str | None) -> int | None:
    """Extract year from ISO datetime string like '2025-11-19T00:00:00+00:00'."""
    if not publication_date:
        return None
    try:
        return int(publication_date[:4])
    except Exception:
        return None


def _build_publication_record_from_node(pub: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw publication dict into a normalized record."""

    pub_id = pub.get("id")
    title = pub.get("title")
    abstract = pub.get("abstract")
    publication_date = pub.get("publicationDate")
    year = extract_year(publication_date)

    url_path = pub.get("url")
    full_url = f"{BASE_URL}/{url_path}" if url_path else None

    journal_title = None
    journal = pub.get("journal")
    if isinstance(journal, dict):
        journal_title = journal.get("title")

    citations_count = pub.get("incomingCitationCount")

    stats = pub.get("stats") or {}
    read_metrics = stats.get("readMetrics") or {}
    read_all = read_metrics.get("all") or {}
    reads_total = read_all.get("total")

    authorships = pub.get("authorships") or []
    authors = []
    for a in authorships:
        full_name = a.get("fullName")
        url = a.get("url")

        author_obj = a.get("author") or {}
        author_id = author_obj.get("id")  # already like "AU:..."

        authors.append(
            {
                "author_id": author_id,
                "full_name": full_name,
                "profile_url": f"{BASE_URL}/{url}" if url else None,
            }
        )

    return {
        "publication_id": pub_id,
        "title": title,
        "abstract": abstract,
        "year": year,
        "publication_date": publication_date,
        "url": full_url,
        "journal_title": journal_title,
        "citations_count": citations_count,
        "reads_total": reads_total,
        "authors": authors,
        "language": None,
        "keywords": None,
        "affiliations": None,
        "countries": None,
        "references_count": None,
    }


# -----------------------------------------------------------------------------
# Core parser
# -----------------------------------------------------------------------------

def extract_publications(rg_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract full publication records from ResearchGate JSON.

    Supports two formats:
    1) "result.state.rigel.store"
    2) "result.data.publicationSearch.nodes"
    """

    publications: List[Dict[str, Any]] = []

    result = rg_json.get("result", {})

    # Format 1: rigel.store
    store = (
        result
        .get("state", {})
        .get("rigel", {})
        .get("store", {})
    )

    if store:
        for key, pub in store.items():
            if not is_publication_node(key, pub):
                continue
            publications.append(_build_publication_record_from_node(pub))

        if publications:
            return publications

    # Format 2: result.data.publicationSearch.nodes
    nodes = (
        result
        .get("data", {})
        .get("publicationSearch", {})
        .get("nodes", [])
    )

    for pub in nodes:
        if not isinstance(pub, dict):
            continue
        if pub.get("__typename") != "Publication":
            continue

        publications.append(_build_publication_record_from_node(pub))

    return publications


# -----------------------------------------------------------------------------
# CSV helpers
# -----------------------------------------------------------------------------

def replace_source_file_rows(
        csv_path: Path,
        source_file: str,
        new_rows: List[Dict[str, Any]],
        fieldnames: List[str],
) -> None:
    """
    Remove all rows having the same source_file, append new ones,
    and overwrite the CSV.
    """
    rows: List[Dict[str, Any]] = []

    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows.extend(r for r in reader if r.get("source_file") != source_file)

    rows.extend(new_rows)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# -----------------------------------------------------------------------------
# Export: raw publications → publications_raw.csv
# -----------------------------------------------------------------------------

def export_raw_publications(
        topic: str,
        json_file_path: str,
        export_folder_path: str | Path | None = None,
) -> None:
    """
    Load saved ResearchGate JSON, extract publications,
    attach topic + source_file, and write to publications_raw.csv.

    Replacement is done by source_file: all rows previously created
    from this JSON file are replaced.
    """
    json_path = Path(json_file_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    source_file = json_path.name

    data = json.loads(json_path.read_text(encoding="utf-8"))
    pubs = extract_publications(data)

    if export_folder_path is None:
        exports_dir = Path(__file__).resolve().parent / "processed"
    else:
        exports_dir = Path(export_folder_path)

    exports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = exports_dir / "publications_raw.csv"

    rows: List[Dict[str, Any]] = [
        {
            "topic": topic,
            "source_file": source_file,
            "publication_id": p["publication_id"],
            "title": p["title"],
            "year": p["year"],
            "url": p["url"],
            "citations_count": p["citations_count"],
        }
        for p in pubs
    ]

    fieldnames = [
        "topic",
        "source_file",
        "publication_id",
        "title",
        "year",
        "url",
        "citations_count",
    ]

    replace_source_file_rows(csv_path, source_file, rows, fieldnames)

    print(
        f"Saved {len(rows)} publications "
        f"for topic='{topic}', source_file='{source_file}' into {csv_path}"
    )
