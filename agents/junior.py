"""
JRIH — Junior (Adversarial Critic)
Hard gate on all Juniper decisions.
Self-improving via pattern detection.

Also usable standalone for ad-hoc decision critique.

Usage:
  python junior.py review "Deploy AxiomOS v6.1 to production" --confidence 0.88 --type deploy
  python junior.py rules           # show active rules
  python junior.py learn           # run weekly learning loop
"""

import sys
import json
from datetime import datetime, timedelta
from langchain_anthropic import ChatAnthropic

from config import sb, MODELS, route_junior


def critique(
    decision_description: str,
    action_type: str = 'memory',
    confidence: float = 0.8,
    division: str = 'jri',
    context: str = '',
) -> dict:
    """Critique a decision. Returns verdict + reason."""

    # Load learned rules
    rules_result = sb.table('junior_patterns') \
        .select('rule_text') \
        .eq('is_rule', True) \
        .execute()
    learned_rules = '\n'.join([f"- {r['rule_text']}" for r in (rules_result.data or [])]) or 'None yet.'

    model = route_junior(action_type, confidence)
    junior = ChatAnthropic(model=model, max_tokens=800)

    resp = junior.invoke(f"""You are Junior, the adversarial critic for JRIH (Juniper Rose Investments & Holdings).
Your sole purpose: protect the organism. Be skeptical. Be precise.

RULES:
1. Check if this serves the north star: $100M+ assets, Florida dominance, national scale.
2. Check if the confidence score is justified by the evidence.
3. Identify risks the proposer may have missed.
4. Check compliance with learned rules below.
5. Never approve something you don't understand fully.

Learned Rules:
{learned_rules}

DECISION TO REVIEW:
Division: {division}
Action type: {action_type}
Confidence: {confidence}
Description: {decision_description}
{f'Additional context: {context}' if context else ''}

Respond with JSON:
{{"verdict": "approve|reject|revise",
  "reason": "specific reason",
  "risk_flags": ["list of identified risks"],
  "suggested_revision": "if verdict is revise, what should change"}}

JSON:""")

    try:
        text = resp.content
        start = text.find('{')
        end = text.rfind('}') + 1
        result = json.loads(text[start:end])
    except Exception:
        result = {'verdict': 'reject', 'reason': 'Failed to parse critique', 'risk_flags': ['parse_error']}

    result['model_used'] = model
    return result


def log_rejection(division: str, action_type: str, reason: str):
    """Log rejection pattern to system namespace for learning."""
    sb.table('thoughts').insert({
        'content': f"JUNIOR PATTERN: [{division}] {action_type} rejected. Reason: {reason}",
        'source': 'system',
        'entry_type': 'observation',
        'agent': 'junior-learning',
        'tags': ['junior-pattern', division, action_type],
        'confidence': 1.0,
    }).execute()


def get_active_rules() -> list:
    """Get all active Junior rules."""
    result = sb.table('junior_patterns') \
        .select('*') \
        .eq('is_rule', True) \
        .order('created_at', desc=True) \
        .execute()
    return result.data or []


def run_learning_loop():
    """Weekly: analyze rejection patterns, write new rules."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Pull all rejection patterns from the past week
    patterns = sb.table('thoughts') \
        .select('content, tags') \
        .contains('tags', ['junior-pattern']) \
        .gte('created_at', week_ago) \
        .execute()

    if not patterns.data or len(patterns.data) < 2:
        print("Not enough patterns to learn from this week.")
        return

    # Count pattern reasons
    reason_counts = {}
    for p in patterns.data:
        content = p['content']
        # Extract reason after "Reason: "
        if 'Reason: ' in content:
            reason = content.split('Reason: ', 1)[1]
            key = reason[:100]  # Normalize
            reason_counts[key] = reason_counts.get(key, 0) + 1

    # Patterns appearing 2+ times become rules
    new_rules = []
    for reason, count in reason_counts.items():
        if count >= 2:
            # Check if rule already exists
            existing = sb.table('junior_patterns') \
                .select('id') \
                .ilike('description', f'%{reason[:50]}%') \
                .eq('is_rule', True) \
                .execute()

            if not existing.data:
                # Generate rule text
                sonnet = ChatAnthropic(model=MODELS['sonnet'], max_tokens=300)
                resp = sonnet.invoke(f"""Convert this rejection pattern into a clear, actionable rule for Junior (JRIH adversarial critic).
Pattern seen {count} times: {reason}

Write ONE rule. Be specific. Start with "ALWAYS" or "NEVER" or "REQUIRE".""")

                rule_text = resp.content.strip()

                sb.table('junior_patterns').insert({
                    'pattern_type': 'rejection_reason',
                    'description': reason,
                    'occurrence_count': count,
                    'is_rule': True,
                    'rule_text': rule_text,
                }).execute()

                new_rules.append(rule_text)
                print(f"  NEW RULE: {rule_text}")

    print(f"\nLearning complete. {len(new_rules)} new rules written. {len(reason_counts)} patterns analyzed.")
    return new_rules


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python junior.py review <description> [--confidence N] [--type TYPE]")
        print("  python junior.py rules")
        print("  python junior.py learn")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'review':
        desc = sys.argv[2] if len(sys.argv) > 2 else 'No description'
        conf = 0.8
        atype = 'memory'
        for i, arg in enumerate(sys.argv):
            if arg == '--confidence' and i + 1 < len(sys.argv):
                conf = float(sys.argv[i + 1])
            if arg == '--type' and i + 1 < len(sys.argv):
                atype = sys.argv[i + 1]
        result = critique(desc, action_type=atype, confidence=conf)
        print(json.dumps(result, indent=2))

    elif cmd == 'rules':
        rules = get_active_rules()
        if rules:
            for r in rules:
                print(f"  [{r['pattern_type']}] {r['rule_text']}")
                print(f"    Occurrences: {r['occurrence_count']} | Since: {r['first_seen'][:10]}")
        else:
            print("  No active rules yet. Run 'learn' after Junior has enough rejection patterns.")

    elif cmd == 'learn':
        run_learning_loop()
