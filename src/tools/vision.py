"""Vision image processing tool — property photos, document scans, brand QA.

Usage:
    from tools.vision import vision_analyze_property_photo, vision_scan_document

    result = vision_analyze_property_photo(image_url="https://example.com/photo.jpg")
    if result["ok"]:
        print(result["analysis"])
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_PRIMARY_MODEL = "claude-sonnet-4-6"
_FALLBACK_MODEL = "claude-haiku-4-5-20251001"


def _anthropic_client() -> Any:
    """Return an Anthropic client; raises if ANTHROPIC_API_KEY not set."""
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise RuntimeError("anthropic SDK not installed — pip install anthropic") from exc
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var not set")
    return anthropic.Anthropic(api_key=api_key)


def _image_content(
    image_url: str | None,
    image_base64: str | None,
    media_type: str,
) -> dict[str, Any]:
    """Build the Anthropic image content block."""
    if image_url:
        return {"type": "image", "source": {"type": "url", "url": image_url}}
    if image_base64:
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": image_base64},
        }
    raise ValueError("Either image_url or image_base64 must be provided")


def vision_analyze_property_photo(
    image_url: str | None = None,
    image_base64: str | None = None,
    media_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Analyze a property photo: condition, features, estimated rent band, red flags."""
    try:
        client = _anthropic_client()
        img = _image_content(image_url, image_base64, media_type)
        prompt = (
            "You are a real-estate analyst. Analyze this property photo and respond with "
            "a JSON object containing: condition (string: excellent/good/fair/poor), "
            "features (list of notable features), estimated_rent_band (string range), "
            "red_flags (list), and summary (1-2 sentence overview)."
        )
        response = client.messages.create(
            model=_PRIMARY_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": [img, {"type": "text", "text": prompt}]}],
        )
        raw = response.content[0].text.strip()
        # Try to parse JSON; fall back to returning raw text
        try:
            analysis = json.loads(raw)
        except json.JSONDecodeError:
            analysis = {"raw": raw}
        return {"ok": True, "analysis": analysis, "model": _PRIMARY_MODEL, "error": None}
    except Exception as exc:
        logger.exception("vision_analyze_property_photo failed")
        return {"ok": False, "analysis": None, "model": None, "error": str(exc)}


def vision_scan_document(
    image_base64: str,
    media_type: str = "image/jpeg",
    goal: str = "Extract all text and key data fields from this document.",
) -> dict[str, Any]:
    """OCR + structured extraction from a document image."""
    try:
        client = _anthropic_client()
        img = _image_content(None, image_base64, media_type)
        prompt = (
            f"{goal}\n"
            "Return a JSON object with: text (full extracted text as string), "
            "fields (dict of key/value pairs found), document_type (string), confidence (high/medium/low)."
        )
        response = client.messages.create(
            model=_PRIMARY_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": [img, {"type": "text", "text": prompt}]}],
        )
        raw = response.content[0].text.strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"text": raw, "fields": {}, "document_type": "unknown", "confidence": "low"}
        return {"ok": True, "result": result, "model": _PRIMARY_MODEL, "error": None}
    except Exception as exc:
        logger.exception("vision_scan_document failed")
        return {"ok": False, "result": None, "model": None, "error": str(exc)}


def vision_brand_qa(
    image_base64: str,
    media_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Check a marketing image for brand guideline compliance (logo, colors, typography)."""
    try:
        client = _anthropic_client()
        img = _image_content(None, image_base64, media_type)
        prompt = (
            "You are a brand quality-assurance reviewer. Inspect this marketing image and "
            "respond with a JSON object containing: pass (boolean), issues (list of strings "
            "describing any brand violations), suggestions (list of improvement suggestions), "
            "and overall_score (0-100 integer)."
        )
        response = client.messages.create(
            model=_PRIMARY_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": [img, {"type": "text", "text": prompt}]}],
        )
        raw = response.content[0].text.strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"raw": raw}
        return {"ok": True, "result": result, "model": _PRIMARY_MODEL, "error": None}
    except Exception as exc:
        logger.exception("vision_brand_qa failed")
        return {"ok": False, "result": None, "model": None, "error": str(exc)}


if __name__ == "__main__":
    import json, sys

    logging.basicConfig(level=logging.INFO)
    # Quick smoke-test with a public image URL
    TEST_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Fronalpstock_big.jpg/320px-Fronalpstock_big.jpg"
    print("=== vision_analyze_property_photo (URL) ===")
    r = vision_analyze_property_photo(image_url=TEST_URL)
    print(json.dumps(r, indent=2, default=str))
