"""
JRIH Second Brain — Core LangGraph Agents
Ingest, Gatekeeper, Wiki, Retrieval, Synthesis.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from config import sb, embed, route_model, get_llm, LoopGuard, MODELS


# ═══════════════════════════════════════════════════════════
# SHARED STATE
# ═══════════════════════════════════════════════════════════

class IngestState(TypedDict):
    raw_content: str
    source: str
    filename: str
    classification: dict
    quality_score: float
    embedding: list
    thought_id: str
    status: str

class SearchState(TypedDict):
    query: str
    source_filter: str | None
    results: list
    synthesized: str
    retry_count: int

class SynthesisState(TypedDict):
    period: str
    thoughts: list
    digest: str
    status: str


# ═══════════════════════════════════════════════════════════
# INGEST AGENT
# Trigger: GitHub push to vault/raw/ or n8n Gmail
# Pipeline: Classify → Gate → Embed → Store
# ═══════════════════════════════════════════════════════════

def classify_content(state: IngestState) -> IngestState:
    """Gemma: classify source, type, tags, TTL."""
    content = state['raw_content'][:2000]
    # Use Google AI API (Gemma 4) for classification via GEMMA_API_KEY
    try:
        import requests, os as _os
        _gemma_key = _os.environ.get('GEMMA_API_KEY', '')
        _prompt = f"""Classify this content for a knowledge base. Return JSON only.
Fields: source (one of: jrih, axiom, lumena, aro, personal, content, infra, intel, heart_of_juniper),
entry_type (one of: observation, decision, task, reference, insight, question, flagged),
tags (list of 2-5 keyword tags),
ttl_days (null for permanent, or number of days),
quality_estimate (1-10).

Content:
{content}

JSON:"""
        resp = requests.post(
            'https://generativelanguage.googleapis.com/v1beta/models/gemma-4:generateContent',
            params={'key': _gemma_key},
            json={'contents': [{'parts': [{'text': _prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()  # surface 429 rate-limit errors explicitly
        result = resp.json()['candidates'][0]['content']['parts'][0]['text']
        # Extract JSON from response
        start = result.find('{')
        end = result.rfind('}') + 1
        if start >= 0 and end > start:
            classification = json.loads(result[start:end])
        else:
            classification = {
                'source': state.get('source', 'jrih'),
                'entry_type': 'observation',
                'tags': ['unclassified'],
                'ttl_days': None,
                'quality_estimate': 5,
            }
    except Exception as _gemma_err:
        # Fallback chain: Groq Llama-4-Scout (on 429 rate-limit) → Haiku
        _is_rate_limit = '429' in str(_gemma_err) or (
            hasattr(_gemma_err, 'response') and
            getattr(getattr(_gemma_err, 'response', None), 'status_code', 0) == 429
        )
        _groq_classification = None
        if _is_rate_limit:
            try:
                from langchain_openai import ChatOpenAI as _COAI
                _groq = _COAI(
                    model='meta-llama/llama-4-scout',
                    base_url='https://openrouter.ai/api/v1',
                    api_key=_os.environ.get('OPENROUTER_API_KEY', ''),
                    max_tokens=500,
                )
                _gr = _groq.invoke(
                    f'Classify this content. Return JSON with: source, entry_type, tags, ttl_days, quality_estimate.\nContent: {content}'
                )
                _text = _gr.content
                _s, _e = _text.find('{'), _text.rfind('}') + 1
                if _s >= 0 and _e > _s:
                    _groq_classification = json.loads(_text[_s:_e])
            except Exception:
                pass  # fall through to Haiku

        if _groq_classification:
            classification = _groq_classification
        else:
            # Final fallback: Haiku
            haiku = ChatAnthropic(model=MODELS['haiku'], max_tokens=500)
            resp = haiku.invoke(f"""Classify this content. Return JSON with: source, entry_type, tags, ttl_days, quality_estimate.
