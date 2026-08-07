"""Admin registration for face enrolment."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import FaceProfile


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
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

    # The embedding is a 512-value vector — useful to inspect, never to hand-edit.
    readonly_fields = ['embedding', 'embedding_dim', 'enrolled_at', 'updated_at']

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
