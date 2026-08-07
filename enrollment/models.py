"""
Face enrolment.

Each worker has exactly one active face profile holding the ArcFace embedding
generated when they enrolled. Daily verification compares a freshly captured
face against this stored vector.

The embedding is kept as JSON (a list of floats) so the project can run on
SQLite; moving to PostgreSQL later means swapping this field for a pgvector
``vector(512)`` column without changing the surrounding logic.
"""

import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


def validate_embedding(value):
    """Ensure the stored value really is a fixed-length vector of numbers."""
    expected_dim = getattr(settings, 'FACE_EMBEDDING_DIM', 512)

    if not isinstance(value, list):
        raise ValidationError(_('Embedding must be a list of floats.'))
    if len(value) != expected_dim:
        raise ValidationError(
            _('Embedding must contain exactly %(dim)d values, got %(got)d.'),
            params={'dim': expected_dim, 'got': len(value)},
        )
    if not all(isinstance(component, (int, float)) for component in value):
        raise ValidationError(_('Embedding must contain only numbers.'))


class FaceProfile(models.Model):
    """
    The reference face for one worker.

    ``embedding`` is the average of several good frames captured during a
    guided enrolment sequence, which makes matching more robust than relying
    on a single photograph.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='face_profile',
        verbose_name=_('user'),
    )

    embedding = models.JSONField(
        _('face embedding'),
        validators=[validate_embedding],
        help_text=_('ArcFace vector averaged over the enrolment frames.'),
    )
    embedding_dim = models.PositiveIntegerField(
        _('embedding dimensions'),
        default=512,
    )
    model_version = models.CharField(
        _('model version'),
        max_length=100,
        blank=True,
        help_text=_('Which ArcFace model produced this embedding, for re-enrolment tracking.'),
    )

    liveness_score = models.FloatField(
        _('liveness score'),
        default=0.0,
        help_text=_('Anti-spoofing confidence recorded at enrolment (0-1).'),
    )
    frames_captured = models.PositiveIntegerField(
        _('frames captured'),
        default=0,
        help_text=_('How many good frames were averaged into the embedding.'),
    )

    # Reference image kept only if the retention policy allows it.
    reference_image = models.ImageField(
        _('reference image'),
        upload_to='enrollment/reference/%Y/%m/',
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(_('active'), default=True)
    enrolled_at = models.DateTimeField(_('enrolled at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('face profile')
        verbose_name_plural = _('face profiles')
        ordering = ['-enrolled_at']
        indexes = [models.Index(fields=['user', 'is_active'])]

    def __str__(self):
        return f'Face profile for {self.user}'

    def similarity_to(self, other_embedding):
        """
        Cosine similarity between this profile and a freshly captured face.

        Returns a value in the range -1.0 to 1.0, where 1.0 is identical.
        Compared against ``settings.FACE_MATCH_THRESHOLD`` to decide a match.
        """
        stored = self.embedding

        if not stored or not other_embedding:
            return 0.0
        if len(stored) != len(other_embedding):
            raise ValueError('Embeddings must have the same number of dimensions.')

        dot = sum(a * b for a, b in zip(stored, other_embedding))
        norm_stored = math.sqrt(sum(a * a for a in stored))
        norm_other = math.sqrt(sum(b * b for b in other_embedding))

        if norm_stored == 0 or norm_other == 0:
            return 0.0

        return dot / (norm_stored * norm_other)

    def matches(self, other_embedding, threshold=None):
        """Whether a captured face is close enough to count as the same person."""
        if threshold is None:
            threshold = getattr(settings, 'FACE_MATCH_THRESHOLD', 0.60)
        return self.similarity_to(other_embedding) >= threshold
