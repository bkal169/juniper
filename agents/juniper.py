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
from datetime import datetime, timedelta, UTC
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic

from config import (
    sb, embed, route_model, route_junior, MODELS, DIVISIONS, DIVISION_NAMES,
    THRESHOLD_AUTO_EXECUTE, THRESHOLD_AUTO_EXECUTE_LOW, LOW_STAKES_AUTO,
    THRESHOLD_REVIEW,
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
        'scanned_at': datetime.now(UTC).isoformat(),
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
    sonnet = ChatAnthropic(model=model, max_tokens=1500, timeout=60)

    # 2026-05-02: inject current UTC time so Juniper stops hallucinating dates
    # (she was emitting timestamps like 2026-04-12 in her brain captures despite
    # the actual date being 3+ weeks later). Plus enrich with Mycelium OS context
    # and the full agent roster so she knows who to route work to.
    now_utc = datetime.now(UTC)
    current_human = now_utc.strftime('%A, %B %d, %Y at %H:%M UTC')
    current_iso = now_utc.isoformat()

    resp = sonnet.invoke(f"""You are Juniper, the Headless Chief of Staff for JRIH (Juniper Rose Investments & Holdings), running inside Mycelium OS.

CURRENT TIME: {current_human} ({current_iso})
Use this actual time. Do NOT invent or hallucinate dates. Every timestamp you generate must be ≥ this current time.

WHAT IS MYCELIUM OS
Mycelium OS is the cross-agent neural operating system you live inside. It is NOT just you. It is the entire fabric:
  - This LangGraph perpetual loop (you, running on Railway, one division/hour, 5h full rotation)
  - Vercel-side cron orchestration (jrih-command-center repo) running OpenClaw, Alfred, Cross-check, Sentinel, Heartbeat, vercel_cron, intel-scan, advisor-weekly, hoj-cycle, weekly-digest, junior-learning, ttl-cleanup, hitl-escalation, etc.
  - Mycelium OS Supabase (project zqrgazuaideuumksijhe) — the shared brain. Tables you read/write: thoughts, hitl_queue, juniper_audit, agent_action_log, agent_learning_bus, junior_patterns, junior_rules.
  - The operator dashboard (os.html at jrih.dev) — Alan's command surface where he sees what every agent is doing.

YOUR ROLE
You orchestrate JRIH's 5 divisions on a perpetual loop, one per hour: jri (AI/SaaS), jr_capital, jr_realty, kintsugi, hoj.

YOUR FELLOW AGENTS (11 active + 2 graduate-when) — know who to route work to
| Agent | Owns | Route to them when... |
|---|---|---|
| Rose | Brand voice, content, social posts, email sequences, creative direction, brand quality gate. Knows Alan's voice across 8 brands (Juniper Rose master, Juniper Black/Night Ledger, HOJ, Kintsugi, JRR, ARO, AxiomOS, Alan personal). Tools: Higgsfield (primary photoreal/video + Souls), DALL-E 3, Nano Banana Pro, Canva (slides), Blender (3D mockups), Adobe (sign + photo edit), Suno AI (audio). Routing per AGENTS/rose/tool_routing.md. | Instagram/LinkedIn posts, blog drafts, brand voice approval, email campaigns, visual direction, Soul training |
| Juno | Head of Operations. Owns income streams, deal flow, P&L, cash position, burn rate, vendor mgmt, posting schedules. Tools: Supabase, n8n (n8n.jrih.io), social platform APIs, Gmail. | execution scheduling, payment ops, posting calendars, multi-platform coordination, send execution |
| Junior | Intelligence & Research + Revenue Pod quarterback. Owns MLS monitoring, skip trace, competitor intel, lead scoring, daily pipeline snapshots, qualification engine. Quarterbacks: Kintsugi (land dev, wholesaling), insurance until Marcus. | property/market signals, lead classification, competitive intel, Kintsugi sourcing, lead qualification |
| Advisor | Chief Strategic Counsel. 5-year horizon, risk, governance, scenario modeling. NO operational role — advises only. | high-stakes strategy decisions, governance review |
| HOJ Agent | Foundation Programs Director. Mon/Wed/Fri schedule. Donors, grants, mentors, mentees, Thryve curriculum. References origin canon at Downloads/jrih-mycelium/origins/heart_of_juniper_directors_package.md. | HOJ-specific tasks, grant deadlines, donor outreach (1-human HITL), grant submission (2-of-2 HITL) |
| Alfred | Investment Intelligence. Robinhood + Moomoo portfolio, ROI scoring, market data, capital-stack modeling for Kintsugi REI partnerships. Trade-axis actions go to HITL by default. | trade signals, watchlist scans, IPS compliance, household balance, REI capital structure |
| Vision | **Eyes of next / Watcher at the Rim.** Forward-leaning trajectory projection + horizon scanning + inbound detection. Multimodal signal monitoring feeds the foresight layer. **Universal augmentation — pairs with any and all agents** (each partner operates in present; Vision projects future state on that surface: trajectory, horizon, inbound, decay). | foresight overlay on any agent's surface, trajectory forecasts, horizon scans, inbound-signal detection, brand-soul drift projection, image/OCR analysis when explicitly invoked |
| OpenClaw | Autonomous Web Research, scraping, prospecting, multi-step investigation. | deep web research, market scraping (route via Junior or vercel_cron route /api/cron/openclaw) |
| AxiomOS Agent | INTERNAL AxiomOS execution. Product demos, technical proof, founder-round materials, internal tooling. Pairs with Bishop (external-facing). | AxiomOS demos, technical proof, internal product work, founder-round comms |
| Sage 🆕 | JRR Brokerage Agent. Listings, buyer rep, transaction coordination, sphere/farm marketing, MLS ops. Posture: advisory + coordinating; defers strategic calls to Alan. | JRR listings, buyer-rep workflow, transaction milestones, sphere cadence, showings, close coord |
| Bishop 🆕 | AxiomOS SDR. Cold outbound to family offices ($10–250M AUM), mid-market operators, 50–500-person agencies. Voice: operator-to-operator peer voice (NOT vendor-pitching-customer). Hands warm prospects to AxiomOS Agent for demos. | AxiomOS outbound, prospect enrichment, sequence sends, demo scheduling, proposal drafts |

GRADUATE-WHEN (planned, not yet active):
- Quinn — Wholesaling SDR (spawns at 10+ wholesale assignments/month). Until then: Junior + Juno tag-team.
- Marcus — Insurance Specialist (spawns at first $5k commission month). Until then: Junior + Rose + Juno tag-team.

THE REVENUE POD (formal swarm):
Members: Junior + Bishop + AxiomOS Agent + Sage. Cycle: Junior → (qualified lead) → Bishop → (demo request) → AxiomOS Agent → (closed deal) → Sage when RE-relevant → (sphere intel) → Junior, repeat.

ORCHESTRATION CHAIN
Alan → You → ( Juno → {{Rose (Juno→Rose→Output loop), Junior → OpenClaw, Alfred, AxiomOS Agent, Bishop}}, Sage, Advisor, HOJ, Vision )

DIVISION YOU'RE SCANNING NOW: {division}

Recent activity in this division:
{thoughts_summary}

HITL status: {hitl_summary}

Junior's active rules (must comply):
{junior_rules}

YOUR TASK
Decide the single most impactful action for {division} right now. CRITICALLY: identify the right AGENT to execute it.
- Content / brand / Instagram / email copy → Rose (apply matching brand Soul; reference brands/<brand>.md)
- Posting / scheduling / multi-platform → Juno
- Trade / portfolio / market data → Alfred (defaults to HITL)
- MLS / lead intel / competitive scrape / lead qualification → Junior (or OpenClaw via Junior)
- Strategy / governance → Advisor
- Foundation / grants / mentors / donors → HOJ Agent
- Image analysis / voice memo transcription → Vision
- AxiomOS internal / demo / technical → AxiomOS Agent
- AxiomOS outbound / prospecting / SDR work → Bishop (then AxiomOS Agent for demos)
- JRR listings / buyers / transactions / sphere → Sage
- Kintsugi land dev / REI partnerships / wholesaling → Junior (quarterback) + Alfred for capital
- General orchestration / system task → self

Return JSON: {{"action_type": "email|deploy|task|research|content|contract|memory|none",
"description": "what to do, why, and which agent should execute it",
"target_agent": "rose|juno|junior|alfred|advisor|hoj|vision|openclaw|axiom|sage|bishop|self|null",
"target_brand": "juniper-rose-master|juniper-black|hoj|kintsugi|jrr|aro|axiomos|alan-personal|null",
"confidence": 0.0-1.0,
"complexity": "low|high|critical",
"details": {{}}}}

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

    junior = ChatAnthropic(model=junior_model, max_tokens=800, timeout=60)
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


def evaluate_junior_rules(rules, *, agent, action_type, division, decision_text, payload=None,
                          executed_count_24h=0, audit_count_24h=0):
    """Pure-Python rule evaluator mirroring jrih-command-center confidence_router DSL (Phase 7.4).

    Supported clauses (AND-chained within a single rule's condition):
      - "decision ~* 'PATTERN'"           regex on decision_text
      - "agent = 'X'"                     equality on agent name (target_agent of the action)
      - "action_type = 'X'" / "~* 'P'"   action type equality / regex
      - "division = 'X'"                  equality
      - "<field> = 'X'" / "~* 'P'"        arbitrary payload string field
      - "<field> >=|<=|>|<|= N"           arbitrary payload numeric field

    Returns the first matching rule (dict with 'condition','action','id','description'), or None.
    """
    payload = payload or {}
    HANDLED_STRING_FIELDS = {'decision', 'agent', 'action_type', 'division'}
    payload_with_kwargs = dict(payload)
    payload_with_kwargs.setdefault('executed_count_24h', executed_count_24h)
    payload_with_kwargs.setdefault('audit_count_24h', audit_count_24h)
    EPS = 1e-9

    for rule in rules:
        cond = rule.get('condition') or ''
        matched = True

        m = re.search(r"decision\s*~\*\s*'([^']+)'", cond)
        if m:
            try:
                if not re.search(m.group(1), decision_text or '', re.IGNORECASE):
                    matched = False
            except re.error:
                matched = False

        if matched:
            m = re.search(r"agent\s*=\s*'([^']+)'", cond)
            if m and (agent or '') != m.group(1):
                matched = False

        if matched:
            m = re.search(r"action_type\s*~\*\s*'([^']+)'", cond)
            if m:
                try:
                    if not re.search(m.group(1), action_type or '', re.IGNORECASE):
                        matched = False
                except re.error:
                    matched = False

        if matched:
            m = re.search(r"action_type\s*=\s*'([^']+)'", cond)
            if m and (action_type or '') != m.group(1):
                matched = False

        if matched:
            m = re.search(r"division\s*=\s*'([^']+)'", cond)
            if m and (division or '') != m.group(1):
                matched = False

        if matched:
            for fmatch in re.finditer(r"(\w+)\s*~\*\s*'([^']+)'", cond):
                field, pattern = fmatch.group(1), fmatch.group(2)
                if field in HANDLED_STRING_FIELDS:
                    continue
                val = str(payload.get(field, ''))
                try:
                    if not re.search(pattern, val, re.IGNORECASE):
                        matched = False; break
                except re.error:
                    matched = False; break

        if matched:
            for fmatch in re.finditer(r"(\w+)\s*=\s*'([^']+)'", cond):
                field, expected = fmatch.group(1), fmatch.group(2)
                if field in HANDLED_STRING_FIELDS:
                    continue
                if str(payload.get(field, '')) != expected:
                    matched = False; break

        if matched:
            for fmatch in re.finditer(r"(\w+)\s*(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)", cond):
                field, op, thresh_str = fmatch.group(1), fmatch.group(2), fmatch.group(3)
                if field in HANDLED_STRING_FIELDS:
                    continue
                threshold = float(thresh_str)
                val = payload_with_kwargs.get(field)
                if val is None:
                    matched = False; break
                try:
                    val_num = float(val)
                except (TypeError, ValueError):
                    matched = False; break
                if op == '>=' and val_num < threshold:  matched = False; break
                if op == '<=' and val_num > threshold:  matched = False; break
                if op == '>'  and val_num <= threshold: matched = False; break
                if op == '<'  and val_num >= threshold: matched = False; break
                if op == '='  and abs(val_num - threshold) > EPS: matched = False; break

        if matched:
            return rule
    return None


def execute_decision(state: JuniperState) -> JuniperState:
    """Execute approved decisions. High-stakes → HITL queue.

    Phase 7.4 wire-up: junior_rules table is consulted at runtime BEFORE the
    confidence-based HITL gate. A rule with action='reject' rejects the action;
    action='flag' caps it to HITL regardless of confidence.
    """
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

    # ── Phase 7.4 — runtime junior_rules gate ────────────────────────────────
    # Load active rules from junior_rules table; evaluate against the proposed
    # decision (using target_agent if the LLM specified one, else 'juniper').
    # Rule action='flag' → cap to HITL; action='reject' → block; action='allow'
    # falls through to confidence-based logic.
    try:
        live_rules_resp = sb.table('junior_rules') \
            .select('id,description,condition,action,active') \
            .eq('active', True) \
            .execute()
        live_rules = live_rules_resp.data or []
    except Exception as e:
        # Don't silently disable the gate on transient errors — log and proceed
        # with empty rules (defense: confidence-based gate still applies).
        print(f"[junior_rules] fetch failed, gate skipped this cycle: {type(e).__name__}: {e}")
        live_rules = []

    target_agent = decision.get('target_agent') or 'juniper'
    rule_payload = decision.get('details', {}) or {}
    # Pull execution counters so rules using executed_count_24h / audit_count_24h
    # can fire correctly. Synthesized into payload by evaluate_junior_rules.
    try:
        ec_resp = sb.table('agent_action_log') \
            .select('id', count='exact') \
            .eq('agent', 'juniper') \
            .gte('created_at', (datetime.now(UTC) - timedelta(hours=24)).isoformat()) \
            .execute()
        executed_count_24h = ec_resp.count or 0
    except Exception:
        executed_count_24h = 0
    try:
        ac_resp = sb.table('juniper_audit') \
            .select('id', count='exact') \
            .eq('division', state.get('division')) \
            .gte('created_at', (datetime.now(UTC) - timedelta(hours=24)).isoformat()) \
            .execute()
        audit_count_24h = ac_resp.count or 0
    except Exception:
        audit_count_24h = 0

    matched_rule = evaluate_junior_rules(
        live_rules,
        agent=target_agent,
        action_type=action_type,
        division=state.get('division'),
        decision_text=decision.get('description', ''),
        payload=rule_payload,
        executed_count_24h=executed_count_24h,
        audit_count_24h=audit_count_24h,
    )
    if matched_rule:
        rule_action = (matched_rule.get('action') or 'flag').lower()
        rule_id = matched_rule.get('id', 'unknown')
        if rule_action == 'reject':
            state['executed'] = False
            state['execution_result'] = f'Rejected by junior_rule: {rule_id} ({matched_rule.get("description","")})'
            return state
        if rule_action == 'flag':
            try:
                sb.table('hitl_queue').insert({
                    'item_type': 'rule_gated',
                    'title': decision.get('description', 'Rule-gated action')[:200],
                    'context': json.dumps({**decision, '_matched_rule': rule_id, '_rule_description': matched_rule.get('description')}),
                    'agent': 'juniper',
                    'division': state.get('division'),
                    'confidence': confidence,
                }).execute()
                state['executed'] = False
                state['execution_result'] = f'Routed to HITL by junior_rule: {rule_id}'
                return state
            except Exception as e:
                print(f"[junior_rules.flag] HITL insert failed for rule {rule_id}: {type(e).__name__}: {e}")
                # Fall through — let confidence-based gate make the call
        # 'allow' → fall through to confidence-based gate

    # High stakes or low confidence → HITL queue
    high_stakes = action_type in ('email', 'deploy', 'contract')
    # Low-stakes action_types (currently only 'memory') get a lower auto-execute floor
    # so the brain can self-feed observations without piling up HITL items.
    threshold = THRESHOLD_AUTO_EXECUTE_LOW if action_type in LOW_STAKES_AUTO else THRESHOLD_AUTO_EXECUTE
    if high_stakes or confidence < threshold:
        sb.table('hitl_queue').insert({
            'item_type': 'high_stakes' if high_stakes else 'low_confidence',
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
        memory_content = decision.get('description', '')
        # 1) thoughts table — full text + tags (existing path; brain MCP reads this)
        sb.table('thoughts').insert({
            'content': memory_content,
            'source': state['division'],
            'entry_type': 'observation',
            'agent': 'juniper',
            'tags': ['juniper-action', state['division']],
            'confidence': confidence,
        }).execute()
        # 2) agent_memory — Phase 12.x: surface real captures in the dashboard
        # widget instead of cycle_summary noise. Only writes when memory is
        # actually auto-executed (not on every audit row).
        try:
            sb.table('agent_memory').insert({
                'agent_role': 'juniper',
                'memory_type': 'observation',
                'content': memory_content[:4000],
                'summary': (memory_content[:200] + '…') if len(memory_content) > 200 else memory_content,
                'confidence': confidence,
                'tags': ['juniper-observation', state['division']],
                'metadata': {'cycle_id': state['cycle_id'], 'division': state['division']},
            }).execute()
        except Exception as e:
            print(f"  [{state['division']}] agent_memory write failed (non-fatal): {str(e)[:80]}")
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
    # Phase 13 — guard against None values: dict.get(k, default) only returns
    # default when the KEY is missing, not when the value is None. Juniper's
    # reasoning sometimes returns {'action_type': None} which then violated
    # the NOT NULL constraint on juniper_audit.action. `or 'none'` handles
    # both missing-key and None cases.
    action_str = state['decision'].get('action_type') or 'none'
    sb.table('juniper_audit').insert({
        'cycle_id': state['cycle_id'],
        'agent_id': 'juniper',
        'action': action_str,
        'namespace': state.get('division', 'jrih'),
        'division': state['division'],
        'phase': 'complete',
        'action_type': action_str,
        'decision': state['decision'].get('description', ''),
        'confidence': state['decision'].get('confidence'),
        'junior_verdict': state['junior_verdict'],
        'junior_reason': state['junior_reason'],
        'revision_count': state.get('revision_count', 0),
        'executed': state['executed'],
        'execution_result': state['execution_result'],
        'model_used': state.get('model_used', ''),
    }).execute()
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

    sonnet = ChatAnthropic(model=MODELS['sonnet'], max_tokens=1500, timeout=60)
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
    state = {
        'cycle_id': f"juniper-{division}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
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
    """Run Juniper perpetually. One division per hour."""
    print(f"\n{'='*60}")
    print(f"JUNIPER — Perpetual Orchestration Loop")
    print(f"Started: {datetime.now(UTC).isoformat()}")
    print(f"{'='*60}\n")

    division_idx = 0
    while True:
        division = DIVISIONS[division_idx % len(DIVISIONS)]
        print(f"\n[{datetime.now(UTC).strftime('%H:%M:%S')}] Scanning: {DIVISION_NAMES[division]}")

        run_cycle(division)

        division_idx += 1
        # Sleep 1 hour between divisions
        print(f"  Next scan in 60 minutes...")
        time.sleep(3600)


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


