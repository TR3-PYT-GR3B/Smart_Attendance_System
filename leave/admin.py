"""Admin registration for leave management."""

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .models import LeaveBalance, LeaveRequest, LeaveStatus, LeaveType


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'default_days_per_year',
        'requires_document',
        'is_paid',
        'is_active',
    ]
    list_filter = ['requires_document', 'is_paid', 'is_active']
    search_fields = ['name']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'leave_type',
        'start_date',
        'end_date',
        'get_total_days',
        'status',
        'reviewed_by',
        'created_at',
    ]
    list_filter = ['status', 'leave_type', 'start_date', 'user__department']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'reason']
    list_select_related = ['user', 'leave_type', 'reviewed_by']
    autocomplete_fields = ['user', 'reviewed_by', 'supporting_document']
    date_hierarchy = 'start_date'
    actions = ['approve_selected']

    readonly_fields = ['created_at', 'updated_at']

    fieldsets = [
        (None, {'fields': ['user', 'leave_type', 'status']}),
        (_('Dates'), {'fields': ['start_date', 'end_date', 'reason']}),
        (_('Supporting document'), {'fields': ['supporting_document']}),
        (_('Review'), {
            'fields': ['reviewed_by', 'reviewed_at', 'rejection_reason', 'review_notes'],
        }),
        (_('Timestamps'), {'fields': ['created_at', 'updated_at']}),
    ]

    @admin.display(description=_('days'))
    def get_total_days(self, obj):
        return obj.total_days

    @admin.action(description=_('Approve selected leave requests'))
    def approve_selected(self, request, queryset):
        """Approve pending requests and draw the days down from each balance."""
        pending = queryset.filter(status=LeaveStatus.PENDING)
        approved = 0

        for leave_request in pending:
            leave_request.approve(reviewer=request.user)
            approved += 1

        skipped = queryset.count() - approved
        self.message_user(
            request,
            _('%(count)d leave request(s) approved.') % {'count': approved},
            messages.SUCCESS,
        )
        if skipped:
            self.message_user(
                request,
                _('%(count)d already-reviewed request(s) were skipped.') % {'count': skipped},
                messages.WARNING,
            )


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'leave_type',
        'year',
        'days_allocated',
        'days_used',
        'get_days_remaining',
    ]
    list_filter = ['year', 'leave_type', 'user__department']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['user', 'leave_type']
    autocomplete_fields = ['user']

    @admin.display(description=_('days remaining'))
    def get_days_remaining(self, obj):
        return obj.days_remaining
