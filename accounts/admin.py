"""Admin registration for the custom user model."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin,  ModelAdmin):
    """User admin driven by email rather than a username."""

    change_password_form = AdminPasswordChangeForm
    ordering = ['email']

    list_display = [
        'email',
        'get_full_name',
        'role',
        'department',
        'is_approved',
        'employment_status',
        'is_active',
    ]
    list_filter = ['role', 'is_approved', 'employment_status', 'is_active', 'department']
    search_fields = ['email', 'first_name', 'last_name', 'phone', 'employee_id']
    list_select_related = ['department']

    fieldsets = [
        (None, {'fields': ['email', 'password']}),
        (_('Personal info'), {
            'fields': ['first_name', 'last_name', 'phone', 'employee_id'],
        }),
        (_('Role & placement'), {'fields': ['role', 'department']}),
        (_('Account state'), {
            'fields': ['is_approved', 'employment_status', 'biometric_consent_at'],
        }),
        (_('Permissions'), {
            'fields': ['is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'],
        }),
        (_('Important dates'), {'fields': ['last_login', 'date_joined']}),
    ]

    add_fieldsets = [
        (None, {
            'classes': ['wide'],
            'fields': ['email', 'password1', 'password2', 'role', 'department'],
        }),
    ]

    @admin.display(description=_('name'), ordering='first_name')
    def get_full_name(self, obj):
        return obj.get_full_name() or '—'
