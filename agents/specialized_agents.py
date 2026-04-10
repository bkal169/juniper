"""
JRIH — Specialized Agents
Competitive Intel (Wednesday), HOJ (3x/week), Claude Advisor (Monday + on-demand).
"""

import json
from datetime import datetime, timedelta
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic

from config import sb, embed, MODELS


# ═══════════════════════════════════════════════════════════
# COMPETITIVE INTEL AGENT
# Wednesday cron. 4 parallel domain scanners.
# ═══════════════════════════════════════════════════════════

INTEL_DOMAINS = {
    'axiom_competitors': 'AxiomOS competitors: Procore, Autodesk, Briq, Northspyre, Doxel. Track product launches, pricing, partnerships, funding.',
    'florida_realestate': 'Florida real estate market: Sarasota focus. Interest rates, inventory, price trends, new developments, zoning changes.',
    'finance_regulations': 'Financial services regulations: MLO, 2-15 insurance, DAC funding, Series 7, 4-40. New compliance, rule changes.',
    'ai_tooling': 'AI tooling landscape: LangChain, LangGraph, Claude, OpenAI, local models, vector DBs, agent frameworks. New releases, pricing changes.',
}


class IntelState(TypedDict):
    domain: str
    scan_prompt: str
    findings: str
    status: str


def scan_domain(state: IntelState) -> IntelState:
    """Scan a single domain for changes. Uses Sonnet (reasoning needed)."""
    # Pull existing intel for context
    existing = sb.table('thoughts') \
        .select('content, created_at') \
        .eq('source', 'intel') \
        .contains('tags', [state['domain']]) \
        .order('created_at', desc=True) \
        .limit(5) \
        .execute()

    context = '\n'.join([f"[{e['created_at'][:10]}] {e['content'][:200]}" for e in (existing.data or [])])

    sonnet = ChatAnthropic(model=MODELS['sonnet'], max_tokens=1500)
    resp = sonnet.invoke(f"""You are the Competitive Intelligence Agent for JRIH.
Scan this domain and report what's changed or notable.

Domain: {state['domain']}
Focus: {state['scan_prompt']}

Previous intel (for delta detection):
{context or 'No previous intel.'}

Based on your training data, report:
1. What's new or changed in this domain?
2. What matters to JRIH specifically?
3. Any threats or opportunities?
4. Confidence in each finding (high/medium/low).

Be specific. No filler. Delta only — don't repeat what's already known.""")

    state['findings'] = resp.content
    state['status'] = 'scanned'
    return state


def store_intel(state: IntelState) -> IntelState:
    """Store intel findings in brain with 30-day TTL."""
    sb.table('thoughts').insert({
        'content': f"INTEL [{state['domain']}]: {state['findings']}",
        'source': 'intel',
        'entry_type': 'observation',
        'agent': 'competitive-intel',
        'tags': ['intel', state['domain'], 'weekly'],
        'embedding': embed(state['findings']),
        'confidence': 0.7,
        'ttl': '30 days',
    }).execute()
    state['status'] = 'stored'
    return state


def run_intel_scan():
    """Run all 4 domain scans and merge."""
    print(f"\n[Intel] Starting weekly scan — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")

    all_findings = []
    for domain, prompt in INTEL_DOMAINS.items():
        print(f"  Scanning: {domain}...")
        state = {'domain': domain, 'scan_prompt': prompt, 'findings': '', 'status': ''}
        state = scan_domain(state)
        state = store_intel(state)
        all_findings.append(f"## {domain}\n{state['findings']}")
        print(f"  Done: {domain}")

    # Synthesis pass
    combined = '\n\n'.join(all_findings)
    sonnet = ChatAnthropic(model=MODELS['sonnet'], max_tokens=2000)
    synthesis = sonnet.invoke(f"""Synthesize these 4 domain scans into a single weekly intel brief for JRIH.
Highlight: cross-domain patterns, urgent items, strategic opportunities.
Be concise. Juniper reads this to inform division decisions.

{combined}

Weekly Intel Brief:""")

    # Store synthesis
    sb.table('thoughts').insert({
        'content': f"WEEKLY INTEL BRIEF: {synthesis.content}",
        'source': 'intel',
        'entry_type': 'insight',
        'agent': 'competitive-intel',
        'tags': ['intel', 'synthesis', 'weekly'],
        'embedding': embed(synthesis.content),
        'confidence': 0.8,
        'ttl': '30 days',
    }).execute()

    print(f"  Intel brief stored. {len(all_findings)} domains scanned.\n")
    return synthesis.content


