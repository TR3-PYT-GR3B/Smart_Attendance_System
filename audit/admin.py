"""Admin registration for the audit trail."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only interface to the audit trail — entries are append-only."""

    list_display = [
        'action',
        'actor',
        'subject',
        'get_target',
        'timestamp',
    ]
    list_filter = ['action', 'timestamp']
    search_fields = [
        'actor__email',
        'subject__email',
        'description',
        'target_app',
        'target_model',
        'target_id',
    ]
    list_select_related = ['actor', 'subject']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    @admin.display(description=_('target'))
    def get_target(self, obj):
        if obj.target_app and obj.target_model and obj.target_id:
            return f'{obj.target_app}.{obj.target_model}#{obj.target_id}'
        return '—'
