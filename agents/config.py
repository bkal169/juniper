"""
JRIH Second Brain — Agent Configuration
Model routing, Supabase client, embeddings.
"""

import os
from supabase import create_client, Client
from langchain_openai import OpenAIEmbeddings

# ═══════════════════════════════════════════════════════════
# SUPABASE
# ═══════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://ubdhpacoqmlxudcvhyuu.supabase.co')
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
    'gemma':  'claude-haiku-4-5-20251001',          # haiku fallback (Ollama not on Railway)
    'haiku':  'claude-haiku-4-5-20251001',         # Fast, cheap
    'kimi':   'kimi-k2',         # Long-doc + swarm
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
    """Route to the right model. No wasted tokens."""
    # Long doc always goes to Kimi
    if token_count > 50_000:
        return MODELS['kimi']

    # Critical always goes to Opus
    if complexity == 'critical':
        return MODELS['opus']

    base_tier = TASK_TIER.get(task, 'haiku')

    # Escalate on low confidence or high complexity
    if confidence < 0.75 or complexity == 'high':
        tier_idx = TIER_ORDER.index(base_tier) if base_tier in TIER_ORDER else 1
        # Skip kimi (it's for volume, not reasoning)
        next_tiers = [t for t in TIER_ORDER[tier_idx + 1:] if t != 'kimi']
        if next_tiers:
            base_tier = next_tiers[0]

    return MODELS.get(base_tier, MODELS['haiku'])


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
THRESHOLD_AUTO_EXECUTE_LOW = 0.85          # Phase 12.x — memory-only auto-execute floor
LOW_STAKES_AUTO = {'memory'}               # action_types eligible for the lower threshold
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
    'gemma':  {'input': 0.00, 'output': 0.00},   # Local Ollama
    'haiku':  {'input': 0.80, 'output': 4.00},
    'kimi':   {'input': 0.60, 'output': 2.00},
    'sonnet': {'input': 3.00, 'output': 15.00},
    'opus':   {'input': 15.00, 'output': 75.00},
}

# ═══════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════

ENDPOINTS = {
    'ollama':    os.environ.get('OLLAMA_URL', 'http://localhost:11434'),
    'anthropic': 'https://api.anthropic.com',
    'moonshot':  'https://api.moonshot.cn',
    'openai':    'https://api.openai.com',
}

# ═══════════════════════════════════════════════════════════
# INFRASTRUCTURE CONSTANTS
# ═══════════════════════════════════════════════════════════

VERCEL_TEAM_ID = 'team_k9pMkrpQoIolWK5TG0xkDSXD'
NOTION_LIFEOS_PAGE = '23d10dec-72aa-8007-b2d8-d08a989b1db5'
NOTION_SOCIAL_DB = '25710dec-72aa-8116-9146-000b4ef78002'
GMAIL = 'bkalan169@gmail.com'
STAN_STORE = 'stan.store/bkalan169'
N8N_URL = 'bkalan169.app.n8n.cloud'


