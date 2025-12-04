import csv
import os
import time
from pathlib import Path
from urllib.parse import quote
from typing import List, Dict, Any, Optional, Set
import concurrent.futures
import json

import requests
from dotenv import load_dotenv

BASE_METADATA_URL = (
    "https://www.researchgate.net/"
    "research.tabContainer.ResearchDetailTabOverview.html"
)
BASE_URL = "https://www.researchgate.net"

MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 3


# -----------------------------------------------------------------------------
# 1. ENV LOADER
# -----------------------------------------------------------------------------

def load_env() -> dict:
    """Load .env variables from project root."""
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


def build_metadata_url(publication_id: str, view_id: str) -> str:
    """Build the API URL for the publication Overview tab."""
    encoded_key = quote(publication_id, safe="")
    return (
        f"{BASE_METADATA_URL}"
        f"?publicationKey={encoded_key}"
        f"&adPreview=false"
        f"&viewId={view_id}"
    )


def decode_response(resp: requests.Response) -> dict:
    """Parse JSON response."""
    return resp.json()


def handle_request(url: str, headers: Dict[str, str], pub_id: str) -> Optional[requests.Response]:
    """Handles requests with retry logic for HTTP 429."""
    delay = INITIAL_RETRY_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 429:
                print(f"  [FAIL] {pub_id}: HTTP 429 (Rate Limit). Pausing {delay}s and retrying...")
                time.sleep(delay)
                delay *= 2
                continue

            if resp.status_code != 200:
                print(f"  [FAIL] {pub_id}: HTTP {resp.status_code}.")
                return None

            return resp

        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] {pub_id}: Request failed on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
            else:
                return None
        except Exception as e:
            print(f"  [ERROR] {pub_id}: Unexpected error: {e}")
            return None

    return None


# -----------------------------------------------------------------------------
# 3. PARSERS & FETCHING
# -----------------------------------------------------------------------------

def extract_publication_metadata(store: dict, pub_id: str) -> dict | None:
    """
    Extract essential metadata from the Rigel store. Abstract is optional.
    """
    target_data = None

    # Find the target publication object within the store
    for key, val in store.items():
        if val.get("id") == pub_id:
            if isinstance(val, dict):
                target_data = val
                break

    if not target_data:
        return None

    # We proceed even if abstract is None
    abstract = target_data.get("abstract")

    numeric_id = pub_id.split(":")[-1]
    full_url = f"{BASE_URL}/publication/{numeric_id}"
    pub_type = target_data.get("type")

    return {
        "publication_id": pub_id,
        "url": full_url,
        "type": pub_type,
        "abstract": abstract,
    }


def fetch_and_extract_metadata(row: Dict[str, Any], env: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Fetches and extracts metadata for a single publication concurrently.
    """
    pub_id = row.get("publication_id")
    if not pub_id:
        return None

    url = build_metadata_url(pub_id, env['view_id'])
    headers = build_headers(env)

    resp = handle_request(url, headers, pub_id)

    if not resp:
        return None

    if '<html>' in resp.text.lower():
        print(f"  [FAIL] {pub_id}: HTML/Cloudflare response received.")
        return None

    try:
        data = decode_response(resp)
    except json.JSONDecodeError:
        print(f"  [FAIL] {pub_id}: Failed to decode JSON response.")
        return None

    store = (
        data.get("result", {}).get("state", {}).get("rigel", {}).get("store", {})
    )

    metadata = extract_publication_metadata(store, pub_id)

    if metadata:
        print(f"  [OK] Metadata extracted for {pub_id}.")
        return metadata
    else:
        print(f"  [WARN] {pub_id}: Metadata object not found in store.")
        return None


# -----------------------------------------------------------------------------
# 4. BATCH SAVING HELPER
# -----------------------------------------------------------------------------

def save_metadata_batch(
        metadata_batch: List[Dict[str, Any]],
        output_path: Path,
        fieldnames: List[str],
        append_mode: bool
):
    """Saves a batch of metadata incrementally to the output file."""

    write_header = not append_mode
    mode = 'a' if append_mode else 'w'

    try:
        with output_path.open(mode, encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if write_header:
                writer.writeheader()

            for row in metadata_batch:
                writer.writerow(row)

        print(
            f"  [SAVE] Batch of {len(metadata_batch)} articles saved to {output_path.name}. Mode: {'Append' if append_mode else 'Write/Overwrite'}")

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to save batch to {output_path}: {e}")
        raise


# -----------------------------------------------------------------------------
# 5. DIFF LOGIC & MAIN PIPELINE
# -----------------------------------------------------------------------------

def get_missing_ids(input_path: Path, output_path: Path) -> List[Dict[str, Any]]:
    """Get list of IDs from input not yet processed in output."""
    with input_path.open("r", encoding="utf-8") as f:
        all_publications = list(csv.DictReader(f))

    processed_ids: Set[str] = set()
    if output_path.exists():
        try:
            with output_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    processed_ids = {row['publication_id'] for row in reader if 'publication_id' in row}
            print(f"Loaded {len(processed_ids)} processed IDs from {output_path.name}.")
        except Exception:
            processed_ids = set()

    missing_publications = [
        row for row in all_publications
        if row.get('publication_id') and row['publication_id'] not in processed_ids
    ]

    return missing_publications


def process_publication_metadata(
        input_csv_path: str,
        output_csv_path: str,
        batch_size: int,
        num_workers: int = 4,
        run_diff: bool = False,
) -> None:
    """
    Main pipeline to read IDs, fetch metadata concurrently, and save incrementally.
    """
    env = load_env()
    input_path = Path(input_csv_path)
    output_path = Path(output_csv_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_fieldnames = [
        "publication_id",
        "url",
        "type",
        "abstract",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if run_diff and output_path.exists():
        publications = get_missing_ids(input_path, output_path)
        print(f"Running in DIFF mode: Found {len(publications)} IDs remaining to process.")
        is_first_batch = False
    else:
        with input_path.open("r", encoding="utf-8") as f:
            publications = list(csv.DictReader(f))
        print(f"Running in FULL mode: Found {len(publications)} total IDs to process.")
        is_first_batch = True

    total_publications = len(publications)
    if total_publications == 0:
        print("No publications to process. Exiting.")
        return

    print(f"Starting processing with batch size: {batch_size}, using {num_workers} thread(s).")

    for i in range(0, total_publications, batch_size):

        batch = publications[i:i + batch_size]
        print(f"\n--- PROCESSING BATCH {i // batch_size + 1} ({len(batch)} items) ---")

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:

            fetch_args = [(row, env) for row in batch]
            future_results = executor.map(lambda p: fetch_and_extract_metadata(p[0], p[1]), fetch_args)

            current_batch_metadata = [
                res for res in future_results if res is not None
            ]

        print(f"  [DEBUG] Batch finished. Successfully extracted {len(current_batch_metadata)} items.")

        if current_batch_metadata:
            save_metadata_batch(
                current_batch_metadata,
                output_path,
                output_fieldnames,
                append_mode=not is_first_batch
            )
            is_first_batch = False

        if (i + batch_size) < total_publications:
            print(f"Pausing for 4 seconds before the next batch...")
            time.sleep(4.0)

    print(f"\n--- PROCESSING COMPLETE ---")
    print(f"Full metadata saved incrementally to {output_path}")


if __name__ == "__main__":
    process_publication_metadata(
        "processed/tmp/unique_ids.csv",
        "processed/publications_overview.csv",
        batch_size=50,
        num_workers=3,
        run_diff=True
    )
