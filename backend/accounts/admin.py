"""Admin registration for the custom user model."""

from django.contrib import admin, messages
from unfold.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.utils.translation import gettext_lazy as _

from audit.models import AuditAction, AuditLog

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin,  ModelAdmin):
    """User admin driven by email rather than a username."""

    change_password_form = AdminPasswordChangeForm
    ordering = ['email']
    actions = ['authorize_face_reenrollment']

    list_display = [
        'email',
        'get_full_name',
        'role',
        'department',
        'is_approved',
        'must_change_password',
        'get_face_enrollment_state',
        'employment_status',
        'is_active',
    ]
    list_filter = [
        'role',
        'is_approved',
        'must_change_password',
        'face_enrollment_allowed',
        'employment_status',
        'is_active',
        'department',
    ]
    search_fields = ['email', 'first_name', 'last_name', 'phone', 'employee_id']
    list_select_related = ['department']
    readonly_fields = [
        'biometric_consent_at',
        'biometric_consent_version',
        'last_login',
        'date_joined',
    ]

    fieldsets = [
        (None, {'fields': ['email', 'password']}),
        (_('Personal info'), {
            'fields': ['first_name', 'last_name', 'phone', 'employee_id'],
        }),
        (_('Role & placement'), {'fields': ['role', 'department']}),
        (_('Account state'), {
            'fields': [
                'is_approved',
                'employment_status',
                'must_change_password',
                'face_enrollment_allowed',
                'biometric_consent_at',
                'biometric_consent_version',
            ],
        }),
        (_('Permissions'), {
            'fields': ['is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'],
        }),
        (_('Important dates'), {'fields': ['last_login', 'date_joined']}),
    ]

    add_fieldsets = [
        (None, {
            'classes': ['wide'],
            'fields': [
                'email',
                'password1',
                'password2',
                'first_name',
                'last_name',
                'phone',
                'employee_id',
                'role',
                'department',
            ],
        }),
    ]

    def save_model(self, request, obj, form, change):
        """Provision new dashboard-created workers for the first-login flow."""
        is_new = not change
        if is_new:
            obj.is_approved = True
            obj.must_change_password = not obj.is_superuser
            obj.face_enrollment_allowed = not obj.is_superuser

        super().save_model(request, obj, form, change)

        if is_new:
            AuditLog.log(
                AuditAction.ACCOUNT_REGISTERED,
                actor=request.user,
                subject=obj,
                target=obj,
                description=f'{obj.email} was provisioned by an administrator.',
                metadata={
                    'department_id': obj.department_id,
                    'role': obj.role,
                    'must_change_password': obj.must_change_password,
                },
                request=request,
            )

    @admin.action(description=_('Authorize selected users for face re-enrollment'))
    def authorize_face_reenrollment(self, request, queryset):
        """Reset biometric state after the administrator verifies the worker."""
        reset_count = 0
        for user in queryset:
            profile = getattr(user, 'face_profile', None)
            if profile is not None:
                AuditLog.log(
                    AuditAction.FACE_DATA_DELETED,
                    actor=request.user,
                    subject=user,
                    target=profile,
                    description='Existing face removed during administrator-authorized reset.',
                    metadata={'model_version': profile.model_version},
                    request=request,
                )
                profile.delete()

            user.biometric_consent_at = None
            user.biometric_consent_version = ''
            user.face_enrollment_allowed = True
            user.save(
                update_fields=[
                    'biometric_consent_at',
                    'biometric_consent_version',
                    'face_enrollment_allowed',
                ]
            )
            AuditLog.log(
                AuditAction.OTHER,
                actor=request.user,
                subject=user,
                target=user,
                description='Administrator authorized the user for face re-enrollment.',
                request=request,
            )
            reset_count += 1

        self.message_user(
            request,
            _('%(count)d user(s) authorized for face re-enrollment.')
            % {'count': reset_count},
            messages.SUCCESS,
        )

    @admin.display(description=_('face enrollment'), boolean=True)
    def get_face_enrollment_state(self, obj):
        profile = getattr(obj, 'face_profile', None)
        return bool(profile and profile.is_active)

    @admin.display(description=_('name'), ordering='first_name')
    def get_full_name(self, obj):
        return obj.get_full_name() or '—'
