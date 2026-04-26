"""
JRIH — Juniper Orchestration Agent
Headless Chief of Staff. Execute rights. Perpetual loop.
Loop: Perceive -> Reason -> Junior Gate -> Execute -> Log
Cycle: One division per hour, rotating.

Usage:
  python juniper.py              # perpetual loop
  python juniper.py cycle jri    # single cycle, one division
  python juniper.py brief        # generate morning brief
"""

import sys
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic

from config import (
    sb, embed, route_model, route_junior, get_llm, LoopGuard,
    reset_cycle_counters, MODELS, DIVISIONS, DIVISION_NAMES,
    THRESHOLD_AUTO_EXECUTE, THRESHOLD_REVIEW,
)


# ═══════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════

class JuniperState(TypedDict):
    cycle_id: str
    division: str
    perception: dict        # what Juniper sees
    reasoning: dict         # what Juniper thinks
    decision: dict          # what Juniper wants to do
    junior_verdict: str     # approve | reject | revise
    junior_reason: str
    revision_count: int
    executed: bool
    execution_result: str
    model_used: str
    tokens_used: int
    error: str


# ═══════════════════════════════════════════════════════════
# NODES
# ═══════════════════════════════════════════════════════════

def perceive(state: JuniperState) -> JuniperState:
    """Scan division state from brain + external signals."""
    division = state['division']
    cycle_id = state['cycle_id']

    # Pull recent thoughts for this division
    namespace_map = {
        'jri': 'axiom', 'jr_capital': 'jrih', 'jr_realty': 'jrih',
        'kintsugi': 'jrih', 'hoj': 'heart_of_juniper',
    }
    namespace = namespace_map.get(division, 'jrih')

    recent = sb.table('thoughts') \
        .select('content, entry_type, tags, confidence, created_at') \
        .eq('source', namespace) \
        .order('created_at', desc=True) \
        .limit(20) \
        .execute()

    # Check HITL queue for this division
    hitl = sb.table('hitl_queue') \
        .select('id, item_type, title, created_at') \
        .eq('division', division) \
        .eq('status', 'pending') \
        .execute()

    # Check recent audit for patterns
    recent_audit = sb.table('juniper_audit') \
        .select('decision, junior_verdict, confidence') \
        .eq('division', division) \
        .order('created_at', desc=True) \
        .limit(10) \
        .execute()

    state['perception'] = {
        'division': division,
        'division_name': DIVISION_NAMES.get(division, division),
        'recent_thoughts': recent.data or [],
        'pending_hitl': hitl.data or [],
        'recent_decisions': recent_audit.data or [],
        'scanned_at': datetime.utcnow().isoformat(),
    }
    return state


def reason(state: JuniperState) -> JuniperState:
    """Sonnet: analyze perception, decide action."""
    perception = state['perception']
    division = perception['division_name']

    thoughts_summary = '\n'.join([
        f"- [{t['entry_type']}] {t['content'][:120]}..."
        for t in perception['recent_thoughts'][:10]
    ])

    hitl_summary = f"{len(perception['pending_hitl'])} pending HITL items" if perception['pending_hitl'] else "No pending HITL"

    # Load Junior's active rules
    rules = sb.table('junior_patterns') \
        .select('rule_text') \
        .eq('is_rule', True) \
        .execute()
    junior_rules = '\n'.join([r['rule_text'] for r in (rules.data or [])]) or 'No active rules yet.'

    model = route_model('reason', complexity='low')
    sonnet = ChatAnthropic(model=model, max_tokens=1500)

    resp = sonnet.invoke(f"""You are Juniper, the headless Chief of Staff for JRIH.
You are scanning the {division} division. Decide the single most impactful action to take.

Division recent activity:
{thoughts_summary}

HITL status: {hitl_summary}

Junior's active rules (must comply):
{junior_rules}

Consider: What is the highest-leverage action for {division} right now?
Return JSON: {{"action_type": "email|deploy|task|research|content|contract|memory|none",
"description": "what to do and why", "confidence": 0.0-1.0,
"complexity": "low|high|critical", "details": {{}}}}

If nothing actionable, return action_type "none" with confidence 1.0.

JSON:""")

    try:
        text = resp.content
        start = text.find('{')
        end = text.rfind('}') + 1
        decision = json.loads(text[start:end])
    except Exception:
        decision = {'action_type': 'none', 'description': 'Failed to parse reasoning', 'confidence': 0.5}

    state['reasoning'] = {'model': model, 'raw_response': resp.content[:500]}
    state['decision'] = decision
    state['model_used'] = model
    return state


