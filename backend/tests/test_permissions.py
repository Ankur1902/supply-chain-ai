"""Unit tests for the RBAC permission table (app/auth/permissions.py)."""

from app.auth.permissions import Permission, Role, role_has_permission


def test_admin_has_every_permission():
    for permission in Permission:
        assert role_has_permission([Role.ADMIN.value], permission)


def test_viewer_has_read_only_access():
    assert role_has_permission([Role.VIEWER.value], Permission.SHIPMENTS_READ)
    assert role_has_permission([Role.VIEWER.value], Permission.SUPPLIERS_READ)
    assert role_has_permission([Role.VIEWER.value], Permission.ANALYTICS_READ)


def test_viewer_cannot_write_or_use_ai():
    assert not role_has_permission([Role.VIEWER.value], Permission.SHIPMENTS_WRITE)
    assert not role_has_permission([Role.VIEWER.value], Permission.AI_USE)
    assert not role_has_permission([Role.VIEWER.value], Permission.SCENARIOS_RUN)
    assert not role_has_permission([Role.VIEWER.value], Permission.USERS_MANAGE)


def test_analyst_can_use_ai_but_not_write_shipments():
    assert role_has_permission([Role.ANALYST.value], Permission.AI_USE)
    assert role_has_permission([Role.ANALYST.value], Permission.SCENARIOS_RUN)
    assert not role_has_permission([Role.ANALYST.value], Permission.SHIPMENTS_WRITE)


def test_operations_manager_can_write_shipments_and_alerts():
    assert role_has_permission([Role.OPERATIONS_MANAGER.value], Permission.SHIPMENTS_WRITE)
    assert role_has_permission([Role.OPERATIONS_MANAGER.value], Permission.ALERTS_WRITE)
    assert not role_has_permission([Role.OPERATIONS_MANAGER.value], Permission.USERS_MANAGE)


def test_unknown_role_name_grants_nothing():
    assert not role_has_permission(["nonexistent_role"], Permission.SHIPMENTS_READ)


def test_every_ai_use_role_also_has_full_read_access():
    """Documented in docs/ai-system.md: the AI tool registry doesn't
    re-check per-resource RBAC per tool call, which is only safe because
    every role granted AI_USE also has full read access. This test pins
    that invariant so a future role change can't silently break it."""
    from app.auth.permissions import ROLE_PERMISSIONS

    read_perms = {Permission.SHIPMENTS_READ, Permission.SUPPLIERS_READ, Permission.ALERTS_READ, Permission.ANALYTICS_READ}
    for role, perms in ROLE_PERMISSIONS.items():
        if Permission.AI_USE in perms:
            assert read_perms.issubset(perms), f"{role} has AI_USE but not full read access"
