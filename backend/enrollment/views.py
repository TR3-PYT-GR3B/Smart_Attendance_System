"""One-time face enrollment and active-liveness challenge endpoints."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditAction, AuditLog

from django.utils import timezone

from .models import ChallengePurpose, FaceProfile, LivenessChallenge
from .serializers import (
    EnrollmentStatusSerializer,
    FaceProfileSerializer,
    LivenessChallengeRequestSerializer,
    LivenessChallengeSerializer,
    LivenessPoseCheckSerializer,
    LivenessCaptureSerializer,
)
from .services import (
    FaceProcessingError,
    analyze_face,
    issue_liveness_challenge,
    validate_guided_pose,
)


class LivenessChallengeView(APIView):
    """Issue a short-lived challenge for enrollment or attendance capture."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LivenessChallengeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = serializer.validated_data['purpose']

        if purpose == ChallengePurpose.ENROLLMENT:
            if request.user.next_step != 'enroll_face':
                return Response(
                    {
                        'detail': 'Face enrollment is not currently authorized.',
                        'next_step': request.user.next_step,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        elif not request.user.can_record_attendance:
            return Response(
                {
                    'detail': 'This account is not ready to record attendance.',
                    'next_step': request.user.next_step,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        challenge = issue_liveness_challenge(request.user, purpose)
        return Response(
            LivenessChallengeSerializer(challenge).data,
            status=status.HTTP_201_CREATED,
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
        request.user.refresh_from_db()

        processed = serializer.processed_liveness

        AuditLog.log(
            AuditAction.CONSENT_GIVEN,
            actor=request.user,
            subject=request.user,
            target=request.user,
            description='Biometric consent accepted during first-login enrollment.',
            metadata={'consent_version': request.user.biometric_consent_version},
            request=request,
        )

        AuditLog.log(
            AuditAction.FACE_ENROLLED,
            actor=request.user,
            subject=request.user,
            target=profile,
            description=f'Face profile created from {profile.frames_captured} challenge frames.',
            metadata={
                'frames_captured': profile.frames_captured,
                'liveness_score': profile.liveness_score,
                'model_version': profile.model_version,
                'yaw_by_action': processed.liveness.yaw_by_action,
                'continuity_score': processed.liveness.continuity_score,
            },
            request=request,
        )

        return Response(
            {
                'profile': FaceProfileSerializer(profile).data,
                'detail': 'Face enrolled successfully.',
                'next_step': 'ready_to_check_in',
            },
            status=status.HTTP_201_CREATED,
        )


class LivenessPoseCheckView(APIView):
    """Check one low-resolution browser frame without consuming a challenge."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LivenessPoseCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            challenge = LivenessChallenge.objects.get(
                pk=data['challenge_id'],
                user=request.user,
            )
        except LivenessChallenge.DoesNotExist:
            return Response(
                {'detail': 'The face capture session could not be found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if challenge.used_at is not None:
            return Response(
                {'detail': 'The face capture session has already been completed.'},
                status=status.HTTP_409_CONFLICT,
            )
        if challenge.expires_at <= timezone.now():
            return Response(
                {'detail': 'The face capture session expired. Please start again.'},
                status=status.HTTP_410_GONE,
            )
        if data['action'] not in challenge.actions:
            return Response(
                {'detail': 'That position is not part of this face capture session.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            analysis = analyze_face(data['frame'])
            result = validate_guided_pose(analysis, data['action'])
        except FaceProcessingError as error:
            message = str(error)
            if 'No face detected' in message:
                message = 'No face detected. Move into the circle.'
            elif 'Multiple faces' in message:
                message = 'Only one person should be visible.'
            else:
                message = 'Your face could not be confirmed. Hold still and try again.'
            return Response({'accepted': False, 'message': message})

        return Response({
            'accepted': result.accepted,
            'message': result.message,
        })


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

        payload = {
            'is_enrolled': is_enrolled,
            'is_approved': user.is_approved,
            'must_change_password': user.must_change_password,
            'consent_required': user.biometric_consent_at is None,
            'can_record_attendance': user.can_record_attendance,
            'next_step': user.next_step,
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
        request.user.biometric_consent_at = None
        request.user.biometric_consent_version = ''
        # Deletion is not an authorization to bind a replacement face. An
        # administrator must verify the worker and explicitly reset enrollment.
        request.user.face_enrollment_allowed = False
        request.user.save(
            update_fields=[
                'biometric_consent_at',
                'biometric_consent_version',
                'face_enrollment_allowed',
            ]
        )

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
                    'Face data deleted. Contact an administrator if enrollment '
                    'must be restored.'
                ),
                'next_step': 'contact_administrator',
            },
            status=status.HTTP_200_OK,
        )
