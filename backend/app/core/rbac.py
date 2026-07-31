from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from fastapi import Depends, HTTPException, status

from app.api.deps import CurrentUser, get_current_user


class Permission(StrEnum):
    OWNER_DASHBOARD_READ = "owner.dashboard.read"
    OWNER_MANAGERS_WRITE = "owner.managers.write"
    OWNER_FINANCE_WRITE = "owner.finance.write"
    OWNER_MODELS_WRITE = "owner.models.write"
    OWNER_AUDIT_READ = "owner.audit.read"
    SOFTWARE_READ = "software.read"
    SOFTWARE_WRITE = "software.write"
    KNOWLEDGE_WRITE = "knowledge.write"
    SNAPSHOT_PUBLISH = "snapshot.publish"
    USERS_WRITE = "users.write"
    API_KEYS_WRITE = "api_keys.write"
    REQUESTS_READ = "requests.read"
    QUALITY_WRITE = "quality.write"
    REPORT_REQUEST = "report.request"
    CONNECTOR_OPERATE = "connector.operate"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "system_owner": set(Permission),
    "software_admin": {
        Permission.SOFTWARE_READ,
        Permission.SOFTWARE_WRITE,
        Permission.KNOWLEDGE_WRITE,
        Permission.SNAPSHOT_PUBLISH,
        Permission.USERS_WRITE,
        Permission.API_KEYS_WRITE,
        Permission.REQUESTS_READ,
        Permission.QUALITY_WRITE,
        Permission.REPORT_REQUEST,
    },
    "report_user": {Permission.REPORT_REQUEST},
    "connector_operator": {Permission.CONNECTOR_OPERATE, Permission.REQUESTS_READ},
}


def effective_permissions(role_names: Iterable[str]) -> set[str]:
    permissions: set[Permission] = set()
    for role_name in role_names:
        permissions |= ROLE_PERMISSIONS.get(role_name, set())
    return {permission.value for permission in permissions}


def require_permissions(*required: Permission):
    async def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        permissions = effective_permissions(current_user.roles)
        missing = [permission.value for permission in required if permission.value not in permissions]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "missing_permissions": missing},
            )
        return current_user

    return dependency
