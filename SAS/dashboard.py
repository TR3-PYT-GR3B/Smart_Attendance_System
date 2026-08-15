import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncMonth
from accounts.models import User
from attendance.models import AttendanceRecord
from leave.models import LeaveRequest

def custom_dashboard_callback(request, context):
    total_users = User.objects.count()
    total_attendance_records = AttendanceRecord.objects.count()
    
    approved_count = User.objects.filter(is_approved=True).count()
    pending_count = User.objects.filter(is_approved=False).count()
    
    approval_labels = ["Approved", "Pending"]
    approval_counts = [approved_count, pending_count]

    time_filter = request.GET.get('filter', 'this_week')
    now = timezone.now()
    
    # 1. TIME-FILTERED ATTENDANCE DATA
    if time_filter == 'this_month':
        start_date = now - timedelta(days=30)
        records = AttendanceRecord.objects.filter(check_in_time__gte=start_date)
        grouped = records.annotate(day=TruncDay('check_in_time')).values('day').annotate(count=Count('id')).order_by('day')
        attendance_labels = [item['day'].strftime('%b %d') for item in grouped]
        
    elif time_filter == 'this_year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        records = AttendanceRecord.objects.filter(check_in_time__gte=start_date)
        grouped = records.annotate(month=TruncMonth('check_in_time')).values('month').annotate(count=Count('id')).order_by('month')
        attendance_labels = [item['month'].strftime('%b %Y') for item in grouped]
        
    else: 
        start_date = now - timedelta(days=7)
        records = AttendanceRecord.objects.filter(check_in_time__gte=start_date)
        grouped = records.annotate(day=TruncDay('check_in_time')).values('day').annotate(count=Count('id')).order_by('day')
        attendance_labels = [item['day'].strftime('%a, %b %d') for item in grouped]

    attendance_counts = [item['count'] for item in grouped]

    if not attendance_labels:
        attendance_labels = ["No Data Yet"]
        attendance_counts = [0]

    # 2. TIME-FILTERED LEAVE DATA
    leave_records = LeaveRequest.objects.filter(created_at__gte=start_date)
    total_leave = leave_records.count()
    approved_leave = leave_records.filter(status='approved').count()
    rejected_leave = leave_records.filter(status='rejected').count()
    pending_leave = leave_records.filter(status='pending').count()
    
    leave_labels = ["Approved", "Rejected", "Pending"]
    leave_data = [approved_leave, rejected_leave, pending_leave]

    # --- 3. NEW: RECENT ACTIVITY & PENDING ACTIONS ---
    # Get the 5 absolute most recent check-ins, grabbing user/location info efficiently
    recent_checkins = AttendanceRecord.objects.select_related('user', 'work_location').order_by('-check_in_time')[:5]
    
    # Get total global counts for items requiring administrator attention
    pending_leave_total = LeaveRequest.objects.filter(status='pending').count()
    flagged_attendance_total = AttendanceRecord.objects.filter(status='flagged').count()
    # -------------------------------------------------

    context.update({
        "total_users": total_users,
        "approved_count": approved_count,
        "pending_count": pending_count,
        "total_attendance_records": total_attendance_records,
        
        "attendance_labels": json.dumps(attendance_labels),
        "attendance_data": json.dumps(attendance_counts),
        "approval_labels": json.dumps(approval_labels),
        "approval_data": json.dumps(approval_counts),
        
        "total_leave": total_leave,
        "leave_labels": json.dumps(leave_labels),
        "leave_data": json.dumps(leave_data),
        
        "current_filter": time_filter,
        
        # Pass the new queries to the frontend template
        "recent_checkins": recent_checkins,
        "pending_leave_total": pending_leave_total,
        "flagged_attendance_total": flagged_attendance_total,
    })
    
    return context