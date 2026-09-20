"""Python-side model router; mirrors src/lib/ai/router.ts tier ladder.

Tier ladder (ascending cost):
  0  Gemma        — free/local, classify + summarize only
  1  MiniMax      — free cloud, light analysis
  2  Kimi K3      — 1M context, strong analysis (moonshotai/kimi-k3)
  3  DeepSeek     — cheap cloud, good reasoning
  4  Haiku        — fast Anthropic, tool-use capable
  5  Sonnet       — Anthropic workhorse (default)
  6  Opus         — Anthropic closer, strategic tasks only

"Tier-up-as-Fable" gated capability (T6/#43): evaluate_tier_up() below
references the SAME tier-2 Kimi route explicitly, for callers who want to
reason about escalating to it (stakes/complexity/long-context) even when
pick_model()'s floor logic would not have reached it on its own. It is a
recommendation function only — never invoked automatically inside
pick_model() — mirrors src/lib/ai/router.ts's evaluateKimiTierUp().

T6/#43 (2026-07-17) bump: tier 2's model_id was the short-form "kimi-k2"
(not a real OpenRouter slug on its own) and ignored the KIMI_MODEL env var
on the knowledge_graph.py fast-path (see _try_kimi below — now fixed). K3
prices at Sonnet-5 parity ($3/$15 per Mtok, verified live via OpenRouter
2026-07-17), so tier 2 is no longer "the cheap one" — its role shifts from
budget-tier to long-context-tier. Mass-enable stays OFF: no agent's assigned
model changed here, only which Kimi variant answers when the Kimi tier fires.

Authoritative tier table also lives in Supabase (`model_routes`).  On boot
we load those rows and cache them; consumers call :func:`pick_model` with a
task descriptor.  The static FALLBACK_LADDER below is used when Supabase is
unavailable (e.g. during _call_cheap_model in knowledge_graph.py).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from supabase import Client, create_client

PrivacyLevel = Literal["public", "internal", "confidential", "restricted"]
Complexity   = Literal["simple", "moderate", "complex"]
Stakes       = Literal["low", "medium", "high"]


@dataclass
class ModelRoute:
    tier: int
    provider: str
    model_id: str
    display_name: str
    in_cost_per_mtok: float
    out_cost_per_mtok: float
    supports_cache: bool
    supports_batch: bool
    supports_files: bool
    min_confidence: float


# ---------------------------------------------------------------------------
# Static fallback ladder — used when Supabase is unavailable.
# Keep in sync with src/lib/ai/router.ts MODEL_CAPABILITIES.
# ---------------------------------------------------------------------------

FALLBACK_LADDER: list[ModelRoute] = [
    ModelRoute(
        tier=0, provider="ollama",
        model_id=os.environ.get("OLLAMA_MODEL", "gemma3:4b"),
        display_name="Gemma (local)",
        in_cost_per_mtok=0.0, out_cost_per_mtok=0.0,
        supports_cache=False, supports_batch=False, supports_files=False,
        min_confidence=0.0,
    ),
    ModelRoute(
        tier=1, provider="minimax",
        model_id=os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01"),
        display_name="MiniMax",
        in_cost_per_mtok=0.0, out_cost_per_mtok=0.0,
        supports_cache=False, supports_batch=False, supports_files=False,
        min_confidence=0.0,
    ),
    ModelRoute(
        tier=2, provider="moonshot",
        # T6/#43 (2026-07-17): default bumped from short-form "kimi-k2" to the
        # confirmed OpenRouter slug moonshotai/kimi-k3. Pricing below verified
        # live via OpenRouter 2026-07-17: $3.00/Mtok in, $15.00/Mtok out.
        model_id=os.environ.get("KIMI_MODEL", "moonshotai/kimi-k3"),
        display_name="Kimi K3 (1M ctx)",
        in_cost_per_mtok=3.0, out_cost_per_mtok=15.0,
        supports_cache=False, supports_batch=False, supports_files=False,
        min_confidence=0.0,
    ),
    ModelRoute(
        tier=3, provider="deepseek",
        model_id=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        display_name="DeepSeek",
        in_cost_per_mtok=0.27, out_cost_per_mtok=1.1,
        supports_cache=False, supports_batch=False, supports_files=False,
        min_confidence=0.0,
    ),
    ModelRoute(
        tier=4, provider="anthropic",
        model_id=os.environ.get("MODEL_HAIKU", "claude-haiku-4-5-20251001"),
        display_name="Haiku",
        in_cost_per_mtok=1.0, out_cost_per_mtok=5.0,
        supports_cache=True, supports_batch=True, supports_files=True,
        min_confidence=0.75,
    ),
    ModelRoute(
        tier=5, provider="anthropic",
        model_id=os.environ.get("MODEL_SONNET", "claude-sonnet-4-6"),
        display_name="Sonnet",
        in_cost_per_mtok=3.0, out_cost_per_mtok=15.0,
        supports_cache=True, supports_batch=True, supports_files=True,
        min_confidence=0.85,
    ),
    ModelRoute(
        tier=6, provider="anthropic",
        model_id=os.environ.get("MODEL_OPUS", "claude-opus-4-6"),
        display_name="Opus",
        in_cost_per_mtok=15.0, out_cost_per_mtok=75.0,
        supports_cache=True, supports_batch=True, supports_files=True,
        min_confidence=0.95,
    ),
]


_CACHE: list[ModelRoute] | None = None


def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def load_routes(force: bool = False) -> list[ModelRoute]:
    """Load model routes from Supabase; fall back to FALLBACK_LADDER on error."""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    try:
        rows = (
            _client()
            .table("model_routes")
            .select("*")
            .eq("enabled", True)
            .order("tier")
            .execute()
        )
        _CACHE = [ModelRoute(**r) for r in rows.data]
        return _CACHE
    except Exception:
        # Supabase unavailable — use static ladder
        _CACHE = FALLBACK_LADDER
        return _CACHE


def pick_model(
    privacy: PrivacyLevel,
    complexity: Complexity,
    min_confidence: float = 0.7,
) -> ModelRoute:
    routes = load_routes()
    allowed = _filter_by_privacy(routes, privacy)
    floor = _tier_floor(complexity, min_confidence)
    for r in allowed:
        if r.tier >= floor:
            return r
    return allowed[-1]


def _filter_by_privacy(routes: list[ModelRoute], privacy: PrivacyLevel) -> list[ModelRoute]:
    if privacy == "public":
        return routes
    if privacy == "internal":
        return [r for r in routes if r.provider == "anthropic"]
    if privacy == "confidential":
        return [r for r in routes if r.provider == "anthropic" and r.tier >= 5]
    if privacy == "restricted":
        return [r for r in routes if r.provider == "ollama"]
    return routes


def _tier_floor(complexity: Complexity, min_confidence: float) -> int:
    if complexity == "complex":
        return 5   # Sonnet minimum for complex tasks
    if complexity == "moderate":
        return 4 if min_confidence > 0.8 else 2   # Haiku or Kimi
    return 0


# ---------------------------------------------------------------------------
# "Tier-up-as-Fable" — a gated escalation capability, NOT a default (T6/#43).
#
# Mirrors src/lib/ai/router.ts's evaluateKimiTierUp(). pick_model()'s normal
# floor logic never reaches tier 2 for complex tasks (floor=5 lands on
# Sonnet first) and Kimi is excluded entirely from the "internal" privacy
# pool (see _filter_by_privacy — provider != "anthropic"). This function is
# the deliberate, explicit path a caller takes to reach Kimi K3 for its 1M
# context window when the task genuinely needs it — never automatic, never
# silently reassigning an agent's configured model.
# ---------------------------------------------------------------------------

KIMI_TIER_UP_TOKEN_THRESHOLD = int(os.environ.get("KIMI_TIER_UP_TOKEN_THRESHOLD", "50000"))


@dataclass
class TierUpEvaluation:
    eligible: bool
    ask_gate: bool
    target: ModelRoute
    reason: str
    cost_delta_in_per_mtok: float


def evaluate_tier_up(
    privacy: PrivacyLevel,
    complexity: Complexity,
    current_pick: ModelRoute,
    estimated_tokens: int = 0,
    stakes: Stakes = "medium",
) -> TierUpEvaluation:
    """Evaluate whether a task should tier up to Kimi K3.

    Pure function — no dispatch, no side effects. `askGate=True` means the
    caller MUST get explicit confirmation before actually spending the
    delta; this function only recommends.
    """
    routes = load_routes()
    kimi_route = next((r for r in routes if r.provider == "moonshot"), None)
    if kimi_route is None:
        return TierUpEvaluation(
            eligible=False, ask_gate=False, target=current_pick,
            reason="no moonshot/kimi route found in model_routes",
            cost_delta_in_per_mtok=0.0,
        )

    cost_delta = kimi_route.in_cost_per_mtok - current_pick.in_cost_per_mtok

    allowed = _filter_by_privacy(routes, privacy)
    if kimi_route not in allowed:
        return TierUpEvaluation(
            eligible=False, ask_gate=False, target=kimi_route,
            reason=f"privacy '{privacy}' excludes the moonshot/kimi provider",
            cost_delta_in_per_mtok=cost_delta,
        )
    if current_pick.model_id == kimi_route.model_id:
        return TierUpEvaluation(
            eligible=False, ask_gate=False, target=kimi_route,
            reason="already on the tier-up target — nothing to escalate",
            cost_delta_in_per_mtok=0.0,
        )

    triggers: list[str] = []
    if stakes == "high":
        triggers.append("stakes='high'")
    if complexity == "complex":
        triggers.append("complexity='complex'")
    if estimated_tokens > KIMI_TIER_UP_TOKEN_THRESHOLD:
        triggers.append(f"estimated_tokens ({estimated_tokens}) > {KIMI_TIER_UP_TOKEN_THRESHOLD}")

    if not triggers:
        return TierUpEvaluation(
            eligible=False, ask_gate=False, target=kimi_route,
            reason="no escalation trigger fired (stakes/complexity/long-context all below threshold)",
            cost_delta_in_per_mtok=cost_delta,
        )

    ask_gate = cost_delta > 0
    reason = f"tier-up eligible: {', '.join(triggers)}"
    if ask_gate:
        reason += (
            f" — pricier than '{current_pick.display_name}' by "
            f"${cost_delta:.2f}/Mtok in; ask-gate required before dispatch"
        )
    else:
        reason += " — no cost penalty vs current pick"

    return TierUpEvaluation(
        eligible=True, ask_gate=ask_gate, target=kimi_route,
        reason=reason, cost_delta_in_per_mtok=cost_delta,
    )


if __name__ == "__main__":
    print("juniper.model_router — tier ladder:")
    for r in FALLBACK_LADDER:
        print(f"  tier={r.tier}  {r.display_name:<22} ({r.provider}) ${r.in_cost_per_mtok}/Mtok in")
