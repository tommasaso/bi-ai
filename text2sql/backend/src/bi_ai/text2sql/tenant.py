"""Resolve the current user's tenant_id from Flask/Superset context."""
from __future__ import annotations
import re


def get_current_tenant_id() -> int | None:
    """
    Resolve tenant_id from Flask context:
    1. JWT custom claim 'tenant_id' (production path via Keycloak)
    2. Superset RLS filter clause 'tenant_id = X' for the current user's roles
    3. None if not found (dev fallback — no tenant isolation)
    """
    try:
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        if claims and "tenant_id" in claims:
            return int(claims["tenant_id"])
    except Exception:
        pass

    try:
        from flask_login import current_user
        from superset import db as superset_db

        if current_user and not current_user.is_anonymous:
            role_ids = [r.id for r in current_user.roles]
            if role_ids:
                result = superset_db.session.execute(
                    """
                    SELECT rlsf.clause
                    FROM row_level_security_filters rlsf
                    JOIN rls_filter_roles rfr ON rfr.rls_filter_id = rlsf.id
                    WHERE rfr.role_id = ANY(:role_ids)
                    LIMIT 1
                    """,
                    {"role_ids": role_ids},
                ).fetchone()
                if result:
                    match = re.search(r"tenant_id\s*=\s*(\d+)", result[0])
                    if match:
                        return int(match.group(1))
    except Exception:
        pass

    return None
