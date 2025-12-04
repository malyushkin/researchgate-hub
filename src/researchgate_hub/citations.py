# src/researchgate_hub/citations.py

import csv
import json
import os
import time
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

BASE_CITATIONS_URL = (
    "https://www.researchgate.net/"
    "research.tabContainer.ResearchDetailTabCitations.html"
)
BASE_URL = "https://www.researchgate.net"


# -----------------------------------------------------------------------------
# 1. ENV LOADER
# -----------------------------------------------------------------------------

def load_env() -> dict:
    """Load .env from project root."""
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    load_dotenv(env_path)

    return {
        "cookie": os.getenv("RG_COOKIE", ""),
        "user_agent": os.getenv("RG_USER_AGENT", "Mozilla/5.0"),
        "rg_request_token": os.getenv("RG_REQUEST_TOKEN", ""),
        "view_id": os.getenv("RG_VIEW_ID", "DUMMY_VIEW_ID"),
    }


# -----------------------------------------------------------------------------
# 2. REQUEST HELPERS
# -----------------------------------------------------------------------------

def build_headers(env: dict) -> dict:
    return {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": env["user_agent"],
        "Cookie": env["cookie"],
        "rg-request-token": env["rg_request_token"],
        "X-Requested-With": "XMLHttpRequest",
    }


def build_citations_url(publication_id: str, view_id: str) -> str:
    encoded_key = quote(publication_id, safe="")
    return (
        f"{BASE_CITATIONS_URL}"
        f"?publicationKey={encoded_key}"
        f"&adPreview=false"
        f"&viewId={view_id}"
    )


def decode_response(resp: requests.Response) -> dict:
    """Requests already handles gzip/br/zstd, just parse JSON."""
    return resp.json()


# -----------------------------------------------------------------------------
# 3. PARSERS
# -----------------------------------------------------------------------------

def extract_citing_publications(store: dict) -> list[dict]:
    """
    Extract publication objects from store.

    We look for keys like: publication(id:"PB:390527396")
    """
    publications = []

    for key, val in store.items():
        if not key.startswith("publication("):
            continue
        if not isinstance(val, dict):
            continue

        pub_id = val.get("id")
        title = val.get("title")
        url_path = val.get("url")
        full_url = f"{BASE_URL}/{url_path}" if url_path else None

        # Extract fields
        pub_type = val.get("type")
        authors_raw = val.get("authorships") or []
        publication_date = val.get("publicationDate")
        abstract = val.get("abstract")
        doi = val.get("doi")

        authors = [a.get("fullName") for a in authors_raw]

        publications.append(
            {
                "publication_id": pub_id,
                "title": title,
                "url": full_url,
                "type": pub_type,
                "publicationDate": publication_date,
                "authors": authors,
                "abstract": abstract,
                "doi": doi,
            }
        )

    return publications


def extract_citation_edges(store: dict, cited_pub_id: str, topic: str) -> list[dict]:
    """
    Extract edges: cited_pub_id -> citing_publication_id
    using incomingCitingPublicationsWithContext.
    """
    edges: list[dict] = []

    incoming = None
    for key, val in store.items():
        if key.startswith(f'publication(id:"{cited_pub_id}"'):
            incoming = val.get("incomingCitingPublicationsWithContext", {})
            break

    if not incoming:
        return edges

    pages = incoming.get("__pagination__", [])

    for page in pages:
        for entry in page.get("list", []):
            source = entry.get("sourcePublication", {}) or {}
            ref = source.get("__ref__")
            if isinstance(ref, str) and ref.startswith("publication(id:"):
                # example: publication(id:"PB:397094004")
                citing_id = ref.split('"')[1]
                edges.append(
                    {
                        "topic": topic,
                        "cited_publication_id": cited_pub_id,
                        "citing_publication_id": citing_id,
                    }
                )

    return edges


# -----------------------------------------------------------------------------
# 4. MAIN PIPELINE
# -----------------------------------------------------------------------------

def process_citations_for_publications() -> None:
    """
    Read processed/publications_raw.csv, fetch citations for each publication,
    and write two CSV files in processed/:

      - citations_edges.csv
      - citations_publications.csv
    """
    env = load_env()

    processed_dir = Path(__file__).resolve().parent / "processed"
    pubs_csv = processed_dir / "publications_raw.csv"

    edges_csv = processed_dir / "citations_edges.csv"
    citing_pubs_csv = processed_dir / "citations_publications.csv"

    if not pubs_csv.exists():
        raise FileNotFoundError(pubs_csv)

    with pubs_csv.open("r", encoding="utf-8") as f:
        publications = list(csv.DictReader(f))

    all_edges: list[dict] = []
    all_citing_pubs: list[dict] = []

    print(f"Found {len(publications)} publications in {pubs_csv}")

    for row in publications:
        topic = row.get("topic", "")
        pub_id = row["publication_id"]

        url = build_citations_url(pub_id, env["view_id"])
        headers = build_headers(env)

        print(f"\n→ Fetching citations for {pub_id} (topic='{topic}')")
        resp = requests.get(url, headers=headers)

        if resp.status_code != 200:
            print(f"  ! Failed, HTTP {resp.status_code}")
            continue

        data = decode_response(resp)
        store = (
            data.get("result", {})
            .get("state", {})
            .get("rigel", {})
            .get("store", {})
        )

        edges = extract_citation_edges(store, pub_id, topic)
        all_edges.extend(edges)

        citing_pubs = extract_citing_publications(store)
        for cp in citing_pubs:
            cp["topic"] = topic
        all_citing_pubs.extend(citing_pubs)

        print(
            f"  ok: edges={len(edges)}, citing_publications={len(citing_pubs)}"
        )

        time.sleep(1.0)  # simple rate limiting

    # ----- write edges -----
    with edges_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["topic", "cited_publication_id", "citing_publication_id"],
        )
        writer.writeheader()
        for r in all_edges:
            writer.writerow(r)

    # ----- write citing publications -----
    with citing_pubs_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "topic",
                "publication_id",
                "title",
                "type",
                "url",
                "publicationDate",
                "authors",
                "abstract",
                "doi",
            ],
        )
        writer.writeheader()
        for r in all_citing_pubs:
            writer.writerow(r)

    print(
        f"\nSaved {len(all_edges)} edges to {edges_csv} "
        f"and {len(all_citing_pubs)} citing publications to {citing_pubs_csv}"
    )


if __name__ == "__main__":
    process_citations_for_publications()
