from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsApprovedWorker

from .models import LeaveType, LeaveRequest
from .serializers import LeaveTypeSerializer, LeaveRequestSerializer

class LeaveTypeListView(generics.ListAPIView):
    """
    GET /api/leave/types/
    List active leave types available for request.
    """
    queryset = LeaveType.objects.filter(is_active=True)
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]


class LeaveRequestListCreateView(generics.ListCreateAPIView):
    """
    GET /api/leave/requests/
    POST /api/leave/requests/
    List the user's leave requests, or create a new one.
    """
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated, IsApprovedWorker]

    def get_queryset(self):
        return LeaveRequest.objects.filter(user=self.request.user)