# ═══════════════════════════════════════════════════════════
# HOJ AGENT — Heart of Juniper Dedicated
# 3x/week (Mon/Wed/Fri). Independent of Juniper rotation.
# Grant-aware. Community-first.
# ═══════════════════════════════════════════════════════════

def run_hoj_cycle():
    """HOJ dedicated cycle. Checks grants, programs, community."""
    print(f"\n[HOJ] Running dedicated cycle — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")

    # Pull HOJ-specific data
    recent_hoj = sb.table('thoughts') \
        .select('content, entry_type, tags, created_at') \
        .eq('source', 'heart_of_juniper') \
        .order('created_at', desc=True) \
        .limit(15) \
        .execute()

    # Check for grant deadlines (from hoj_grants table if exists)
    try:
        upcoming_grants = sb.table('hoj_grants') \
            .select('grant_name, funder_name, deadline, status, amount') \
            .in_('status', ['identified', 'in_progress']) \
            .order('deadline', desc=False) \
            .limit(10) \
            .execute()
        grants_data = upcoming_grants.data or []
    except Exception:
        grants_data = []

    hoj_context = '\n'.join([
        f"- [{t['entry_type']}] {t['content'][:150]}"
        for t in (recent_hoj.data or [])
    ])
    grants_context = '\n'.join([
        f"- {g['grant_name']} ({g['funder_name']}): ${g['amount']} — deadline: {g.get('deadline', 'TBD')} — status: {g['status']}"
        for g in grants_data
    ]) or 'No active grants tracked.'

    sonnet = ChatAnthropic(model=MODELS['sonnet'], max_tokens=1500)
    resp = sonnet.invoke(f"""You are the HOJ Agent for Heart of Juniper Foundation.
Programs: Rise and Thrive, Girls Circles. Sarasota, Florida.
Community impact is the north star — NOT revenue.
Brand: earthy, warm, approachable. NOT dark/tech.

Recent HOJ activity:
{hoj_context or 'No recent activity.'}

Upcoming grants:
{grants_context}

Generate a brief HOJ status update covering:
1. Grant pipeline status (any deadlines within 14 days?)
2. Program status check
3. Community engagement opportunities
4. Recommended next actions (max 3)

Keep it warm but action-oriented.""")

    # Store HOJ cycle output
    sb.table('thoughts').insert({
        'content': f"HOJ CYCLE: {resp.content}",
        'source': 'heart_of_juniper',
        'entry_type': 'observation',
        'agent': 'hoj-agent',
        'tags': ['hoj', 'cycle', 'programs'],
        'embedding': embed(resp.content),
        'confidence': 0.85,
    }).execute()

    # Flag urgent grants to HITL
    for g in grants_data:
        if g.get('deadline'):
            try:
                deadline = datetime.fromisoformat(str(g['deadline']))
                if deadline - datetime.utcnow() < timedelta(days=14):
                    sb.table('hitl_queue').insert({
                        'item_type': 'hoj_grant',
                        'title': f"Grant deadline approaching: {g['grant_name']} ({g['funder_name']}) — {g['deadline']}",
                        'context': json.dumps(g, default=str),
                        'agent': 'hoj-agent',
                        'division': 'hoj',
                        'confidence': 0.9,
                    }).execute()
                    print(f"  ALERT: Grant deadline within 14 days — {g['grant_name']}")
            except (ValueError, TypeError):
                pass

    print(f"  HOJ cycle complete.\n")
    return resp.content


# ═══════════════════════════════════════════════════════════
# CLAUDE ADVISOR — Strategic Counsel
# Monday 7am brief + on-demand.
# Haiku (format) → Sonnet (analysis) → Opus (deep counsel)
# ═══════════════════════════════════════════════════════════

