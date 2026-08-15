"""Admin registration for face enrolment."""

from django.contrib import admin, messages
from unfold.admin import ModelAdmin
from django.utils.translation import gettext_lazy as _

from audit.models import AuditAction, AuditLog

from .models import FaceProfile, LivenessChallenge


@admin.register(FaceProfile)
class FaceProfileAdmin(ModelAdmin):
    actions = ['authorize_reenrollment']
    list_display = [
        'user',
        'liveness_score',
        'frames_captured',
        'model_version',
        'is_active',
        'enrolled_at',
    ]
    list_filter = ['is_active', 'model_version', 'enrolled_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['user']
    autocomplete_fields = ['user']

    fieldsets = [
        (None, {'fields': ['user', 'is_active']}),
        (_('Biometric data'), {
            'fields': ['embedding', 'embedding_dim', 'model_version'],
            'classes': ['collapse'],
            'description': _('Generated server-side at enrolment; not editable by hand.'),
        }),
        (_('Capture quality'), {'fields': ['liveness_score', 'frames_captured', 'reference_image']}),
        (_('Timestamps'), {'fields': ['enrolled_at', 'updated_at']}),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    @admin.action(description=_('Reset selected workers for verified re-enrollment'))
    def authorize_reenrollment(self, request, queryset):
        reset_count = 0
        for profile in queryset.select_related('user'):
            user = profile.user
            AuditLog.log(
                AuditAction.FACE_DATA_DELETED,
                actor=request.user,
                subject=user,
                target=profile,
                description='Existing face removed after administrator-authorized reset.',
                metadata={
                    'model_version': profile.model_version,
                    'enrolled_at': profile.enrolled_at.isoformat(),
                },
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
            reset_count += 1

        self.message_user(
            request,
            _('%(count)d worker(s) authorized for re-enrollment.') % {'count': reset_count},
            messages.SUCCESS,
        )


@admin.register(LivenessChallenge)
class LivenessChallengeAdmin(ModelAdmin):
    list_display = ['id', 'user', 'purpose', 'created_at', 'expires_at', 'used_at']
    list_filter = ['purpose', 'created_at', 'used_at']
    search_fields = ['user__email']
    list_select_related = ['user']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]
