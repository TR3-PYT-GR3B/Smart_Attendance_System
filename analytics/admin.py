"""Admin registration for analytics summaries."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    DepartmentDailySummary,
    WorkerDailySummary,
    WorkerMonthlySummary,
)


class SummaryBaseAdmin(admin.ModelAdmin):
    """Shared admin surface for the roll-up tables; all read-only."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(WorkerDailySummary)
class WorkerDailySummaryAdmin(SummaryBaseAdmin):
    list_display = [
        'user',
        'department',
        'date',
        'days_present',
        'days_late',
        'days_absent',
        'days_on_leave',
        'generated_at',
    ]
    list_filter = ['date', 'department']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['user', 'department']
    date_hierarchy = 'date'


@admin.register(WorkerMonthlySummary)
class WorkerMonthlySummaryAdmin(SummaryBaseAdmin):
    list_display = [
        'user',
        'department',
        'year',
        'month',
        'get_attendance_rate',
        'get_punctuality_rate',
        'leave_days_used',
        'generated_at',
    ]
    list_filter = ['year', 'month', 'department']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['user', 'department']

    @admin.display(description=_('attendance %'))
    def get_attendance_rate(self, obj):
        return obj.attendance_rate

    @admin.display(description=_('punctuality %'))
    def get_punctuality_rate(self, obj):
        return obj.punctuality_rate


@admin.register(DepartmentDailySummary)
class DepartmentDailySummaryAdmin(SummaryBaseAdmin):
    list_display = [
        'department',
        'date',
        'get_attendance_rate',
        'headcount',
        'flagged_attempts',
        'generated_at',
    ]
    list_filter = ['date', 'department']
    search_fields = ['department__name']
    list_select_related = ['department']
    date_hierarchy = 'date'

    @admin.display(description=_('attendance %'))
    def get_attendance_rate(self, obj):
        return obj.attendance_rate