def advisor_weekly_brief():
    """Monday 7am: strategic overview for Alan."""
    print(f"\n[Advisor] Generating weekly strategic brief...")

    # Gather cross-division intel
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Pull weekly stats
    stats = sb.rpc('juniper_stats', {'days': 7}).execute()
    stat = stats.data[0] if stats.data else {}

    # Pull digest if available
    digests = sb.table('digests') \
        .select('content') \
        .order('created_at', desc=True) \
        .limit(1) \
        .execute()
    latest_digest = digests.data[0]['content'][:2000] if digests.data else 'No digest available.'

    # Pull intel brief
    intel = sb.table('thoughts') \
        .select('content') \
        .eq('source', 'intel') \
        .contains('tags', ['synthesis']) \
        .order('created_at', desc=True) \
        .limit(1) \
        .execute()
    latest_intel = intel.data[0]['content'][:1500] if intel.data else 'No intel brief available.'

    # Sonnet for analysis
    sonnet = ChatAnthropic(model=MODELS['sonnet'], max_tokens=2000)
    resp = sonnet.invoke(f"""You are Claude Advisor, the strategic counsel for JRIH.
Founder: Alan Augustin. North star: $100M+ assets.
Your role: see what Juniper can't. Long horizon. Cross-division patterns.

Juniper Stats (7 days):
{json.dumps(stat, default=str)}

Latest Weekly Digest:
{latest_digest}

Latest Intel Brief:
{latest_intel}

Generate the Monday Strategic Brief:
1. North Star Alignment: Are we moving toward $100M? What's accelerating or decelerating?
2. Cross-Division Patterns: What themes are emerging across divisions?
3. Blind Spots: What is Juniper NOT seeing?
4. Strategic Opportunities: Based on intel, what should Alan consider?
5. This Week's Focus: Top 3 recommendations for the week ahead.
6. Risk Watch: Anything that needs immediate attention.

Be the elder counsel. Don't repeat what Juniper already knows. Add perspective.""")

    # Store advisor brief
    sb.table('thoughts').insert({
        'content': f"ADVISOR WEEKLY BRIEF: {resp.content}",
        'source': 'jrih',
        'entry_type': 'insight',
        'agent': 'claude-advisor',
        'tags': ['advisor', 'weekly', 'strategic'],
        'embedding': embed(resp.content),
        'confidence': 0.9,
    }).execute()

    print(f"  Advisor brief stored.\n")
    return resp.content


def advisor_deep_analysis(topic: str, context: str = ''):
    """On-demand Opus analysis for critical decisions."""
    print(f"\n[Advisor] Deep analysis: {topic[:50]}...")

    # Pull all relevant brain context
    query_embedding = embed(topic)
    results = sb.rpc('hybrid_search', {
        'query_text': topic,
        'query_embedding': query_embedding,
        'match_count': 15,
    }).execute()

    brain_context = '\n'.join([
        f"[{r['source']}/{r['entry_type']}] {r['content'][:300]}"
        for r in (results.data or [])
    ])

    # Opus for deep counsel
    opus = ChatAnthropic(model=MODELS['opus'], max_tokens=4000)
    resp = opus.invoke(f"""You are Claude Advisor (Opus tier) — the deepest strategic counsel for JRIH.
Founder: Alan Augustin. North star: $100M+ assets. Florida market dominance.

TOPIC: {topic}

{f'ADDITIONAL CONTEXT: {context}' if context else ''}

BRAIN CONTEXT (relevant entries):
{brain_context}

Provide a comprehensive strategic analysis:
1. Full situation assessment
2. Opportunity cost analysis against JRIH north star
3. Risk matrix (probability x impact)
4. Scenarios: best case, expected case, worst case
5. Cross-reference with existing JRIH strategy
6. Clear recommendation with confidence score (0-1.0)
7. What Alan should do next (specific, actionable)

This is Opus-tier analysis. No surface-level takes. Go deep.""")

    # Store analysis
    sb.table('thoughts').insert({
        'content': f"ADVISOR DEEP ANALYSIS [{topic[:80]}]: {resp.content}",
        'source': 'jrih',
        'entry_type': 'decision',
        'agent': 'claude-advisor',
        'tags': ['advisor', 'deep-analysis', 'opus'],
        'embedding': embed(resp.content),
        'confidence': 0.95,
    }).execute()

    print(f"  Deep analysis stored.\n")
    return resp.content


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python specialized_agents.py intel        # Run weekly intel scan")
        print("  python specialized_agents.py hoj          # Run HOJ cycle")
        print("  python specialized_agents.py advisor      # Run weekly advisor brief")
        print('  python specialized_agents.py deep "topic" # Run Opus deep analysis')
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'intel':
        run_intel_scan()
    elif cmd == 'hoj':
        run_hoj_cycle()
    elif cmd == 'advisor':
        advisor_weekly_brief()
    elif cmd == 'deep':
        topic = sys.argv[2] if len(sys.argv) > 2 else 'General JRIH strategic review'
        advisor_deep_analysis(topic)
