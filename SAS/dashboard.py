import json
from accounts.models import User  # Adjust import based on your exact model name
from attendance.models import AttendanceRecord

def custom_dashboard_callback(request, context):
    """
    This function calculates stats and passes them to the dashboard template.
    """
    # 1. Calculate simple stats (KPIs)
    total_users = User.objects.count()
    total_attendance_records = AttendanceRecord.objects.count()
    # REAL DATA: Count users based on their approval status
 
    
    attendance_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    attendance_counts = [45, 52, 38, 60, 55]


    approved_count = User.objects.filter(is_approved=True).count()
    pending_count = User.objects.filter(is_approved=False).count()
    approval_labels = ["Approved", "Pending"]
    approval_counts = [approved_count, pending_count]


    # 2. Add them to the context dictionary
    context.update({
        "total_users": total_users,
        "approved_count":approved_count,
        "pending_count":pending_count,
        "total_attendance_records": total_attendance_records,
        # You can add chart data here later!
        "attendance_labels": json.dumps(attendance_labels),
        "attendance_data": json.dumps(attendance_counts),
        "approval_labels": json.dumps(approval_labels),
        "approval_data": json.dumps(approval_counts),
    })
    
    return context