def junior_gate(state: JuniperState) -> JuniperState:
    """Junior: adversarial critique of Juniper's decision."""
    decision = state['decision']

    if decision.get('action_type') == 'none':
        state['junior_verdict'] = 'approve'
        state['junior_reason'] = 'No action proposed.'
        return state

    confidence = decision.get('confidence', 0.5)

    # Below threshold → auto-reject
    if confidence < THRESHOLD_REVIEW:
        state['junior_verdict'] = 'reject'
        state['junior_reason'] = f'Confidence {confidence} below threshold {THRESHOLD_REVIEW}'
        return state

    # Route Junior to appropriate model
    action_type = decision.get('action_type', 'memory')
    junior_model = route_junior(action_type, confidence)

    # Load Junior's learned rules
    rules = sb.table('junior_patterns') \
        .select('rule_text') \
        .eq('is_rule', True) \
        .execute()
    learned_rules = '\n'.join([f"- {r['rule_text']}" for r in (rules.data or [])]) or 'None yet.'

    junior = ChatAnthropic(model=junior_model, max_tokens=800)
    resp = junior.invoke(f"""You are Junior, the adversarial critic for JRIH. Your job: protect the organism.
Evaluate this Juniper decision. Be skeptical. Check for:
1. Does this serve the organism's north star ($100M assets)?
2. Is the confidence score justified?
3. Are there risks Juniper missed?
4. Does it violate any learned rules?

Learned rules:
{learned_rules}

Juniper's decision:
Division: {state['division']}
Action: {decision.get('action_type')}
Description: {decision.get('description')}
Confidence: {confidence}
Complexity: {decision.get('complexity')}

Return JSON: {{"verdict": "approve|reject|revise", "reason": "why", "suggested_revision": "if revise"}}

JSON:""")

    try:
        text = resp.content
        start = text.find('{')
        end = text.rfind('}') + 1
        verdict = json.loads(text[start:end])
    except Exception:
        verdict = {'verdict': 'reject', 'reason': 'Failed to parse Junior response'}

    state['junior_verdict'] = verdict.get('verdict', 'reject')
    state['junior_reason'] = verdict.get('reason', '')

    # Log rejection pattern for learning loop
    if state['junior_verdict'] == 'reject':
        sb.table('thoughts').insert({
            'content': f"JUNIOR PATTERN: [{state['division']}] {decision.get('action_type')} rejected. Reason: {state['junior_reason']}",
            'source': 'system',
            'entry_type': 'observation',
            'agent': 'junior-learning',
            'tags': ['junior-pattern', state['division'], decision.get('action_type', 'unknown')],
            'confidence': 1.0,
        }).execute()

    return state


def execute_decision(state: JuniperState) -> JuniperState:
    """Execute approved decisions. High-stakes → HITL queue."""
    decision = state['decision']
    action_type = decision.get('action_type', 'none')
    confidence = decision.get('confidence', 0.5)

    # No action or rejected
    if action_type == 'none' or state['junior_verdict'] == 'reject':
        state['executed'] = False
        state['execution_result'] = f"Not executed. Verdict: {state['junior_verdict']}"
        return state

    # Revision requested (max 2)
    if state['junior_verdict'] == 'revise' and state['revision_count'] < 2:
        state['revision_count'] = state.get('revision_count', 0) + 1
        state['executed'] = False
        state['execution_result'] = 'Revision requested'
        return state

    # High stakes or low confidence → HITL queue
    if action_type in ('email', 'deploy', 'contract') or confidence < THRESHOLD_AUTO_EXECUTE:
        sb.table('hitl_queue').insert({
            'item_type': 'high_stakes' if action_type in ('email', 'deploy', 'contract') else 'low_confidence',
            'title': decision.get('description', 'Unnamed decision')[:200],
            'context': json.dumps(decision),
            'agent': 'juniper',
            'division': state['division'],
            'confidence': confidence,
        }).execute()
        state['executed'] = False
        state['execution_result'] = f'Routed to HITL queue ({action_type})'
        return state

    # Auto-execute: memory, research, content at high confidence
    if action_type == 'memory':
        sb.table('thoughts').insert({
            'content': decision.get('description', ''),
            'source': state['division'],
            'entry_type': 'observation',
            'agent': 'juniper',
            'tags': ['juniper-action', state['division']],
            'confidence': confidence,
        }).execute()
        state['executed'] = True
        state['execution_result'] = 'Memory entry created'
    elif action_type == 'research':
        # Queue research task
        sb.table('thoughts').insert({
            'content': f"RESEARCH TASK: {decision.get('description', '')}",
            'source': state['division'],
            'entry_type': 'task',
            'agent': 'juniper',
            'tags': ['research', 'queued', state['division']],
            'confidence': confidence,
        }).execute()
        state['executed'] = True
        state['execution_result'] = 'Research task queued'
    elif action_type == 'content':
        sb.table('thoughts').insert({
            'content': f"CONTENT TASK: {decision.get('description', '')}",
            'source': 'content',
            'entry_type': 'task',
            'agent': 'juniper',
            'tags': ['content', 'queued', state['division']],
            'confidence': confidence,
        }).execute()
        state['executed'] = True
        state['execution_result'] = 'Content task queued'
    else:
        state['executed'] = True
        state['execution_result'] = f'Executed: {action_type}'

    return state


