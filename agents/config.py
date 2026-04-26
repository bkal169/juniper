"""
JRIH Second Brain — Agent Configuration
Model routing, Supabase client, embeddings.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client
from langchain_openai import OpenAIEmbeddings

# ═══════════════════════════════════════════════════════════
# SUPABASE
# ═══════════════════════════════════════════════════════════

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_SERVICE_KEY = os.environ['SUPABASE_SERVICE_KEY']

sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ═══════════════════════════════════════════════════════════
# EMBEDDINGS
# ═══════════════════════════════════════════════════════════

embedder = OpenAIEmbeddings(model='text-embedding-3-small')

def embed(text: str) -> list:
    """Embed text, truncated to 8000 chars for safety."""
    return embedder.embed_query(text[:8000])

# ═══════════════════════════════════════════════════════════
# MODEL ROUTING
# Prime Directive: best+highest use, no wasted movements.
# ═══════════════════════════════════════════════════════════

MODELS = {
    'gemma':  'gemma-4',                  # Google AI API (GEMMA_API_KEY)
    'haiku':  'claude-haiku-4-5',         # Fast, cheap
    'kimi':   'moonshotai/kimi-k2',       # OpenRouter, 128k context
    'sonnet': 'claude-sonnet-4-6',        # Primary workhorse
    'opus':   'claude-opus-4-6',          # The closer
}

# Task → default model tier
TASK_TIER = {
    'classify':     'gemma',
    'grade':        'gemma',
    'filter':       'gemma',
    'route':        'gemma',
    'format':       'haiku',
    'summarize':    'haiku',
    'scaffold':     'haiku',
    'handoff_doc':  'haiku',
    'long_doc':     'kimi',
    'brand_swarm':  'kimi',
    'build':        'sonnet',
    'synthesize':   'sonnet',
    'critique':     'sonnet',
    'reason':       'sonnet',
    'agent_logic':  'sonnet',
    'code_gen':     'sonnet',
    'code_review':  'sonnet',
    'strategy':     'opus',
    'hard_bug':     'opus',
    'architecture': 'opus',
    'foundational': 'opus',
}

TIER_ORDER = ['gemma', 'haiku', 'kimi', 'sonnet', 'opus']

def route_model(task: str, confidence: float = 1.0, complexity: str = 'low', token_count: int = 0) -> str:
    """Route to the right model with escalation + de-escalation + call budget."""
    # Long context → Kimi regardless
    if token_count > 45_000:
        return MODELS['kimi']

    # Critical complexity → always Opus
    if complexity == 'critical':
        tier = _check_call_budget('opus')
        return MODELS.get(tier, MODELS['opus'])

    # Jump straight to Opus on critically low confidence
    if confidence < 0.45:
        tier = _check_call_budget('opus')
        return MODELS.get(tier, MODELS['opus'])

    base_tier = TASK_TIER.get(task, 'haiku')

    # Escalate: low confidence or high complexity → step up one tier
    if confidence < 0.65 or complexity == 'high':
        tier_idx = TIER_ORDER.index(base_tier) if base_tier in TIER_ORDER else 1
        next_tiers = [t for t in TIER_ORDER[tier_idx + 1:] if t != 'kimi']
        if next_tiers:
            base_tier = next_tiers[0]

    # De-escalate: high confidence on non-critical task → step down to haiku floor
    elif confidence >= 0.90 and base_tier not in ('gemma', 'haiku'):
        base_tier = 'haiku'

    tier = _check_call_budget(base_tier)
    return MODELS.get(tier, MODELS['haiku'])


# ═══════════════════════════════════════════════════════════
# JUNIOR ROUTING (cost optimization)
# Haiku for low-stakes at high confidence. Sonnet otherwise.
# ═══════════════════════════════════════════════════════════

LOW_STAKES_ACTIONS = {'memory', 'content', 'research', 'wiki', 'digest'}
HIGH_STAKES_ACTIONS = {'email', 'deploy', 'contract', 'task', 'high_stakes'}

def route_junior(action_type: str, confidence: float) -> str:
    """Route Junior to Haiku (cheap) or Sonnet (real reasoning)."""
    if action_type in LOW_STAKES_ACTIONS and confidence > 0.90:
        return MODELS['haiku']
    return MODELS['sonnet']


# ═══════════════════════════════════════════════════════════
# CONFIDENCE THRESHOLDS
# ═══════════════════════════════════════════════════════════

THRESHOLD_AUTO_EXECUTE = 0.92
THRESHOLD_REVIEW = 0.75
# Below 0.75 → Junior rejects, decision shelved

# ═══════════════════════════════════════════════════════════
# DIVISION ROTATION
# ═══════════════════════════════════════════════════════════

DIVISIONS = ['jri', 'jr_capital', 'jr_realty', 'kintsugi', 'hoj']
DIVISION_NAMES = {
    'jri': 'JRi (AI/SaaS)',
    'jr_capital': 'JR Capital',
    'jr_realty': 'JR Realty',
    'kintsugi': 'Kintsugi Development',
    'hoj': 'Heart of Juniper Foundation',
}

# ═══════════════════════════════════════════════════════════
# NAMESPACES
# ═══════════════════════════════════════════════════════════

NAMESPACES = [
    'personal', 'rose', 'jrih', 'axiom', 'lumena', 'aro',
    'content', 'infra', 'intel', 'heart_of_juniper', 'system', 'metrics',
]

# ═══════════════════════════════════════════════════════════
# SUBAGENT PATTERNS CONFIG
# ═══════════════════════════════════════════════════════════

SUBAGENT_PATTERNS = {
    'brand_swarm': {
        'workers': 5,
        'model': 'kimi',
        'channels': ['linkedin', 'newsletter', 'twitter', 'hoj_instagram', 'hoj_grants'],
        'qa_model': 'sonnet',
        'escalate_to': 'opus',
    },
    'division_scan': {
        'workers': 5,
        'model': 'haiku',
        'divisions': DIVISIONS,
        'merge_model': 'sonnet',
    },
    'research_sprint': {
        'workers': 3,
        'models': ['kimi', 'sonnet', 'haiku'],
        'tasks': ['corpus_ingest', 'brain_search', 'digest_pull'],
        'synthesis_model': 'sonnet',
        'escalate_to': 'opus',
    },
    'intel_scan': {
        'workers': 4,
        'model': 'kimi',
        'domains': ['axiom_competitors', 'florida_realestate', 'finance_regs', 'ai_tooling'],
        'synthesis_model': 'sonnet',
    },
}

# ═══════════════════════════════════════════════════════════
# INFRASTRUCTURE CONSTANTS
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# COST TRACKING (per 1M tokens)
# ═══════════════════════════════════════════════════════════

COST_PER_1M = {
    'gemma':  {'input': 0.00, 'output': 0.00},   # Google AI API free tier
    'haiku':  {'input': 0.80, 'output': 4.00},
    'kimi':   {'input': 1.00, 'output': 3.00},   # OpenRouter: moonshotai/kimi-k2
    'sonnet': {'input': 3.00, 'output': 15.00},
    'opus':   {'input': 15.00, 'output': 75.00},
}

# ═══════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════

ENDPOINTS = {
    'ollama':    os.environ.get('OLLAMA_URL', 'http://localhost:11434'),
    'anthropic': 'https://api.anthropic.com',
    'openrouter': 'https://openrouter.ai/api/v1',
    'openai':    'https://api.openai.com',
}

# ═══════════════════════════════════════════════════════════
# INFRASTRUCTURE CONSTANTS
# ═══════════════════════════════════════════════════════════

def get_kimi_llm(max_tokens: int = 4096):
    """Return a ChatOpenAI client pointed at OpenRouter for Kimi K2 (128k context)."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=MODELS['kimi'],
        api_key=os.environ.get('OPENROUTER_API_KEY'),
        base_url=ENDPOINTS['openrouter'],
        max_tokens=max_tokens,
    )

