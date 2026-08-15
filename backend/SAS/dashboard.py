"""Dynamic data for the custom Django administration dashboard."""

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceStatus
from leave.models import LeaveRequest, LeaveStatus


def custom_dashboard_callback(request, context):
    """Add attendance, account, and leave summaries to the admin context."""
    total_users = User.objects.count()
    total_attendance_records = AttendanceRecord.objects.count()
    approved_count = User.objects.filter(is_approved=True).count()
    pending_count = User.objects.filter(is_approved=False).count()

    time_filter = request.GET.get('filter', 'this_week')
    if time_filter not in {'this_week', 'this_month', 'this_year'}:
        time_filter = 'this_week'

    now = timezone.now()
    if time_filter == 'this_month':
        start_date = now - timedelta(days=30)
        grouped_attendance = (
            AttendanceRecord.objects.filter(check_in_time__gte=start_date)
            .annotate(period=TruncDay('check_in_time'))
            .values('period')
            .annotate(count=Count('id'))
            .order_by('period')
        )
        attendance_label_format = '%b %d'
    elif time_filter == 'this_year':
        start_date = now.replace(
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        grouped_attendance = (
            AttendanceRecord.objects.filter(check_in_time__gte=start_date)
            .annotate(period=TruncMonth('check_in_time'))
            .values('period')
            .annotate(count=Count('id'))
            .order_by('period')
        )
        attendance_label_format = '%b %Y'
    else:
        start_date = now - timedelta(days=7)
        grouped_attendance = (
            AttendanceRecord.objects.filter(check_in_time__gte=start_date)
            .annotate(period=TruncDay('check_in_time'))
            .values('period')
            .annotate(count=Count('id'))
            .order_by('period')
        )
        attendance_label_format = '%a, %b %d'

    grouped_attendance = list(grouped_attendance)
    attendance_labels = [
        item['period'].strftime(attendance_label_format)
        for item in grouped_attendance
    ]
    attendance_counts = [item['count'] for item in grouped_attendance]
    if not attendance_labels:
        attendance_labels = ['No data yet']
        attendance_counts = [0]

    leave_records = LeaveRequest.objects.filter(created_at__gte=start_date)
    leave_labels = ['Approved', 'Rejected', 'Pending']
    leave_data = [
        leave_records.filter(status=LeaveStatus.APPROVED).count(),
        leave_records.filter(status=LeaveStatus.REJECTED).count(),
        leave_records.filter(status=LeaveStatus.PENDING).count(),
    ]

    recent_checkins = (
        AttendanceRecord.objects.select_related('user', 'work_location')
        .order_by('-check_in_time')[:5]
    )

    context.update(
        {
            'total_users': total_users,
            'approved_count': approved_count,
            'pending_count': pending_count,
            'total_attendance_records': total_attendance_records,
            'attendance_labels': attendance_labels,
            'attendance_data': attendance_counts,
            'approval_labels': ['Approved', 'Pending'],
            'approval_data': [approved_count, pending_count],
            'total_leave': leave_records.count(),
            'leave_labels': leave_labels,
            'leave_data': leave_data,
            'current_filter': time_filter,
            'recent_checkins': recent_checkins,
            'pending_leave_total': LeaveRequest.objects.filter(
                status=LeaveStatus.PENDING,
            ).count(),
            'flagged_attendance_total': AttendanceRecord.objects.filter(
                status=AttendanceStatus.FLAGGED,
            ).count(),
        }
    )
    return context