def log_cycle(state: JuniperState) -> JuniperState:
    """Log everything to juniper_audit."""
    result = sb.table('juniper_audit').insert({
        'cycle_id': state['cycle_id'],
        'division': state['division'],
        'phase': 'complete',
        'action_type': state['decision'].get('action_type', 'none'),
        'decision': state['decision'].get('description', ''),
        'confidence': state['decision'].get('confidence'),
        'junior_verdict': state['junior_verdict'],
        'junior_reason': state['junior_reason'],
        'revision_count': state.get('revision_count', 0),
        'executed': state['executed'],
        'execution_result': state['execution_result'],
        'model_used': state.get('model_used', ''),
    }).execute()
    if not result.data:
        raise RuntimeError(
            f"juniper_audit insert returned empty data for cycle {state['cycle_id']} — "
            f"likely RLS rejection or wrong Supabase project (check SUPABASE_URL)"
        )
    return state


def should_revise(state: JuniperState) -> str:
    """Check if revision is needed."""
    if state['junior_verdict'] == 'revise' and state.get('revision_count', 0) < 2:
        return 'reason'  # Go back to reasoning with revision context
    return 'execute'


# ═══════════════════════════════════════════════════════════
# BUILD JUNIPER GRAPH
# ═══════════════════════════════════════════════════════════

builder = StateGraph(JuniperState)
builder.add_node('perceive', perceive)
builder.add_node('reason', reason)
builder.add_node('junior_gate', junior_gate)
builder.add_node('execute', execute_decision)
builder.add_node('log', log_cycle)

builder.set_entry_point('perceive')
builder.add_edge('perceive', 'reason')
builder.add_edge('reason', 'junior_gate')
builder.add_conditional_edges('junior_gate', should_revise, {'reason': 'reason', 'execute': 'execute'})
builder.add_edge('execute', 'log')
builder.add_edge('log', END)

juniper_graph = builder.compile()


# ═══════════════════════════════════════════════════════════
# MORNING BRIEF
# ═══════════════════════════════════════════════════════════

def generate_brief() -> str:
    """Generate morning brief for Alan via Rose."""
    # Get stats
    stats = sb.rpc('juniper_stats', {'days': 1}).execute()
    stat = stats.data[0] if stats.data else {}

    # Get pending HITL
    hitl = sb.rpc('get_pending_hitl', {'max_items': 10}).execute()
    hitl_items = hitl.data or []

    # Get recent decisions
    recent = sb.table('juniper_audit') \
        .select('division, action_type, decision, junior_verdict, executed, created_at') \
        .order('created_at', desc=True) \
        .limit(10) \
        .execute()

    sonnet = ChatAnthropic(model=MODELS['sonnet'], max_tokens=1500)
    resp = sonnet.invoke(f"""Generate Alan's morning brief for JRIH. Be concise, direct, actionable.
Alan's style: compressed, directive, expects full context.

Juniper Stats (last 24h):
{json.dumps(stat, default=str)}

Pending HITL Queue ({len(hitl_items)} items):
{json.dumps(hitl_items, default=str)}

Recent Juniper Decisions:
{json.dumps(recent.data, default=str)}

Format:
# Morning Brief — [date]
## HITL Queue (items needing your decision)
## Overnight Activity
## Today's Focus
## Metrics Snapshot
""")

    return resp.content


