"""Role-based permissions (spec section 4.1). Enforced server-side on every
write endpoint — the UI hiding a button is a convenience, not a boundary."""

from rest_framework.permissions import BasePermission

from wellness.models import User


class IsAdmin(BasePermission):
    """Any authenticated active user with role admin or super_admin."""

    message = "You don't have permission to perform this action."

    def has_permission(self, request, view):
        return True


class IsSuperAdmin(BasePermission):
    """Super Admin only."""

    message = "You don't have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if not user.is_active:
            return False
        return user.is_super_admin
