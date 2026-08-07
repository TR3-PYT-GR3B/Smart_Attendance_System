"""
Enrolment endpoints.

Enrolment is available to any authenticated worker, including one still awaiting
approval — there is no reason to make them wait idle when they could be getting
set up. The approval gate sits on attendance instead.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditAction, AuditLog

from .models import FaceProfile
from .serializers import (
    EnrollmentStatusSerializer,
    FaceProfileSerializer,
    LivenessCaptureSerializer,
)


class LivenessCaptureView(APIView):
    """
    ``POST /api/enrollment/liveness-capture/``

    Accepts the frames from a guided capture sequence and stores the resulting
    reference embedding. All liveness checking and encoding happens server-side;
    the client only uploads images.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LivenessCaptureSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()

        # Distinguish first enrolment from re-enrolment in the audit trail —
        # repeated re-enrolments are worth being able to spot.
        was_created = getattr(serializer, 'was_created', True)
        action = AuditAction.FACE_ENROLLED if was_created else AuditAction.FACE_RE_ENROLLED

        AuditLog.log(
            action,
            actor=request.user,
            subject=request.user,
            target=profile,
            description=(
                f'Face profile {"created" if was_created else "replaced"} from '
                f'{profile.frames_captured} frame(s).'
            ),
            metadata={
                'frames_captured': profile.frames_captured,
                'liveness_score': profile.liveness_score,
                'model_version': profile.model_version,
            },
            request=request,
        )

        return Response(
            {
                'profile': FaceProfileSerializer(profile).data,
                'detail': (
                    'Face enrolled successfully.' if was_created
                    else 'Face profile updated successfully.'
                ),
            },
            status=status.HTTP_201_CREATED if was_created else status.HTTP_200_OK,
        )


class EnrollmentStatusView(APIView):
    """
    ``GET /api/enrollment/status/``

    Reports whether the caller is enrolled and approved, plus a ``next_step``
    hint so the app can route without duplicating the rules client-side.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = FaceProfile.objects.filter(user=user, is_active=True).first()

        is_enrolled = profile is not None

        # Enrolment comes first, then approval — a worker cannot be verified
        # without a reference face, and cannot check in without approval.
        if not is_enrolled:
            next_step = 'enroll_face'
        elif not user.is_approved:
            next_step = 'await_approval'
        elif not user.can_record_attendance:
            next_step = 'contact_administrator'
        else:
            next_step = 'ready_to_check_in'

        payload = {
            'is_enrolled': is_enrolled,
            'is_approved': user.is_approved,
            'can_record_attendance': user.can_record_attendance,
            'next_step': next_step,
            'profile': profile,
        }

        return Response(EnrollmentStatusSerializer(payload).data)


class DeleteFaceDataView(APIView):
    """
    ``DELETE /api/enrollment/face-data/``

    Supports the deletion right the plan calls for under its compliance
    checklist: biometric data is sensitive personal data, so a worker must be
    able to have theirs removed.

    The profile row is deleted outright rather than deactivated — a retained
    "inactive" embedding is still biometric data on file. The audit entry
    records that the deletion happened without keeping the vector itself.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        profile = FaceProfile.objects.filter(user=request.user).first()

        if profile is None:
            return Response(
                {'detail': 'No face profile to delete.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Capture the details for the log before the row disappears.
        metadata = {
            'enrolled_at': profile.enrolled_at.isoformat(),
            'model_version': profile.model_version,
            'frames_captured': profile.frames_captured,
        }

        profile.delete()

        AuditLog.log(
            AuditAction.FACE_DATA_DELETED,
            actor=request.user,
            subject=request.user,
            description='Face profile deleted at the worker\'s request.',
            metadata=metadata,
            request=request,
        )

        return Response(
            {
                'detail': (
                    'Face data deleted. You will need to enrol again before '
                    'recording attendance.'
                )
            },
            status=status.HTTP_200_OK,
        )
