"""
Attendance endpoints.

Check-in and check-out both require an approved account (``IsApprovedWorker``)
and both run the full server-side verification described in ``services.py``.
Verification attempts are written for failed requests as well as successful ones,
so a refused check-in can still be investigated afterwards.

A failed check-in returns HTTP 403 rather than 400: the request was well formed,
the worker simply did not pass verification. The body explains which gate failed
so the app can give a useful message rather than a generic error.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsApprovedWorker, scope_queryset_to_user
from audit.models import AuditAction, AuditLog

from organisations.models import WorkLocation

from .models import AttendanceRecord, VerificationAttempt
from .serializers import (
    AttendanceRecordSerializer,
    CheckInSerializer,
    CheckOutSerializer,
    VerificationAttemptSerializer,
    WorkLocationBriefSerializer,
)
from .services import evaluate_punctuality, verify_attendance


def _verification_payload(result):
    """Flatten a ``VerificationResult`` into the response shape."""
    return {
        'passed': result.passed,
        'gps_passed': result.gps.passed,
        'gps_distance_meters': (
            round(result.gps.score, 1) if result.gps.score is not None else None
        ),
        'liveness_passed': result.liveness.passed,
        'liveness_score': (
            round(result.liveness.score, 3) if result.liveness.score is not None else None
        ),
        'face_passed': result.face.passed,
        'face_score': (
            round(result.face.score, 3) if result.face.score is not None else None
        ),
        'failure_reasons': result.failure_reasons,
    }


class CheckInView(APIView):
    """
    ``POST /api/attendance/check-in/``

    Runs GPS, liveness and face verification server-side, and creates an
    ``AttendanceRecord`` only if all three pass. On failure nothing is recorded
    as attendance, but the individual attempts are kept.
    """

    permission_classes = [IsAuthenticated, IsApprovedWorker]

    def post(self, request):
        serializer = CheckInSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        work_location = serializer.validated_data['work_location']
        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        challenge_id = serializer.validated_data['challenge_id']
        frames = serializer.validated_data['frames']

        # Every gate runs here, on the server, and each one is logged.
        result = verify_attendance(
            user=request.user,
            work_location=work_location,
            latitude=latitude,
            longitude=longitude,
            challenge_id=challenge_id,
            frames=frames,
            request=request,
        )

        if not result.passed:
            AuditLog.log(
                AuditAction.CHECK_IN_REJECTED,
                actor=request.user,
                subject=request.user,
                target=work_location,
                description=f'Check-in refused at {work_location.name}.',
                metadata=_verification_payload(result),
                request=request,
            )

            return Response(
                {
                    'detail': 'Check-in could not be verified.',
                    'verification': _verification_payload(result),
                },
                # The request was valid; the worker failed verification.
                status=status.HTTP_403_FORBIDDEN,
            )

        check_in_time = timezone.now()
        attendance_status, minutes_late = evaluate_punctuality(work_location, check_in_time)

        try:
            with transaction.atomic():
                record = AttendanceRecord.objects.create(
                    user=request.user,
                    work_location=work_location,
                    check_in_time=check_in_time,
                    check_in_latitude=latitude,
                    check_in_longitude=longitude,
                    check_in_distance_meters=result.distance_meters,
                    check_in_face_score=result.face_score,
                    status=attendance_status,
                    minutes_late=minutes_late,
                )

                VerificationAttempt.objects.filter(
                    id__in=[attempt.pk for attempt in result.attempts],
                ).update(attendance_record=record)
        except IntegrityError:
            return Response(
                {'detail': 'You already have an open attendance session.'},
                status=status.HTTP_409_CONFLICT,
            )

        AuditLog.log(
            AuditAction.CHECK_IN,
            actor=request.user,
            subject=request.user,
            target=record,
            description=(
                f'Checked in at {work_location.name} '
                f'({record.get_status_display().lower()}).'
            ),
            metadata={
                **_verification_payload(result),
                'minutes_late': minutes_late,
            },
            request=request,
        )

        return Response(
            {
                'record': AttendanceRecordSerializer(record).data,
                'verification': _verification_payload(result),
                'detail': (
                    f'Checked in at {work_location.name}.'
                    + (f' Recorded as late by {minutes_late} minutes.' if minutes_late else '')
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class CheckOutView(APIView):
    """
    ``POST /api/attendance/check-out/``

    Closes the caller's open session. Verification runs again — the same worker
    should be leaving the same site — but a failure here is handled differently
    from a failed check-in.
    """

    permission_classes = [IsAuthenticated, IsApprovedWorker]

    def post(self, request):
        serializer = CheckOutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        record = serializer.validated_data['attendance_record']
        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        challenge_id = serializer.validated_data['challenge_id']
        frames = serializer.validated_data['frames']

        result = verify_attendance(
            user=request.user,
            work_location=record.work_location,
            latitude=latitude,
            longitude=longitude,
            challenge_id=challenge_id,
            frames=frames,
            request=request,
            attendance_record=record,
        )

        if not result.passed:
            AuditLog.log(
                AuditAction.CHECK_OUT,
                actor=request.user,
                subject=request.user,
                target=record,
                description=f'Check-out refused at {record.work_location.name}.',
                metadata=_verification_payload(result),
                request=request,
            )

            return Response(
                {
                    'detail': 'Check-out could not be verified.',
                    'verification': _verification_payload(result),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            record.check_out_time = timezone.now()
            record.check_out_latitude = latitude
            record.check_out_longitude = longitude
            record.check_out_distance_meters = result.distance_meters
            record.check_out_face_score = result.face_score
            record.save()

        AuditLog.log(
            AuditAction.CHECK_OUT,
            actor=request.user,
            subject=request.user,
            target=record,
            description=f'Checked out of {record.work_location.name}',
            metadata={
                **_verification_payload(result),
                'duration_minutes': record.duration_minutes,
            },
            request=request,
        )

        return Response(
            {
                'record': AttendanceRecordSerializer(record).data,
                'verification': _verification_payload(result),
                'detail': f'Checked out of {record.work_location.name}.',
            },
            status=status.HTTP_200_OK,
        )


class AttendanceHistoryView(generics.ListAPIView):
    """
    ``GET /api/attendance/history/``

    A worker's own records; for a department manager, their department's; for an
    administrator, everything. Scoping is applied to the queryset rather than
    trusted to a query parameter.

    Supports ``?from=YYYY-MM-DD``, ``?to=YYYY-MM-DD`` and ``?status=``.
    """

    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            AttendanceRecord.objects
            .select_related('work_location', 'work_location__department', 'user')
        )

        # Role-based narrowing happens before any user-supplied filter, so a
        # filter cannot widen what the caller is allowed to see.
        queryset = scope_queryset_to_user(queryset, self.request.user)

        params = self.request.query_params

        date_from = params.get('from')
        if date_from:
            queryset = queryset.filter(check_in_time__date__gte=date_from)

        date_to = params.get('to')
        if date_to:
            queryset = queryset.filter(check_in_time__date__lte=date_to)

        record_status = params.get('status')
        if record_status:
            queryset = queryset.filter(status=record_status)

        return queryset


class AvailableWorkLocationView(generics.ListAPIView):
    """Active attendance sites the caller is authorized to use."""

    serializer_class = WorkLocationBriefSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = WorkLocation.objects.filter(is_active=True).select_related('department')
        user = self.request.user
        if user.is_administrator:
            return queryset
        if user.is_department_manager:
            return queryset.filter(department__manager=user)
        if user.department_id is None:
            return queryset.none()
        return queryset.filter(department_id=user.department_id)


class CurrentSessionView(APIView):
    """
    ``GET /api/attendance/current/``

    The caller's open session, if any. Lets the app show "Check out" instead of
    "Check in" without pulling the whole history.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        record = (
            AttendanceRecord.objects
            .filter(user=request.user, check_out_time__isnull=True)
            .select_related('work_location', 'work_location__department')
            .first()
        )

        if record is None:
            return Response({'has_open_session': False, 'record': None})

        return Response({
            'has_open_session': True,
            'record': AttendanceRecordSerializer(record).data,
        })


class MyVerificationAttemptsView(generics.ListAPIView):
    """
    ``GET /api/attendance/my-attempts/``

    The caller's own verification history. The plan asks for this in the worker
    self-view so someone who was flagged or refused can see the reason rather
    than having to ask an administrator.
    """

    serializer_class = VerificationAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = VerificationAttempt.objects.filter(user=self.request.user)

        # ?result=false surfaces just the failures, which is the common case.
        result_filter = self.request.query_params.get('result')
        if result_filter is not None:
            queryset = queryset.filter(result=result_filter.lower() in ('true', '1', 'yes'))

        return queryset
