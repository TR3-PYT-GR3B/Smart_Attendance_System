"""Admin registration for attendance records and verification attempts."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import AttendanceRecord, VerificationAttempt


class VerificationAttemptInline(admin.TabularInline):
    """The GPS/liveness/face checks behind a given record, shown read-only."""

    model = VerificationAttempt
    extra = 0
    can_delete = False
    fields = ['attempt_type', 'result', 'score', 'threshold_used', 'reason_failed', 'timestamp']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'work_location',
        'check_in_time',
        'check_out_time',
        'status',
        'minutes_late',
        'is_manual_override',
    ]
    list_filter = ['status', 'is_manual_override', 'work_location', 'check_in_time']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    list_select_related = ['user', 'work_location']
    autocomplete_fields = ['user', 'work_location', 'overridden_by']
    date_hierarchy = 'check_in_time'
    inlines = [VerificationAttemptInline]

    readonly_fields = ['created_at', 'updated_at']

    fieldsets = [
        (None, {'fields': ['user', 'work_location', 'status', 'minutes_late']}),
        (_('Check-in'), {
            'fields': [
                'check_in_time',
                'check_in_latitude',
                'check_in_longitude',
                'check_in_distance_meters',
                'check_in_face_score',
            ],
        }),
        (_('Check-out'), {
            'fields': [
                'check_out_time',
                'check_out_latitude',
                'check_out_longitude',
                'check_out_distance_meters',
                'check_out_face_score',
            ],
        }),
        (_('Manual override'), {
            'fields': ['is_manual_override', 'overridden_by', 'override_reason'],
            'classes': ['collapse'],
            'description': _('For edge cases such as a failed camera or GPS reading.'),
        }),
        (_('Other'), {'fields': ['notes', 'created_at', 'updated_at']}),
    ]


@admin.register(VerificationAttempt)
class VerificationAttemptAdmin(admin.ModelAdmin):
    """Read-only view of the verification log; entries are never hand-edited."""

    list_display = [
        'user',
        'attempt_type',
        'result',
        'score',
        'threshold_used',
        'work_location',
        'timestamp',
    ]
    list_filter = ['attempt_type', 'result', 'timestamp', 'work_location']
    search_fields = ['user__email', 'reason_failed', 'ip_address']
    list_select_related = ['user', 'work_location']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]