# ═══════════════════════════════════════════════════════════
# MAIN — CLI + Perpetual Loop
# ═══════════════════════════════════════════════════════════

def run_cycle(division: str) -> dict:
    """Run a single Juniper cycle for one division."""
    reset_cycle_counters()  # reset per-cycle model call budgets
    state = {
        'cycle_id': f"juniper-{division}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
        'division': division,
        'perception': {},
        'reasoning': {},
        'decision': {},
        'junior_verdict': '',
        'junior_reason': '',
        'revision_count': 0,
        'executed': False,
        'execution_result': '',
        'model_used': '',
        'tokens_used': 0,
        'error': '',
    }

    try:
        result = juniper_graph.invoke(state)
        print(f"  [{division}] {result.get('decision', {}).get('action_type', 'none')} → {result.get('junior_verdict', '?')} → {'EXECUTED' if result.get('executed') else 'NOT EXECUTED'}")
        return result
    except Exception as e:
        print(f"  [{division}] ERROR: {str(e)[:100]}")
        return {**state, 'error': str(e)}


def perpetual_loop():
    """Run Juniper perpetually. One division per hour. LoopGuard detects stall + self-heals."""
    print(f"\n{'='*60}")
    print(f"JUNIPER — Perpetual Orchestration Loop")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")

    def _brain_capture(content, namespace='system', tags=None):
        try:
            sb.table('thoughts').insert({
                'content':    content,
                'source':     namespace,
                'entry_type': 'observation',
                'agent':      'loop_guard',
                'tags':       tags or [],
                'confidence': 1.0,
            }).execute()
        except Exception:
            pass

    division_idx = 0
    # max_iterations is very large — we never want to truly abort a perpetual loop.
    # stall_threshold=10 means 10 consecutive cycles with action_type='none' → heal.
    guard = LoopGuard('juniper_perpetual', max_iterations=100_000, stall_threshold=10)

    while True:
        division = DIVISIONS[division_idx % len(DIVISIONS)]
        print(f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Scanning: {DIVISION_NAMES[division]}")

        result   = run_cycle(division)
        action   = result.get('decision', {}).get('action_type', 'none')
        executed = result.get('executed', False)
        # produced_output = cycle did something actionable (not just 'none')
        produced_output = (action != 'none') and executed

        signal = guard.tick(produced_output=produced_output)

        if signal == 'heal':
            params = guard.get_heal_strategy()
            print(f"  [LoopGuard] Stall detected — heal attempt {guard.heal_attempts}, scope={params['scope']}")
            try:
                sb.table('thoughts').insert({
                    'content':    (
                        f'[Juniper stall] Division {division}: {guard.stall_threshold} cycles with no '
                        f'executed output. Heal attempt {guard.heal_attempts} — scope={params["scope"]}.'
                    ),
                    'source':     'system',
                    'entry_type': 'observation',
                    'agent':      'juniper-loop-guard',
                    'tags':       ['loop_stall', 'juniper', division],
                    'confidence': 0.6,
                }).execute()
            except Exception:
                pass

        elif signal == 'abort':
            guard.emit_to_brain(_brain_capture, extra=f'last_division={division}')
            print(f'  [LoopGuard] All heal attempts exhausted — resetting guard and continuing loop.')
            # Never truly kill the perpetual loop — just reset the guard
            guard = LoopGuard('juniper_perpetual', max_iterations=100_000, stall_threshold=10)

        division_idx += 1
        # Shorten sleep during heal attempts to probe faster
        sleep_secs = 300 if signal == 'heal' else 3600
        print(f"  Next scan in {sleep_secs // 60} minutes...")
        time.sleep(sleep_secs)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'cycle' and len(sys.argv) > 2:
            division = sys.argv[2]
            result = run_cycle(division)
            print(json.dumps({
                'decision': result.get('decision', {}),
                'verdict': result.get('junior_verdict', ''),
                'executed': result.get('executed', False),
                'result': result.get('execution_result', ''),
            }, indent=2))
        elif cmd == 'brief':
            print(generate_brief())
        else:
            print("Usage: python juniper.py [cycle <division>|brief]")
    else:
        perpetual_loop()
