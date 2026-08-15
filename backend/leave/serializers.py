from rest_framework import serializers
from .models import LeaveType, LeaveRequest

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'description', 'requires_document']


class LeaveRequestSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    total_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'leave_type', 'leave_type_name', 'start_date', 'end_date',
            'reason', 'status', 'total_days', 'created_at'
        ]
        read_only_fields = ['status', 'created_at']

    def create(self, validated_data):
        # Attach the current user to the leave request
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)
