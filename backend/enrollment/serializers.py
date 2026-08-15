"""Serializers for one-time, server-verified face enrollment."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.models import EmploymentStatus, User

from .models import ChallengePurpose, FaceProfile, LivenessChallenge
from .services import (
    FACE_MODEL_VERSION,
    FaceProcessingError,
    average_embeddings,
    consume_and_process_liveness_challenge,
)


class FaceProfileSerializer(serializers.ModelSerializer):
    """Public profile metadata; the biometric embedding is never returned."""

    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = FaceProfile
        fields = [
            'id',
            'user_email',
            'embedding_dim',
            'model_version',
            'liveness_score',
            'frames_captured',
            'is_active',
            'enrolled_at',
            'updated_at',
        ]
        read_only_fields = fields


class LivenessChallengeRequestSerializer(serializers.Serializer):
    purpose = serializers.ChoiceField(choices=ChallengePurpose.choices)


class LivenessChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LivenessChallenge
        fields = ['id', 'purpose', 'actions', 'expires_at']
        read_only_fields = fields


class LivenessPoseCheckSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=[
        ('straight', 'Straight'),
        ('turn_left', 'Turn left'),
        ('turn_right', 'Turn right'),
    ])
    frame = serializers.ImageField()

    def validate_frame(self, frame):
        max_bytes = int(getattr(settings, 'LIVENESS_MAX_FRAME_BYTES', 2 * 1024 * 1024))
        if frame.size > max_bytes:
            raise serializers.ValidationError(
                f'The capture must be no larger than {max_bytes // (1024 * 1024)} MB.'
            )
        return frame


class LivenessCaptureSerializer(serializers.Serializer):
    """Bind the authenticated worker to one face after an active challenge."""

    challenge_id = serializers.UUIDField()
    frames = serializers.ListField(
        child=serializers.ImageField(),
        min_length=3,
        max_length=3,
        help_text='One frame for each server-issued liveness action, in order.',
    )
    biometric_consent = serializers.BooleanField(
        help_text='The worker must explicitly accept biometric processing.',
    )

    def validate_biometric_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                'Biometric consent is required before a face can be enrolled.'
            )
        return value

    def validate_frames(self, frames):
        max_bytes = int(getattr(settings, 'LIVENESS_MAX_FRAME_BYTES', 2 * 1024 * 1024))
        if any(frame.size > max_bytes for frame in frames):
            raise serializers.ValidationError(
                f'Each capture frame must be no larger than {max_bytes // (1024 * 1024)} MB.'
            )
        return frames

    def validate(self, attrs):
        user = self.context['request'].user
        if user.must_change_password:
            raise serializers.ValidationError(
                {'detail': 'Change the administrator-issued password before face enrollment.'}
            )
        if not user.is_approved or not user.is_active:
            raise serializers.ValidationError(
                {'detail': 'This account is not active for face enrollment.'}
            )
        if user.employment_status != EmploymentStatus.ACTIVE:
            raise serializers.ValidationError(
                {'detail': 'Only active workers can enroll a face.'}
            )
        if FaceProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                {'detail': 'A face is already enrolled. Ask an administrator to reset it.'}
            )
        if not user.face_enrollment_allowed:
            raise serializers.ValidationError(
                {'detail': 'An administrator must authorize face re-enrollment.'}
            )
        return attrs

    def create(self, validated_data):
        request_user = self.context['request'].user
        try:
            processed = consume_and_process_liveness_challenge(
                user=request_user,
                challenge_id=validated_data['challenge_id'],
                purpose=ChallengePurpose.ENROLLMENT,
                frames=validated_data['frames'],
            )
        except FaceProcessingError as error:
            raise serializers.ValidationError({'detail': str(error)}) from error

        if not processed.liveness.passed:
            raise serializers.ValidationError(
                {
                    'detail': 'The active liveness challenge was not completed.',
                    'liveness_reason': processed.liveness.reason,
                }
            )

        try:
            reference_embedding = average_embeddings(processed.embeddings)
        except FaceProcessingError as error:
            raise serializers.ValidationError({'detail': str(error)}) from error

        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request_user.pk)
            if FaceProfile.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {'detail': 'A face is already enrolled for this account.'}
                )
            if not user.face_enrollment_allowed:
                raise serializers.ValidationError(
                    {'detail': 'Face enrollment is no longer authorized.'}
                )

            profile = FaceProfile.objects.create(
                user=user,
                embedding=reference_embedding,
                embedding_dim=len(reference_embedding),
                model_version=FACE_MODEL_VERSION,
                liveness_score=processed.liveness.score,
                frames_captured=len(processed.analyses),
                is_active=True,
            )
            user.biometric_consent_at = timezone.now()
            user.biometric_consent_version = getattr(
                settings,
                'BIOMETRIC_CONSENT_VERSION',
                '',
            )
            user.face_enrollment_allowed = False
            user.save(
                update_fields=[
                    'biometric_consent_at',
                    'biometric_consent_version',
                    'face_enrollment_allowed',
                ]
            )

        self.processed_liveness = processed
        return profile


class EnrollmentStatusSerializer(serializers.Serializer):
    is_enrolled = serializers.BooleanField()
    is_approved = serializers.BooleanField()
    must_change_password = serializers.BooleanField()
    consent_required = serializers.BooleanField()
    can_record_attendance = serializers.BooleanField()
    next_step = serializers.CharField()
    profile = FaceProfileSerializer(allow_null=True)
