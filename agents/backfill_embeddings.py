"""
JRIH Second Brain — Embedding Backfill
Finds all thoughts with NULL embeddings, generates them via OpenAI,
and updates the rows in Supabase.

Usage:
    export SUPABASE_URL="https://obtoinsjncbqdqgdeddl.supabase.co"
    export SUPABASE_SERVICE_KEY="<your_key>"
    export OPENAI_API_KEY="<your_key>"
    python agents/backfill_embeddings.py
"""

import os
import json
import time
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://obtoinsjncbqdqgdeddl.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OPENAI_KEY = os.environ["OPENAI_API_KEY"]

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def get_null_embedding_rows():
    """Fetch all thoughts where embedding is NULL."""
    url = f"{SUPABASE_URL}/rest/v1/thoughts"
    params = {
        "select": "id,content",
        "embedding": "is.null",
        "order": "created_at.asc",
    }
    resp = requests.get(url, headers=HEADERS_SB, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def embed_text(text: str) -> list:
    """Call OpenAI text-embedding-3-small."""
    resp = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "text-embedding-3-small",
            "input": text[:8000],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def update_embedding(thought_id: str, embedding: list):
    """PATCH the embedding column for a single thought."""
    url = f"{SUPABASE_URL}/rest/v1/thoughts"
    params = {"id": f"eq.{thought_id}"}
    body = {"embedding": embedding}
    resp = requests.patch(url, headers=HEADERS_SB, params=params, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    rows = get_null_embedding_rows()
    total = len(rows)
    print(f"[backfill] Found {total} thoughts with NULL embeddings.")

    if total == 0:
        print("[backfill] Nothing to do.")
        return

    success = 0
    errors = 0

    for i, row in enumerate(rows, 1):
        try:
            content = row["content"]
            vec = embed_text(content)
            update_embedding(row["id"], vec)
            success += 1
            print(f"  [{i}/{total}] embedded: {content[:60]}...")
            # Rate limit: OpenAI free tier = 3 RPM, paid = 3500+ RPM
            # Sleep 0.5s to be safe without being slow
            time.sleep(0.5)
        except Exception as e:
            errors += 1
            print(f"  [{i}/{total}] ERROR: {e}")

    print(f"\n[backfill] Done. Success: {success}, Errors: {errors}")


if __name__ == "__main__":
    main()
