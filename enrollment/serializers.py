"""
Serializers for face enrolment.

The client uploads frames; the server does the processing. No embedding is ever
accepted from the client — that would let a tampered app enrol whatever vector
it liked and then "match" against it later.
"""

from django.conf import settings
from rest_framework import serializers

from .models import FaceProfile
from .services import (
    FaceProcessingError,
    average_embeddings,
    estimate_liveness,
    generate_embedding,
)


class FaceProfileSerializer(serializers.ModelSerializer):
    """
    Read-only view of an enrolment.

    ``embedding`` is deliberately excluded. It is biometric data, the client has
    no use for it, and returning it would hand an attacker the exact vector they
    would need to forge a match.
    """

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


class LivenessCaptureSerializer(serializers.Serializer):
    """
    Enrolment from a guided capture sequence.

    The app walks the worker through a few poses ("look straight", "turn
    slightly left/right") and uploads the frames together. Each frame is checked
    for liveness and encoded, then the embeddings are averaged into one
    reference vector — more robust to angle and lighting than a single shot.

    Re-enrolling replaces the existing profile rather than creating a second
    one, since ``FaceProfile`` is one-to-one with the user.
    """

    frames = serializers.ListField(
        child=serializers.ImageField(),
        min_length=1,
        max_length=10,
        help_text='Captured frames from the guided enrolment sequence.',
    )
    store_reference_image = serializers.BooleanField(
        default=False,
        help_text=(
            'Keep the first frame as a reference image. Leave false unless the '
            'retention policy allows storing raw enrolment media.'
        ),
    )

    def validate_frames(self, frames):
        """
        Process every frame server-side and reject the batch if any frame fails
        the liveness gate.

        Failing the whole batch is intentional: a sequence where one frame looks
        like a spoof is not a sequence to build a reference face from.
        """
        liveness_threshold = getattr(settings, 'LIVENESS_THRESHOLD', 0.70)

        embeddings = []
        liveness_scores = []

        for index, frame in enumerate(frames, start=1):
            try:
                liveness = estimate_liveness(frame)

                # Liveness first — no point encoding a face that looks fake.
                if liveness < liveness_threshold:
                    raise serializers.ValidationError(
                        f'Frame {index} failed the liveness check '
                        f'(scored {liveness:.2f}, needs {liveness_threshold:.2f}). '
                        'Capture a live face rather than a photo of one.'
                    )

                embeddings.append(generate_embedding(frame))
                liveness_scores.append(liveness)

            except FaceProcessingError as error:
                # A processing failure is a problem with the upload, so report
                # it as a validation error rather than a server fault.
                raise serializers.ValidationError(f'Frame {index}: {error}') from error

        # Stash the results for create() so the work is not repeated.
        self._embeddings = embeddings
        self._liveness_scores = liveness_scores

        return frames

    def create(self, validated_data):
        """Store (or replace) the worker's reference face profile."""
        user = self.context['request'].user
        frames = validated_data['frames']

        try:
            reference_embedding = average_embeddings(self._embeddings)
        except FaceProcessingError as error:
            raise serializers.ValidationError(str(error)) from error

        # The weakest frame is the honest summary of the capture's quality.
        liveness_score = min(self._liveness_scores)

        from .services import STUB_MODEL_VERSION

        profile_fields = {
            'embedding': reference_embedding,
            'embedding_dim': len(reference_embedding),
            'model_version': STUB_MODEL_VERSION,
            'liveness_score': liveness_score,
            'frames_captured': len(frames),
            'is_active': True,
        }

        if validated_data.get('store_reference_image'):
            profile_fields['reference_image'] = frames[0]

        # One profile per worker: re-enrolment updates in place.
        profile, created = FaceProfile.objects.update_or_create(
            user=user,
            defaults=profile_fields,
        )

        # Surfaced to the view so it can log enrolment vs. re-enrolment.
        self.was_created = created

        return profile


class EnrollmentStatusSerializer(serializers.Serializer):
    """
    Whether the caller can be verified yet, and what is missing if not.

    Combines enrolment state with account approval so the app can route the
    worker to the right screen from a single request.
    """

    is_enrolled = serializers.BooleanField()
    is_approved = serializers.BooleanField()
    can_record_attendance = serializers.BooleanField()
    next_step = serializers.CharField()
    profile = FaceProfileSerializer(allow_null=True)