VERCEL_TEAM_ID = 'team_k9pMkrpQoIolWK5TG0xkDSXD'
NOTION_LIFEOS_PAGE = '23d10dec-72aa-8007-b2d8-d08a989b1db5'
NOTION_SOCIAL_DB = '25710dec-72aa-8116-9146-000b4ef78002'
GMAIL = 'bkalan169@gmail.com'
STAN_STORE = 'stan.store/bkalan169'
N8N_URL = 'bkalan169.app.n8n.cloud'


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING POLICY — escalation / de-escalation thresholds + per-cycle call caps
# ═══════════════════════════════════════════════════════════════════════════════

ROUTING_POLICY = {
    'de_escalate': {
        'threshold':      0.90,   # confidence >= this → step down to haiku
        'max_deescalate': 'haiku',
    },
    'escalate': {
        'low_confidence':      0.65,   # confidence < this → step up one tier
        'critical_confidence': 0.45,   # confidence < this → jump to opus
        'long_context_tokens': 45_000, # token_count > this → use kimi
    },
    # Max model calls allowed within a single Juniper cycle.
    # If over limit, route remaining calls to next cheaper tier.
    'max_calls_per_cycle': {
        'gemma':  20,
        'haiku':  10,
        'kimi':    5,
        'sonnet':  8,
        'opus':    2,
    },
}

