"""Attendance routes, mounted at ``/api/attendance/``."""

from django.urls import path

from .views import (
    AttendanceHistoryView,
    AvailableWorkLocationView,
    CheckInView,
    CheckOutView,
    CurrentSessionView,
    MyVerificationAttemptsView,
)

app_name = 'attendance'

urlpatterns = [
    path('check-in/', CheckInView.as_view(), name='check-in'),
    path('check-out/', CheckOutView.as_view(), name='check-out'),

    path('history/', AttendanceHistoryView.as_view(), name='history'),
    path('locations/', AvailableWorkLocationView.as_view(), name='locations'),
    path('current/', CurrentSessionView.as_view(), name='current-session'),

    # Worker self-view of their own verification attempts, including failures.
    path('my-attempts/', MyVerificationAttemptsView.as_view(), name='my-attempts'),
]
