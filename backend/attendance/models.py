"""
Attendance records and the audit trail behind them.

``AttendanceRecord`` is the outcome — who was at which site and when.
``VerificationAttempt`` is the evidence — every GPS, liveness and face check
that was run, whether it passed or failed, and why. Attempts are written even
when a check-in is rejected, so disputes can be investigated after the fact.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class AttendanceStatus(models.TextChoices):
    """Outcome recorded against a worker for a given day."""

    PRESENT = 'present', _('Present')
    LATE = 'late', _('Late')
    ON_LEAVE = 'on_leave', _('On Leave')
    ABSENT = 'absent', _('Absent')
    FLAGGED = 'flagged', _('Flagged for Review')
    REJECTED = 'rejected', _('Rejected')


class AttemptType(models.TextChoices):
    """Which of the three server-side gates was being evaluated."""

    GPS = 'gps', _('GPS Geofence')
    LIVENESS = 'liveness', _('Liveness / Anti-spoofing')
    FACE = 'face', _('Face Match')


class AttendanceRecord(models.Model):
    """
    One work session: a check-in, and later a check-out.

    Coordinates are stored as separate float columns rather than a PostGIS
    point so the model works on SQLite.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name=_('user'),
    )
    work_location = models.ForeignKey(
        'organisations.WorkLocation',
        on_delete=models.PROTECT,
        related_name='attendance_records',
        verbose_name=_('work location'),
    )

    # ── Check-in ──
    check_in_time = models.DateTimeField(_('check-in time'))
    check_in_latitude = models.FloatField(
        _('check-in latitude'),
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
    )
    check_in_longitude = models.FloatField(
        _('check-in longitude'),
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
    )
    check_in_distance_meters = models.FloatField(
        _('check-in distance from site (metres)'),
        null=True,
        blank=True,
    )
    check_in_face_score = models.FloatField(
        _('check-in face similarity'),
        null=True,
        blank=True,
    )

    # ── Check-out ──
    check_out_time = models.DateTimeField(_('check-out time'), null=True, blank=True)
    check_out_latitude = models.FloatField(
        _('check-out latitude'),
        null=True,
        blank=True,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
    )
    check_out_longitude = models.FloatField(
        _('check-out longitude'),
        null=True,
        blank=True,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
    )
    check_out_distance_meters = models.FloatField(
        _('check-out distance from site (metres)'),
        null=True,
        blank=True,
    )
    check_out_face_score = models.FloatField(
        _('check-out face similarity'),
        null=True,
        blank=True,
    )

    # ── Outcome ──
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )
    minutes_late = models.PositiveIntegerField(_('minutes late'), default=0)

    # Set when an administrator overrides a failed capture (camera/GPS problems).
    is_manual_override = models.BooleanField(_('manual override'), default=False)
    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='overridden_attendance_records',
        verbose_name=_('overridden by'),
    )
    override_reason = models.TextField(_('override reason'), blank=True)

    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('attendance record')
        verbose_name_plural = _('attendance records')
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['user', '-check_in_time']),
            models.Index(fields=['work_location', '-check_in_time']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(check_out_time__isnull=True),
                name='unique_open_attendance_session_per_user',
            ),
        ]

    def __str__(self):
        return f'{self.user} @ {self.work_location.name} on {self.check_in_time:%Y-%m-%d}'

    @property
    def is_open(self):
        """Still checked in — no check-out recorded yet."""
        return self.check_out_time is None

    @property
    def duration_minutes(self):
        """Length of the completed session, or ``None`` if still open."""
        if self.check_out_time is None:
            return None
        return int((self.check_out_time - self.check_in_time).total_seconds() // 60)


class VerificationAttempt(models.Model):
    """
    A single server-side check, stored whether it passed or failed.

    Kept append-only: rows are never edited after they are written, so the log
    can be relied on when an attendance decision is challenged.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_attempts',
        verbose_name=_('user'),
    )
    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verification_attempts',
        verbose_name=_('attendance record'),
        help_text=_('Empty when the attempt failed before a record was created.'),
    )
    work_location = models.ForeignKey(
        'organisations.WorkLocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verification_attempts',
        verbose_name=_('work location'),
    )

    attempt_type = models.CharField(
        _('attempt type'),
        max_length=20,
        choices=AttemptType.choices,
    )
    result = models.BooleanField(_('passed'), default=False)
    score = models.FloatField(
        _('score'),
        null=True,
        blank=True,
        help_text=_('Similarity, liveness confidence, or distance in metres.'),
    )
    threshold_used = models.FloatField(
        _('threshold used'),
        null=True,
        blank=True,
        help_text=_('The value the score was compared against at the time.'),
    )
    reason_failed = models.TextField(_('reason failed'), blank=True)

    # Context captured for investigating suspicious attempts.
    latitude = models.FloatField(_('latitude'), null=True, blank=True)
    longitude = models.FloatField(_('longitude'), null=True, blank=True)
    device_info = models.CharField(_('device info'), max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)

    timestamp = models.DateTimeField(_('timestamp'), auto_now_add=True)

    class Meta:
        verbose_name = _('verification attempt')
        verbose_name_plural = _('verification attempts')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['attempt_type', 'result']),
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        outcome = 'passed' if self.result else 'failed'
        return f'{self.get_attempt_type_display()} {outcome} for {self.user}'
