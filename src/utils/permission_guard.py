"""Runtime permission enforcement for JRIH agents.

Each agent has a fixed set of allowed env vars and namespace access rules.
Operations are: "read", "write". Namespaces map to Supabase row partitions.

Permission violations raise PermissionError and are automatically appended to
the audit log controlled by PERMISSION_AUDIT_LOG (default: permission_audit.log).

Public API:
    check_permission(agent_id, operation, namespace) -> bool
    check_env_access(agent_id, env_var) -> bool
    audit_permission_violation(agent_id, operation, namespace) -> None
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

# ─── Permission matrix ────────────────────────────────────────────────────────

# fmt: off
_ENV_VARS: dict[str, frozenset[str]] = {
    "juniper":   frozenset({"ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "ORG_ID"}),
    "rose":      frozenset({"ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"}),
    "junior":    frozenset({"ANTHROPIC_API_KEY", "SUPABASE_URL"}),
    "juno":      frozenset({"SUPABASE_URL"}),
    "advisor":   frozenset({"ANTHROPIC_API_KEY", "SUPABASE_URL"}),
    "hoj_agent": frozenset({"SUPABASE_URL"}),
}

# Namespaces each agent may write to (read is restricted to own namespaces)
_WRITE_NAMESPACES: dict[str, frozenset[str]] = {
    "juniper":   frozenset({"jrih", "brand", "critique", "intel", "ops", "hoj", "strategic", "system"}),
    "rose":      frozenset({"brand", "critique"}),
    "junior":    frozenset({"intel"}),
    "juno":      frozenset({"ops"}),
    "advisor":   frozenset({"strategic"}),
    "hoj_agent": frozenset({"hoj"}),
}

_READ_NAMESPACES: dict[str, frozenset[str]] = {
    "juniper":   frozenset({"jrih", "brand", "critique", "intel", "ops", "hoj", "strategic", "system"}),
    "rose":      frozenset({"brand", "critique"}),
    "junior":    frozenset({"intel"}),
    "juno":      frozenset({"ops"}),
    "advisor":   frozenset({"strategic"}),
    "hoj_agent": frozenset({"hoj"}),
}
# fmt: on

_KNOWN_AGENTS: frozenset[str] = frozenset(_ENV_VARS.keys())

# ─── Audit log ────────────────────────────────────────────────────────────────

_AUDIT_LOG_PATH: str = os.environ.get("PERMISSION_AUDIT_LOG", "permission_audit.log")


def audit_permission_violation(agent_id: str, operation: str, namespace: str) -> None:
    """Append a timestamped violation record to the audit log file.

    The log path is controlled by the PERMISSION_AUDIT_LOG env var
    (default: permission_audit.log in the working directory).

    Never raises — I/O failures are silently swallowed so callers always
    proceed to the PermissionError that follows this call.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"{ts} VIOLATION agent={agent_id!r} op={operation!r} ns={namespace!r}\n"
    try:
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except OSError:
        pass


# ─── Public API ───────────────────────────────────────────────────────────────


def check_permission(agent_id: str, operation: str, namespace: str) -> bool:
    """Return True if agent_id is allowed to perform operation on namespace.

    Raises PermissionError on any violation (unknown/empty agent, forbidden
    namespace) and logs the event to the audit file before raising.
    ValueError is raised for an unrecognised operation string.
    """
    if not agent_id:
        audit_permission_violation(repr(agent_id), operation, namespace)
        raise PermissionError(
            f"agent_id must be a non-empty string, got {agent_id!r}"
        )

    if agent_id not in _KNOWN_AGENTS:
        audit_permission_violation(agent_id, operation, namespace)
        raise PermissionError(f"Unknown agent: '{agent_id}'")

    op = operation.lower()
    if op not in ("read", "write"):
        raise ValueError(f"operation must be 'read' or 'write', got '{operation}'")

    allowed = _WRITE_NAMESPACES[agent_id] if op == "write" else _READ_NAMESPACES[agent_id]

    if namespace not in allowed:
        audit_permission_violation(agent_id, operation, namespace)
        raise PermissionError(
            f"Agent '{agent_id}' is not permitted to {op} namespace '{namespace}'. "
            f"Allowed {op} namespaces: {sorted(allowed)}"
        )
    return True


def check_env_access(agent_id: str, env_var: str) -> bool:
    """Return True if agent_id is permitted to read env_var.

    Validates the permission only — does NOT read the variable value. After this
    check passes, call os.getenv(env_var) to retrieve the actual value.

    Raises PermissionError on violation and logs to the audit file before raising.
    """
    if not agent_id:
        audit_permission_violation(repr(agent_id), "env_access", env_var)
        raise PermissionError(
            f"agent_id must be a non-empty string, got {agent_id!r}"
        )

    if agent_id not in _KNOWN_AGENTS:
        audit_permission_violation(agent_id, "env_access", env_var)
        raise PermissionError(f"Unknown agent: '{agent_id}'")

    if env_var not in _ENV_VARS[agent_id]:
        audit_permission_violation(agent_id, "env_access", env_var)
        raise PermissionError(
            f"Agent '{agent_id}' is not permitted to access env var '{env_var}'. "
            f"Allowed vars: {sorted(_ENV_VARS[agent_id])}"
        )
    return True