Content: {content}""")
            try:
                text = resp.content
                start = text.find('{')
                end = text.rfind('}') + 1
                classification = json.loads(text[start:end])
            except Exception:
                classification = {
                    'source': state.get('source', 'jrih'),
                    'entry_type': 'observation',
                    'tags': ['unclassified'],
                    'ttl_days': None,
                    'quality_estimate': 5,
                }

    state['classification'] = classification
    state['quality_score'] = classification.get('quality_estimate', 5)
    return state


def gatekeeper(state: IngestState) -> IngestState:
    """Quality gate. Score <6 → reject. Dedup check."""
    if state['quality_score'] < 6:
        state['status'] = 'rejected_quality'
        return state

    # Dedup: check cosine similarity against recent entries
    content_preview = state['raw_content'][:500]
    test_embedding = embed(content_preview)

    existing = sb.rpc('hybrid_search', {
        'query_text': content_preview[:200],
        'query_embedding': test_embedding,
        'match_count': 1,
    }).execute()

    if existing.data and len(existing.data) > 0:
        # Check if too similar (cosine > 0.95 is near-duplicate)
        # The RRF score being very high suggests near-duplicate
        top = existing.data[0]
        if top.get('rrf_score', 0) > 0.03:  # Very high RRF = likely duplicate
            state['status'] = 'rejected_duplicate'
            return state

    state['status'] = 'passed'
    return state


def embed_content(state: IngestState) -> IngestState:
    """Generate embedding. Lazy embedding for non-urgent types."""
    classification = state['classification']
    entry_type = classification.get('entry_type', 'observation')

    # Urgent types embed immediately
    urgent = {'decision', 'task', 'flagged', 'insight'}
    if entry_type not in urgent and classification.get('ttl_days'):
        # Non-urgent with TTL — skip embedding, save cost
        state['embedding'] = []
        state['status'] = 'stored_no_embed'
    else:
        state['embedding'] = embed(state['raw_content'])

    return state


def store_thought(state: IngestState) -> IngestState:
    """Write to Supabase thoughts table."""
    if state['status'].startswith('rejected'):
        return state

    classification = state['classification']
    ttl_days = classification.get('ttl_days')

    row = {
        'content': state['raw_content'],
        'source': classification.get('source', 'jrih'),
        'entry_type': classification.get('entry_type', 'observation'),
        'agent': 'ingest-agent',
        'tags': classification.get('tags', ['unclassified']),
        'confidence': state['quality_score'] / 10.0,
        'metadata': {'filename': state.get('filename', ''), 'classification': classification},
    }

    if state['embedding']:
        row['embedding'] = state['embedding']

    if ttl_days:
        row['ttl'] = f"{ttl_days} days"

    result = sb.table('thoughts').insert(row).execute()
    state['thought_id'] = result.data[0]['id'] if result.data else ''
    state['status'] = 'stored'
    return state


def should_continue_ingest(state: IngestState) -> str:
    if state['status'].startswith('rejected'):
        return 'end'
    return 'embed'


# Build Ingest Graph
ingest_builder = StateGraph(IngestState)
ingest_builder.add_node('classify', classify_content)
ingest_builder.add_node('gate', gatekeeper)
ingest_builder.add_node('embed', embed_content)
ingest_builder.add_node('store', store_thought)

ingest_builder.set_entry_point('classify')
ingest_builder.add_edge('classify', 'gate')
ingest_builder.add_conditional_edges('gate', should_continue_ingest, {'embed': 'embed', 'end': END})
ingest_builder.add_edge('embed', 'store')
ingest_builder.add_edge('store', END)

ingest_graph = ingest_builder.compile()


# ═══════════════════════════════════════════════════════════
# RETRIEVAL AGENT
# Hybrid search + retry loop + synthesis.
# ═══════════════════════════════════════════════════════════

def search_brain(state: SearchState) -> SearchState:
    """Hybrid search: BM25 + vector with RRF merge."""
    query_embedding = embed(state['query'])

    results = sb.rpc('hybrid_search', {
        'query_text': state['query'],
        'query_embedding': query_embedding,
        'match_count': 10,
        'source_filter': state.get('source_filter'),
    }).execute()

    state['results'] = results.data or []
    state['retry_count'] = state.get('retry_count', 0)
    return state


def grade_results(state: SearchState) -> str:
    """Grade search results. Retry if poor quality."""
    if not state['results']:
        if state['retry_count'] < 3:
            return 'retry'
        return 'no_results'
    return 'synthesize'


def retry_search(state: SearchState) -> SearchState:
    """Broaden search on retry."""
    state['retry_count'] = state.get('retry_count', 0) + 1
    state['source_filter'] = None  # Remove filter on retry
    return search_brain(state)


def synthesize_results(state: SearchState) -> SearchState:
    """Synthesize search results; model tier scales with result quality confidence."""
    results_text = '\n\n'.join([
        f"[{r['source']}/{r['entry_type']}] (confidence: {r['confidence']}, {r['created_at'][:10]})\n{r['content'][:500]}"
        for r in state['results'][:5]
    ])

    # Derive confidence from avg result score; de-escalates to haiku at high confidence
    _avg_conf = (
        sum(r.get('confidence', 0.5) for r in state['results'][:5]) / min(len(state['results']), 5)
        if state['results'] else 0.3
    )
    _llm = get_llm(route_model('synthesize', confidence=_avg_conf))
    resp = _llm.invoke(f"""Based on the following knowledge base entries, answer this query concisely and accurately.
