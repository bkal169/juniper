"""Alfred investment intelligence tool — market data, ROI scoring, portfolio snapshots.

Usage:
    from tools.alfred import alfred_market_snapshot, alfred_roi_score, alfred_portfolio_snapshot

    result = alfred_market_snapshot(["SPY", "QQQ", "BTC-USD"])
    if result["ok"]:
        print(result["data"])
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLIST = "SPY,QQQ,BTC-USD"


def _watchlist() -> list[str]:
    raw = os.environ.get("ALFRED_WATCHLIST", _DEFAULT_WATCHLIST)
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def alfred_market_snapshot(symbols: list[str] | None = None) -> dict[str, Any]:
    """Fetch latest price, day change, and volume for each symbol via yfinance."""
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return {"ok": False, "data": None, "error": "yfinance not installed — pip install yfinance"}

    tickers = symbols or _watchlist()
    if not tickers:
        return {"ok": False, "data": None, "error": "No symbols provided"}
    try:
        data: dict[str, Any] = {}
        for sym in tickers:
            ticker = yf.Ticker(sym)
            info = ticker.fast_info
            data[sym] = {
                "price": getattr(info, "last_price", None),
                "prev_close": getattr(info, "previous_close", None),
                "day_change_pct": None,
                "volume": getattr(info, "last_volume", None),
                "currency": getattr(info, "currency", "USD"),
            }
            price = data[sym]["price"]
            prev = data[sym]["prev_close"]
            if price and prev and prev != 0:
                data[sym]["day_change_pct"] = round((price - prev) / prev * 100, 4)
        return {"ok": True, "data": data, "error": None}
    except Exception as exc:
        logger.exception("alfred_market_snapshot failed")
        return {"ok": False, "data": None, "error": str(exc)}


def alfred_roi_score(
    purchase_price: float,
    current_value: float,
    annual_income: float = 0.0,
    hold_years: float = 1.0,
) -> dict[str, Any]:
    """Compute ROI, annualised ROI, and a simple 0-100 score for an investment."""
    try:
        if purchase_price <= 0:
            raise ValueError("purchase_price must be > 0")
        total_gain = (current_value - purchase_price) + (annual_income * hold_years)
        roi = total_gain / purchase_price
        ann_roi = (1 + roi) ** (1 / max(hold_years, 0.001)) - 1
        # Score: clamp ann_roi between -100% and +100%, map to 0-100
        score = round(max(0.0, min(100.0, (ann_roi + 1.0) / 2.0 * 100)), 1)
        return {
            "ok": True,
            "roi": round(roi, 6),
            "annualised_roi": round(ann_roi, 6),
            "score": score,
            "error": None,
        }
    except Exception as exc:
        logger.exception("alfred_roi_score failed")
        return {"ok": False, "roi": None, "annualised_roi": None, "score": None, "error": str(exc)}


def alfred_portfolio_snapshot() -> dict[str, Any]:
    """Fetch market snapshot for the ALFRED_WATCHLIST (or default SPY/QQQ/BTC-USD)."""
    symbols = _watchlist()
    return alfred_market_snapshot(symbols)


def alfred_robinhood_positions() -> dict[str, Any]:
    """STUB — Robinhood integration not yet implemented.

    TODO: Use robin_stocks library with ROBINHOOD_USERNAME / ROBINHOOD_PASSWORD env vars.
    """
    return {
        "ok": False,
        "positions": None,
        "error": "Robinhood integration not yet implemented (stub)",
    }


def alfred_moomoo_positions() -> dict[str, Any]:
    """STUB — Moomoo/Futu integration not yet implemented.

    TODO: Use futu-api with MOOMOO_HOST / MOOMOO_PORT env vars.
    """
    return {
        "ok": False,
        "positions": None,
        "error": "Moomoo integration not yet implemented (stub)",
    }


# ---------------------------------------------------------------------------
# FRED periodic refresh — pull short list of macro series into market_data_cache
# ---------------------------------------------------------------------------

_FRED_SERIES = ("DGS10", "DFF", "UNRATE", "CPIAUCSL")


def alfred_fred_refresh() -> dict[str, Any]:
    """Refresh FRED macro series into market_data_cache via Supabase REST.

    Fetches the latest observation for each series in _FRED_SERIES and upserts
    a row keyed on (symbol, source='FRED') into market_data_cache.

    Env:
        FRED_API_KEY              — required; missing → warn + no-op
        SUPABASE_URL              — required for write
        SUPABASE_SERVICE_ROLE_KEY — required for write
    """
    import httpx
    from datetime import datetime, timezone

    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        logger.warning("[alfred_fred_refresh] FRED_API_KEY not set — skipping refresh")
        return {"ok": False, "refreshed": 0, "error": "FRED_API_KEY missing"}

    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not sb_url or not sb_key:
        logger.warning("[alfred_fred_refresh] SUPABASE_URL/KEY missing — skipping write")
        return {"ok": False, "refreshed": 0, "error": "supabase env missing"}

    refreshed = 0
    errors: list[str] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    tenant = os.environ.get("WL_TENANT_ID", "f2d21a43-4ba7-4f7f-8bf8-49ef986ad3dc")

    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    with httpx.Client(timeout=10.0) as hx:
        for series in _FRED_SERIES:
            try:
                obs = hx.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={
                        "series_id":     series,
                        "api_key":       api_key,
                        "file_type":     "json",
                        "sort_order":    "desc",
                        "limit":         1,
                    },
                )
                obs.raise_for_status()
                data = obs.json().get("observations") or []
                if not data:
                    continue
                row = data[0]
                value = row.get("value")
                obs_date = row.get("date")
                if value in (".", None, "") or not obs_date:
                    continue
                # Upsert into market_data_cache; unique key is (series_id, observation_date)
                hx.post(
                    f"{sb_url}/rest/v1/market_data_cache?on_conflict=series_id,observation_date",
                    headers=headers,
                    json={
                        "series_id":         series,
                        "source":            "FRED",
                        "observation_date":  obs_date,
                        "value":             float(value),
                        "metadata":          {"raw": row},
                        "fetched_at":        now_iso,
                        "wl_tenant_id":      tenant,
                    },
                ).raise_for_status()
                refreshed += 1
            except Exception as exc:
                errors.append(f"{series}: {exc!r}")
                logger.warning("[alfred_fred_refresh] %s failed: %r", series, exc)

    logger.info("[alfred_fred_refresh] refreshed=%d errors=%d", refreshed, len(errors))
    return {"ok": refreshed > 0, "refreshed": refreshed, "error": errors or None}


if __name__ == "__main__":
    import json, sys

    logging.basicConfig(level=logging.INFO)
    print("=== alfred_market_snapshot ===")
    r = alfred_market_snapshot(["SPY", "QQQ"])
    print(json.dumps(r, indent=2))

    print("\n=== alfred_roi_score ===")
    r2 = alfred_roi_score(purchase_price=100_000, current_value=130_000, annual_income=12_000, hold_years=2)
    print(json.dumps(r2, indent=2))