_call_counters: dict = {k: 0 for k in ROUTING_POLICY['max_calls_per_cycle']}


def reset_cycle_counters() -> None:
    """Call at the start of each Juniper cycle to reset per-cycle budgets."""
    for k in _call_counters:
        _call_counters[k] = 0

def _check_call_budget(tier: str) -> str:
    """
    Check if `tier` has budget remaining this cycle.
    Steps down to cheaper tier if over limit. Returns resolved tier name.
    """
    budget = ROUTING_POLICY['max_calls_per_cycle']
    order  = ['gemma', 'haiku', 'sonnet', 'opus']
    idx    = order.index(tier) if tier in order else 1
    while idx >= 0:
        t = order[idx]
        if _call_counters.get(t, 0) < budget.get(t, 99):
            _call_counters[t] = _call_counters.get(t, 0) + 1
            return t
        idx -= 1  # step down to cheaper tier
    # Absolute fallback
    _call_counters['haiku'] = _call_counters.get('haiku', 0) + 1
    return 'haiku'


def get_llm(model_str: str):
    """Return a LangChain LLM for the given model string."""
    from langchain_anthropic import ChatAnthropic as _CA
    if model_str.startswith('claude'):
        return _CA(model=model_str)
    if model_str == MODELS['kimi']:
        return get_kimi_llm()
    raise ValueError(f'[get_llm] Unknown model: {model_str}')


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP GUARD — Self-healing loop protection
# On stall: retries up to 3x with progressively lighter params.
# Every abort/heal event is captured as a brain thought for Juniper to learn from.
# ═══════════════════════════════════════════════════════════════════════════════

class LoopGuard:
    """Self-healing loop guard. Stall → heal (lighter params) → abort if all heals fail."""

    def __init__(self, loop_name: str, max_iterations: int = 50, stall_threshold: int = 10):
        self.loop_name             = loop_name
        self.max_iterations        = max_iterations
        self.stall_threshold       = stall_threshold
        self.iteration             = 0
        self.last_output_iteration = 0
        self.heal_attempts         = 0
        self.MAX_HEAL_ATTEMPTS     = 3
        self.current_strategy      = 'normal'

    def tick(self, produced_output: bool = False) -> str:
        """Call once per loop iteration. Returns: 'continue' | 'heal' | 'abort'"""
        self.iteration += 1
        if produced_output:
            self.last_output_iteration = self.iteration
            self.heal_attempts         = 0
            self.current_strategy      = 'normal'

        stalled = (self.iteration - self.last_output_iteration) >= self.stall_threshold
        if self.iteration >= self.max_iterations:
            return 'abort'
        if stalled and self.heal_attempts < self.MAX_HEAL_ATTEMPTS:
            self.heal_attempts         += 1
            self.last_output_iteration  = self.iteration  # reset stall clock
            return 'heal'
        if stalled:
            return 'abort'
        return 'continue'

    def get_heal_strategy(self) -> dict:
        """Returns adjusted params for this heal attempt (lighter on each try)."""
        strategies = {
            1: {'model_tier': 'haiku', 'top_k': 2, 'max_tokens': 512,  'scope': 'reduced'},
            2: {'model_tier': 'gemma', 'top_k': 1, 'max_tokens': 256,  'scope': 'minimal'},
            3: {'model_tier': 'haiku', 'top_k': 1, 'max_tokens': 128,  'scope': 'single_item'},
        }
        return strategies.get(self.heal_attempts, strategies[3])

    def emit_to_brain(self, brain_capture_fn, extra: str = ''):
        """Capture stall/abort event as a brain thought so Juniper can learn."""
        status = 'healed' if self.heal_attempts < self.MAX_HEAL_ATTEMPTS else 'aborted'
        brain_capture_fn(
            content=(
                f'[loop_guard] {self.loop_name} {status} after {self.iteration} iterations, '
                f'{self.heal_attempts} heal attempts. {extra}'
            ),
            namespace='system',
            tags=['loop_stall', self.loop_name, status],
        )


