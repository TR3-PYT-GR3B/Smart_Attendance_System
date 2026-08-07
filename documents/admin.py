"""Admin registration for worker document review."""

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .models import DocumentStatus, WorkerDocument


class ExpiryWindowFilter(admin.SimpleListFilter):
    """Filter by how close a document is to expiring, for chasing renewals."""

    title = _('expiry window')
    parameter_name = 'expiry_window'

    def lookups(self, request, model_admin):
        return [
            ('expired', _('Already expired')),
            ('30', _('Expiring within 30 days')),
            ('90', _('Expiring within 90 days')),
            ('none', _('No expiry date')),
        ]

    def queryset(self, request, queryset):
        from datetime import timedelta

        from django.utils import timezone

        today = timezone.localdate()
        value = self.value()

        if value == 'expired':
            return queryset.filter(expiry_date__lt=today)
        if value == '30':
            return queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
        if value == '90':
            return queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=90))
        if value == 'none':
            return queryset.filter(expiry_date__isnull=True)
        return queryset


@admin.register(WorkerDocument)
class WorkerDocumentAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'user',
        'document_type',
        'status',
        'expiry_date',
        'get_days_until_expiry',
        'uploaded_at',
    ]
    list_filter = ['status', 'document_type', ExpiryWindowFilter, 'user__department']
    search_fields = ['title', 'user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['user', 'reviewed_by']
    autocomplete_fields = ['user', 'reviewed_by']
    date_hierarchy = 'uploaded_at'
    actions = ['verify_selected']

    readonly_fields = ['original_filename', 'file_size_bytes', 'uploaded_at', 'updated_at']

    fieldsets = [
        (None, {'fields': ['user', 'document_type', 'title', 'description']}),
        (_('File'), {'fields': ['file', 'original_filename', 'file_size_bytes']}),
        (_('Validity'), {'fields': ['issue_date', 'expiry_date']}),
        (_('Review'), {'fields': ['status', 'reviewed_by', 'reviewed_at', 'rejection_reason']}),
        (_('Timestamps'), {'fields': ['uploaded_at', 'updated_at']}),
    ]

    @admin.display(description=_('days to expiry'), ordering='expiry_date')
    def get_days_until_expiry(self, obj):
        remaining = obj.days_until_expiry
        if remaining is None:
            return '—'
        if remaining < 0:
            return _('expired')
        return remaining

    @admin.action(description=_('Mark selected documents verified'))
    def verify_selected(self, request, queryset):
        pending = queryset.filter(status=DocumentStatus.PENDING_REVIEW)
        verified = 0

        for document in pending:
            document.verify(reviewer=request.user)
            verified += 1

        self.message_user(
            request,
            _('%(count)d document(s) verified.') % {'count': verified},
            messages.SUCCESS,
        )
