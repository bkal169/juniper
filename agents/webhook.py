"""
JRIH Second Brain — GitHub Webhook Ingest
Listens for push events and ingests new/modified Markdown files
from the vault into Supabase thoughts table.

Deploy: Railway (same service as cron) or standalone.
"""

import os
import hmac
import hashlib
import json
import re
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from agents.config import sb, embed

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
INGEST_EXTENSIONS = {".md", ".txt"}
IGNORED_PATHS = {"system/", ".github/", "graphify-out/", ".obsidian/"}


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not WEBHOOK_SECRET:
        return True  # No secret configured, accept all (dev mode)
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def extract_namespace(path: str) -> str:
    """Extract namespace from vault file path."""
    parts = path.lower().split("/")
    namespace_map = {
        "raw": "jrih",
        "wiki": "jrih",
        "projects": "jrih",
        "areas": "jrih",
        "resources": "jrih",
        "outputs": "jrih",
        "personal": "personal",
        "rose": "rose",
        "axiom": "axiom",
        "lumena": "lumena",
        "aro": "aro",
        "content": "content",
        "infra": "infra",
        "intel": "intel",
        "hoj": "heart_of_juniper",
        "heart_of_juniper": "heart_of_juniper",
    }
    for part in parts:
        if part in namespace_map:
            return namespace_map[part]
    return "jrih"


def classify_entry_type(content: str, path: str) -> str:
    """Classify the entry type based on content and path."""
    lower = content.lower()
    if "decision:" in lower or "decided" in lower:
        return "decision"
    if "task:" in lower or "todo:" in lower or "- [ ]" in lower:
        return "task"
    if "?" in content[:200]:
        return "question"
    if "wiki/" in path:
        return "reference"
    if "outputs/" in path:
        return "insight"
    return "observation"


def extract_tags(content: str, path: str) -> list:
    """Extract tags from content frontmatter or inline tags."""
    tags = []
    # YAML frontmatter tags
    fm_match = re.search(r"^---\s*\n.*?tags:\s*\[([^\]]+)\].*?---", content, re.DOTALL)
    if fm_match:
        tags.extend([t.strip().strip("'\"") for t in fm_match.group(1).split(",")])
    # Inline #tags
    inline = re.findall(r"#(\w+)", content)
    tags.extend(inline[:10])
    # Path-based
    parts = path.replace(".md", "").split("/")
    tags.extend([p for p in parts if len(p) > 2 and p not in {"raw", "wiki", "outputs"}])
    return list(set(tags))[:15]


def ingest_file(path: str, content: str, commit_sha: str) -> dict:
    """Ingest a single file into Supabase thoughts."""
    namespace = extract_namespace(path)
    entry_type = classify_entry_type(content, path)
    tags = extract_tags(content, path)

    # Check for existing entry from same path (dedup)
    existing = (
        sb.table("thoughts")
        .select("id")
        .eq("metadata->>source_path", path)
        .execute()
    )
    if existing.data:
        # Update existing
        vec = embed(content)
        sb.table("thoughts").update({
            "content": content,
            "embedding": vec,
            "tags": tags,
            "entry_type": entry_type,
            "metadata": {
                "source_path": path,
                "commit_sha": commit_sha,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "ingested_by": "webhook",
            },
        }).eq("id", existing.data[0]["id"]).execute()
        return {"action": "updated", "id": existing.data[0]["id"], "path": path}

    # Insert new
    vec = embed(content)
    row = {
        "content": content,
        "source": namespace,
        "entry_type": entry_type,
        "agent": "webhook-ingest",
        "tags": tags,
        "embedding": vec,
        "confidence": 0.85,
        "metadata": {
            "source_path": path,
            "commit_sha": commit_sha,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "ingested_by": "webhook",
        },
    }
    result = sb.table("thoughts").insert(row).execute()
    return {"action": "inserted", "id": result.data[0]["id"], "path": path}


@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    """Handle GitHub push events."""
    # Verify signature
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, sig):
        return jsonify({"error": "Invalid signature"}), 403

    event = request.headers.get("X-GitHub-Event", "")
    if event != "push":
        return jsonify({"status": "ignored", "event": event}), 200

    payload = request.json
    commits = payload.get("commits", [])
    results = []

    for commit in commits:
        sha = commit.get("id", "")[:8]
        files = commit.get("added", []) + commit.get("modified", [])

        for filepath in files:
            # Skip non-ingestible files
            ext = os.path.splitext(filepath)[1].lower()
            if ext not in INGEST_EXTENSIONS:
                continue
            # Skip ignored paths
            if any(filepath.startswith(ignored) for ignored in IGNORED_PATHS):
                continue

            try:
                # Fetch file content from GitHub API
                repo = payload.get("repository", {}).get("full_name", "")
                ref = payload.get("ref", "").split("/")[-1]
                # Use raw content URL
                import requests as req
                raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{filepath}"
                resp = req.get(raw_url, timeout=10)
                if resp.status_code == 200:
                    result = ingest_file(filepath, resp.text, sha)
                    results.append(result)
            except Exception as e:
                results.append({"action": "error", "path": filepath, "error": str(e)})

    return jsonify({
        "status": "processed",
        "results": results,
        "total": len(results),
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "jrih-webhook-ingest"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
