"""Admin registration for worker document review."""

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import (
    DocumentRequest,
    DocumentRequestStatus,
    DocumentStatus,
    WorkerDocument,
)


@admin.register(DocumentRequest)
class DocumentRequestAdmin(ModelAdmin):
    """Issue and track office document requests from the dashboard."""

    list_display = [
        'title',
        'department',
        'document_type',
        'status',
        'submission_progress',
        'due_date',
        'is_overdue',
        'created_at',
    ]
    list_filter = ['status', 'document_type', 'due_date', 'department__organization']
    search_fields = [
        'title',
        'department__name',
        'department__organization__name',
    ]
    autocomplete_fields = ['department']
    list_select_related = ['department', 'department__organization', 'created_by']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    actions = ['close_selected', 'cancel_selected', 'reopen_selected']

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description=_('verified employees'))
    def submission_progress(self, obj):
        if obj.department_id is None:
            return '—'
        employee_count = obj.department.members.filter(
            is_active=True,
            employment_status='active',
        ).count()
        verified_count = (
            obj.submissions.filter(status=DocumentStatus.VERIFIED)
            .values('user_id')
            .distinct()
            .count()
        )
        return f'{verified_count} / {employee_count}'

    @admin.action(description=_('Close selected document requests'))
    def close_selected(self, request, queryset):
        queryset.exclude(status=DocumentRequestStatus.CANCELLED).update(
            status=DocumentRequestStatus.CLOSED
        )

    @admin.action(description=_('Cancel selected document requests'))
    def cancel_selected(self, request, queryset):
        queryset.exclude(status=DocumentRequestStatus.CLOSED).update(
            status=DocumentRequestStatus.CANCELLED
        )

    @admin.action(description=_('Reopen selected document requests'))
    def reopen_selected(self, request, queryset):
        queryset.update(status=DocumentRequestStatus.ACTIVE)


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
class WorkerDocumentAdmin(ModelAdmin):
    list_display = [
        'title',
        'request',
        'user',
        'document_type',
        'status',
        'expiry_date',
        'get_days_until_expiry',
        'uploaded_at',
    ]
    list_filter = ['status', 'document_type', ExpiryWindowFilter, 'user__department']
    search_fields = ['title', 'user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['request', 'user', 'reviewed_by']
    autocomplete_fields = ['request', 'user', 'reviewed_by']
    date_hierarchy = 'uploaded_at'
    actions = ['verify_selected']

    readonly_fields = ['original_filename', 'file_size_bytes', 'uploaded_at', 'updated_at']

    fieldsets = [
        (None, {'fields': ['request', 'user', 'document_type', 'title', 'description']}),
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