Cite sources by namespace.

Query: {state['query']}

Knowledge base results:
{results_text}

Answer:""")

    state['synthesized'] = resp.content
    return state


def no_results_response(state: SearchState) -> SearchState:
    state['synthesized'] = f"No results found for: {state['query']}. Consider adding this topic to the brain via raw/ drop."
    return state


# Build Retrieval Graph
retrieval_builder = StateGraph(SearchState)
retrieval_builder.add_node('search', search_brain)
retrieval_builder.add_node('retry', retry_search)
retrieval_builder.add_node('synthesize', synthesize_results)
retrieval_builder.add_node('no_results', no_results_response)

retrieval_builder.set_entry_point('search')
retrieval_builder.add_conditional_edges('search', grade_results, {
    'synthesize': 'synthesize',
    'retry': 'retry',
    'no_results': 'no_results',
})
retrieval_builder.add_conditional_edges('retry', grade_results, {
    'synthesize': 'synthesize',
    'retry': 'retry',
    'no_results': 'no_results',
})
retrieval_builder.add_edge('synthesize', END)
retrieval_builder.add_edge('no_results', END)

retrieval_graph = retrieval_builder.compile()


# ═══════════════════════════════════════════════════════════
# SYNTHESIS AGENT
# Sunday 11pm cron. Weekly digest.
# ═══════════════════════════════════════════════════════════

def gather_week(state: SynthesisState) -> SynthesisState:
    """Pull all thoughts from the past week."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    result = sb.table('thoughts') \
        .select('id, content, source, entry_type, tags, confidence, created_at') \
        .gte('created_at', week_ago) \
        .order('created_at', desc=True) \
        .limit(200) \
        .execute()
    state['thoughts'] = result.data or []
    return state


def synthesize_digest(state: SynthesisState) -> SynthesisState:
    """Sonnet synthesizes weekly digest."""
    if not state['thoughts']:
        state['digest'] = 'No new thoughts this week.'
        state['status'] = 'empty'
        return state

    # Group by source
    by_source = {}
    for t in state['thoughts']:
        src = t['source']
        by_source.setdefault(src, []).append(t)

    summary_parts = []
    for src, items in by_source.items():
        entries = '\n'.join([f"- [{i['entry_type']}] {i['content'][:150]}" for i in items[:10]])
        summary_parts.append(f"## {src} ({len(items)} entries)\n{entries}")

    combined = '\n\n'.join(summary_parts)

    # Weekly digest: default 0.85 confidence stays at sonnet tier (below 0.90 de-escalation threshold)
    _llm = get_llm(route_model('synthesize', confidence=0.85))
    resp = _llm.invoke(f"""Create a weekly digest for JRIH (Juniper Rose Investments & Holdings).
Organize by division. Highlight: decisions made, tasks completed, new insights,
open questions, metrics changes. Flag anything that needs Alan's attention.

Week: {state['period']}
Total entries: {len(state['thoughts'])}

Raw entries by namespace:
{combined}

Weekly Digest:""")

    state['digest'] = resp.content
    state['status'] = 'complete'
    return state


