"""
Role-based access control.

Roles: admin, operations_manager, analyst, viewer.

Permission model is intentionally simple and explicit (a static table) rather
than a generic policy engine — with four roles and ~10 resource scopes, a
lookup table is easier to audit than a rules DSL. See docs/security.md.
"""

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    OPERATIONS_MANAGER = "operations_manager"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(str, Enum):
    SHIPMENTS_READ = "shipments:read"
    SHIPMENTS_WRITE = "shipments:write"
    SUPPLIERS_READ = "suppliers:read"
    SUPPLIERS_WRITE = "suppliers:write"
    ALERTS_READ = "alerts:read"
    ALERTS_WRITE = "alerts:write"
    ANALYTICS_READ = "analytics:read"
    AI_USE = "ai:use"
    MODELS_READ = "models:read"
    MODELS_WRITE = "models:write"
    SCENARIOS_RUN = "scenarios:run"
    USERS_MANAGE = "users:manage"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.OPERATIONS_MANAGER: {
        Permission.SHIPMENTS_READ,
        Permission.SHIPMENTS_WRITE,
        Permission.SUPPLIERS_READ,
        Permission.SUPPLIERS_WRITE,
        Permission.ALERTS_READ,
        Permission.ALERTS_WRITE,
        Permission.ANALYTICS_READ,
        Permission.AI_USE,
        Permission.MODELS_READ,
        Permission.SCENARIOS_RUN,
    },
    Role.ANALYST: {
        Permission.SHIPMENTS_READ,
        Permission.SUPPLIERS_READ,
        Permission.ALERTS_READ,
        Permission.ANALYTICS_READ,
        Permission.AI_USE,
        Permission.MODELS_READ,
        Permission.SCENARIOS_RUN,
    },
    Role.VIEWER: {
        Permission.SHIPMENTS_READ,
        Permission.SUPPLIERS_READ,
        Permission.ALERTS_READ,
        Permission.ANALYTICS_READ,
    },
}


def role_has_permission(role_names: list[str], permission: Permission) -> bool:
    for name in role_names:
        try:
            role = Role(name)
        except ValueError:
            continue
        if permission in ROLE_PERMISSIONS.get(role, set()):
            return True
    return False
