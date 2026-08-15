from django.urls import path
from .views import LeaveTypeListView, LeaveRequestListCreateView

app_name = 'leave'

urlpatterns = [
    path('types/', LeaveTypeListView.as_view(), name='leave-types'),
    path('requests/', LeaveRequestListCreateView.as_view(), name='leave-requests'),
]
