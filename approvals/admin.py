"""Admin registration for the account approval queue."""

from django.contrib import admin, messages
from unfold.admin import ModelAdmin
from django.utils.translation import gettext_lazy as _

from .models import AccountApprovalRequest, ApprovalStatus


@admin.register(AccountApprovalRequest)
class AccountApprovalRequestAdmin(ModelAdmin):
    list_display = [
        'user',
        'get_department',
        'status',
        'submission_count',
        'reviewed_by',
        'reviewed_at',
        'created_at',
    ]
    list_filter = ['status', 'created_at', 'user__department']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'user__employee_id']
    list_select_related = ['user', 'user__department', 'reviewed_by']
    autocomplete_fields = ['user', 'reviewed_by']
    date_hierarchy = 'created_at'
    actions = ['approve_selected', 'reject_selected']

    readonly_fields = ['submission_count', 'created_at', 'updated_at']

    fieldsets = [
        (None, {'fields': ['user', 'status', 'submission_count']}),
        (_('Review'), {
            'fields': ['reviewed_by', 'reviewed_at', 'rejection_reason', 'review_notes'],
        }),
        (_('Timestamps'), {'fields': ['created_at', 'updated_at']}),
    ]

    @admin.display(description=_('department'), ordering='user__department')
    def get_department(self, obj):
        return obj.user.department or '—'

    @admin.action(description=_('Approve selected requests'))
    def approve_selected(self, request, queryset):
        """Approve each pending request, flipping the worker's is_approved flag."""
        pending = queryset.filter(status=ApprovalStatus.PENDING)
        approved = 0

        for approval_request in pending:
            approval_request.approve(reviewer=request.user)
            approved += 1

        skipped = queryset.count() - approved
        self.message_user(
            request,
            _('%(count)d request(s) approved.') % {'count': approved},
            messages.SUCCESS,
        )
        if skipped:
            self.message_user(
                request,
                _('%(count)d already-reviewed request(s) were skipped.') % {'count': skipped},
                messages.WARNING,
            )

    @admin.action(description=_('Reject selected requests'))
    def reject_selected(self, request, queryset):
        """
        Reject in bulk with a placeholder reason.

        A specific reason is far more useful to the worker, so this is a
        fallback — prefer rejecting individually and writing the reason out.
        """
        pending = queryset.filter(status=ApprovalStatus.PENDING)
        rejected = 0

        for approval_request in pending:
            approval_request.reject(
                reviewer=request.user,
                reason=_('Rejected during bulk review. Contact your administrator for details.'),
            )
            rejected += 1

        self.message_user(
            request,
            _('%(count)d request(s) rejected.') % {'count': rejected},
            messages.SUCCESS,
        )