def store_digest(state: SynthesisState) -> SynthesisState:
    """Write digest to Supabase."""
    if state['status'] == 'empty':
        return state

    sb.table('digests').insert({
        'week_label': state['period'],
        'content': state['digest'],
        'sources': [t['id'] for t in state['thoughts'][:50]],
        'agent': 'synthesis-agent',
    }).execute()

    # Also store as a thought for searchability
    sb.table('thoughts').insert({
        'content': state['digest'],
        'source': 'jrih',
        'entry_type': 'insight',
        'agent': 'synthesis-agent',
        'tags': ['digest', 'weekly', state['period']],
        'embedding': embed(state['digest']),
        'confidence': 0.95,
    }).execute()

    return state


# Build Synthesis Graph
synthesis_builder = StateGraph(SynthesisState)
synthesis_builder.add_node('gather', gather_week)
synthesis_builder.add_node('synthesize', synthesize_digest)
synthesis_builder.add_node('store', store_digest)

synthesis_builder.set_entry_point('gather')
synthesis_builder.add_edge('gather', 'synthesize')
synthesis_builder.add_edge('synthesize', 'store')
synthesis_builder.add_edge('store', END)

synthesis_graph = synthesis_builder.compile()


# ═══════════════════════════════════════════════════════════
# WIKI AGENT (stateless helper)
# Triggered post-ingest for entity extraction.
# ═══════════════════════════════════════════════════════════

def extract_entities_and_update_wiki(thought_id: str, content: str):
    """Extract entities from a thought and create/update wiki entries."""
    # Entity extraction: 0.80 confidence → stays at sonnet (no de-escalation)
    _llm = get_llm(route_model('synthesize', confidence=0.80))
    resp = _llm.invoke(f"""Extract named entities from this text. Return JSON array of objects.
Each object: {{"name": "entity name", "type": "person|company|project|concept", "summary": "1-2 sentence summary"}}.
Only extract clearly named entities. Skip generic terms.

Text: {content[:3000]}

JSON:""")

    try:
        text = resp.content
        start = text.find('[')
        end = text.rfind(']') + 1
        entities = json.loads(text[start:end])
    except Exception:
        return []

    def _wiki_brain_capture(content, namespace='system', tags=None):
        try:
            sb.table('thoughts').insert({
                'content': content, 'source': namespace,
                'entry_type': 'observation', 'agent': 'loop_guard',
                'tags': tags or [], 'confidence': 1.0,
            }).execute()
        except Exception:
            pass

    guard = LoopGuard('wiki_entity_loop', max_iterations=30, stall_threshold=8)

    for entity in entities:
        signal = guard.tick(produced_output=False)
        if signal == 'heal':
            params = guard.get_heal_strategy()
            if params['scope'] == 'single_item':
                # Minimal mode: skip this entity to unblock the loop
                guard.tick(produced_output=True)
                continue
        elif signal == 'abort':
            guard.emit_to_brain(_wiki_brain_capture, extra=f'thought_id={thought_id}')
            break

        # Check if wiki entry exists
        existing = sb.table('thoughts') \
            .select('id, content') \
            .eq('source', 'jrih') \
            .eq('entry_type', 'reference') \
            .ilike('content', f"%{entity['name']}%") \
            .contains('tags', ['wiki']) \
            .limit(1) \
            .execute()

        if existing.data:
            # Append-only update: add new info
            old = existing.data[0]
            updated = f"{old['content']}\n\n[{datetime.utcnow().isoformat()[:10]}] (wiki-agent) {entity['summary']}"
            sb.table('thoughts').update({
                'content': updated,
                'embedding': embed(updated),
            }).eq('id', old['id']).execute()
        else:
            # New wiki entry
            wiki_content = f"# {entity['name']}\nType: {entity['type']}\n\n{entity['summary']}\n\n[Source: thought {thought_id}]"
            sb.table('thoughts').insert({
                'content': wiki_content,
                'source': 'jrih',
                'entry_type': 'reference',
                'agent': 'wiki-agent',
                'tags': ['wiki', entity['type'], entity['name'].lower().replace(' ', '_')],
                'embedding': embed(wiki_content),
                'confidence': 0.85,
            }).execute()

        guard.tick(produced_output=True)  # entity successfully processed

    return entities
