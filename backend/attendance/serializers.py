"""
Serializers for attendance.

The input serializers accept only what a phone can honestly report: a captured
frame and a pair of coordinates. There is deliberately no field for a similarity
score, a liveness score, or a "verified" flag — those are computed in
``services.py`` on the server. A client that sends them anyway is simply ignored,
since unknown fields are not bound.
"""

from django.conf import settings
from rest_framework import serializers

from organisations.models import WorkLocation

from .models import AttendanceRecord, VerificationAttempt


def validate_capture_frames(frames):
    """Bound image uploads before they reach the CPU-heavy face pipeline."""
    max_bytes = int(getattr(settings, 'LIVENESS_MAX_FRAME_BYTES', 2 * 1024 * 1024))
    if any(frame.size > max_bytes for frame in frames):
        raise serializers.ValidationError(
            f'Each capture frame must be no larger than {max_bytes // (1024 * 1024)} MB.'
        )
    return frames


class WorkLocationBriefSerializer(serializers.ModelSerializer):
    """Minimal site details for nesting in attendance payloads."""

    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = WorkLocation
        fields = [
            'id',
            'name',
            'department_name',
            'latitude',
            'longitude',
            'radius_meters',
            'shift_start_time',
            'shift_end_time',
        ]


class VerificationAttemptSerializer(serializers.ModelSerializer):
    """
    Read-only view of one verification check.

    Exposed to workers so they can see why an attempt was refused — the plan
    calls for this in the worker self-view, and "you were 340 m away" is a much
    better experience than an unexplained rejection.
    """

    attempt_type_display = serializers.CharField(
        source='get_attempt_type_display',
        read_only=True,
    )

    class Meta:
        model = VerificationAttempt
        fields = [
            'id',
            'attempt_type',
            'attempt_type_display',
            'result',
            'score',
            'threshold_used',
            'reason_failed',
            'timestamp',
        ]
        read_only_fields = fields


class AttendanceRecordSerializer(serializers.ModelSerializer):
    """Read-only view of a work session, used by the history endpoint."""

    work_location = WorkLocationBriefSerializer(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id',
            'user_email',
            'work_location',
            'check_in_time',
            'check_in_latitude',
            'check_in_longitude',
            'check_in_distance_meters',
            'check_in_face_score',
            'check_out_time',
            'check_out_latitude',
            'check_out_longitude',
            'check_out_distance_meters',
            'check_out_face_score',
            'status',
            'status_display',
            'minutes_late',
            'duration_minutes',
            'is_open',
            'is_manual_override',
            'override_reason',
            'notes',
            'created_at',
        ]
        read_only_fields = fields


class CheckInSerializer(serializers.Serializer):
    """
    Input for ``POST /api/attendance/check-in/``.

    The client supplies its location plus the three frames requested by the
    server's short-lived liveness challenge. All verdicts remain server-side.
    """

    work_location_id = serializers.PrimaryKeyRelatedField(
        # Only active sites — a decommissioned location should not accept
        # check-ins even if an old client still has its id cached.
        queryset=WorkLocation.objects.filter(is_active=True),
        source='work_location',
    )
    latitude = serializers.FloatField(min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(min_value=-180.0, max_value=180.0)
    challenge_id = serializers.UUIDField()
    frames = serializers.ListField(
        child=serializers.ImageField(),
        min_length=3,
        max_length=3,
        help_text='The three frames, in exactly the order requested by the challenge.',
    )

    def validate_frames(self, frames):
        return validate_capture_frames(frames)

    def validate(self, attrs):
        """
        Reject a second open check-in before doing any face processing.

        Cheap guard, and it prevents a worker accumulating overlapping sessions
        by tapping the button twice.
        """
        user = self.context['request'].user
        work_location = attrs['work_location']

        if user.is_department_manager:
            allowed = user.managed_departments.filter(pk=work_location.department_id).exists()
        elif user.is_administrator:
            allowed = True
        else:
            allowed = user.department_id == work_location.department_id

        if not allowed:
            raise serializers.ValidationError(
                {'work_location_id': 'This location is not assigned to your department.'}
            )

        open_record = AttendanceRecord.objects.filter(
            user=user,
            check_out_time__isnull=True,
        ).first()

        if open_record is not None:
            raise serializers.ValidationError(
                {
                    'detail': (
                        f'You are already checked in at '
                        f'{open_record.work_location.name}. Check out first.'
                    ),
                    'open_record_id': open_record.id,
                }
            )

        return attrs


class CheckOutSerializer(serializers.Serializer):
    """
    Input for ``POST /api/attendance/check-out/``.

    The site is not asked for — it is taken from the open check-in record, so a
    worker cannot check out of somewhere they never checked into.
    """

    latitude = serializers.FloatField(min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(min_value=-180.0, max_value=180.0)
    challenge_id = serializers.UUIDField()
    frames = serializers.ListField(
        child=serializers.ImageField(),
        min_length=3,
        max_length=3,
        help_text='The three frames, in exactly the order requested by the challenge.',
    )

    def validate_frames(self, frames):
        return validate_capture_frames(frames)

    def validate(self, attrs):
        """Find the open session and attach it for the view to complete."""
        user = self.context['request'].user

        open_record = AttendanceRecord.objects.filter(
            user=user,
            check_out_time__isnull=True,
        ).select_related('work_location').first()

        if open_record is None:
            raise serializers.ValidationError(
                {'detail': 'No open check-in found. Check in before checking out.'}
            )

        attrs['attendance_record'] = open_record
        return attrs


class VerificationOutcomeSerializer(serializers.Serializer):
    """
    Shape of the verification detail returned with a check-in or check-out.

    Reports each gate separately so the app can show precisely what failed
    rather than a single opaque error.
    """

    passed = serializers.BooleanField()
    gps_passed = serializers.BooleanField()
    gps_distance_meters = serializers.FloatField(allow_null=True)
    liveness_passed = serializers.BooleanField()
    liveness_score = serializers.FloatField(allow_null=True)
    face_passed = serializers.BooleanField()
    face_score = serializers.FloatField(allow_null=True)
    failure_reasons = serializers.ListField(child=serializers.CharField())
