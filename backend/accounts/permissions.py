"""
Shared DRF permission classes.

Role checks live here rather than in individual views so that the same rule is
applied everywhere. The plan requires these to be enforced in the API and not
only hidden in the UI: a department manager who calls an endpoint directly must
still be limited to their own department.

Two ideas are kept separate on purpose:

* **Permission classes** decide whether a request may proceed at all.
* ``scope_queryset_to_user`` narrows *which rows* a caller may see. A manager is
  allowed to list attendance records, but only for their own department, and
  that is a filtering concern rather than an allow/deny one.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Administrators only."""

    message = 'Administrator access is required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_administrator)


class IsDeptManagerOrAdmin(BasePermission):
    """
    Department managers and administrators.

    Passing this check does not by itself grant access to every department —
    views must still narrow their queryset with ``scope_queryset_to_user``.
    """

    message = 'Department manager or administrator access is required.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_administrator or user.is_department_manager


class IsOwnerOrAdmin(BasePermission):
    """
    The worker the object belongs to, or an administrator.

    Object ownership is read from ``user``, ``recipient`` or ``subject``,
    whichever the model uses, so the same class works across attendance
    records, notifications and audit entries.
    """

    message = 'You may only access your own records.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.is_administrator:
            return True

        owner = getattr(obj, 'user', None) or getattr(obj, 'recipient', None) \
            or getattr(obj, 'subject', None)

        # A user object is its own owner (e.g. the /me endpoint).
        if owner is None and hasattr(obj, 'email'):
            owner = obj

        return owner == user


class IsApprovedWorker(BasePermission):
    """
    Gate for actions a worker may only take once an administrator has approved
    their account — recording attendance, above all.

    ``can_record_attendance`` on the user model combines approval, active state
    and employment status, so the rule stays in one place.
    """

    message = 'Your account is not ready for attendance. Complete password and face setup first.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # Administrators are exempt: they need to exercise these endpoints to
        # test and to record attendance on a worker's behalf.
        if user.is_administrator:
            return True

        return user.can_record_attendance


class IsAdminOrReadOnly(BasePermission):
    """Anyone authenticated may read; only administrators may write."""

    message = 'Only administrators may modify this resource.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_administrator


def scope_queryset_to_user(queryset, user, user_field='user'):
    """
    Narrow a queryset to the rows a caller is entitled to see.

    * Administrators see everything.
    * Department managers see the departments they manage.
    * Everyone else sees only their own rows.

    ``user_field`` names the path from the model to its owning user, so a model
    that stores the worker under a different name (or reaches a department
    through a relation) can still be scoped with the same helper.
    """
    if user.is_administrator:
        return queryset

    if user.is_department_manager:
        managed_department_ids = user.managed_departments.values_list('id', flat=True)

        # Prefer a direct department column when the model has one; otherwise
        # follow the owning user's department.
        field_names = {field.name for field in queryset.model._meta.get_fields()}
        if 'department' in field_names:
            return queryset.filter(department_id__in=managed_department_ids)

        return queryset.filter(**{f'{user_field}__department_id__in': managed_department_ids})

    return queryset.filter(**{user_field: user})
