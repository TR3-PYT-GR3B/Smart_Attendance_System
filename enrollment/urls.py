"""Enrolment routes, mounted at ``/api/enrollment/``."""

from django.urls import path

from .views import DeleteFaceDataView, EnrollmentStatusView, LivenessCaptureView

app_name = 'enrollment'

urlpatterns = [
    path('liveness-capture/', LivenessCaptureView.as_view(), name='liveness-capture'),
    path('status/', EnrollmentStatusView.as_view(), name='status'),

    # Deletion right for biometric data (see the plan's compliance checklist).
    path('face-data/', DeleteFaceDataView.as_view(), name='delete-face-data'),
]
