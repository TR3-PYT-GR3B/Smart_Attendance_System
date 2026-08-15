"""
Immutable audit trail.

Every decision that affects a worker's record — an approval, a rejection, a
manual attendance override, a document verification — is written here as an
append-only entry. When an attendance or leave decision is challenged, this is
the log that settles it.

Rows are never updated or deleted through the ORM: ``save()`` refuses to write
over an existing entry and ``delete()`` raises. Use the ``log()`` helper to
record an action.

Note that ``attendance.VerificationAttempt`` remains the detailed record of
individual GPS/face/liveness checks; this model captures the human and system
actions taken around them.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditAction(models.TextChoices):
    """The kinds of action worth keeping a permanent record of."""

    # Accounts
    ACCOUNT_REGISTERED = 'account_registered', _('Account Registered')
    ACCOUNT_APPROVED = 'account_approved', _('Account Approved')
    ACCOUNT_REJECTED = 'account_rejected', _('Account Rejected')
    ACCOUNT_SUSPENDED = 'account_suspended', _('Account Suspended')

    # Enrolment / biometrics
    FACE_ENROLLED = 'face_enrolled', _('Face Enrolled')
    FACE_RE_ENROLLED = 'face_re_enrolled', _('Face Re-enrolled')
    FACE_DATA_DELETED = 'face_data_deleted', _('Face Data Deleted')
    CONSENT_GIVEN = 'consent_given', _('Biometric Consent Given')
    CONSENT_WITHDRAWN = 'consent_withdrawn', _('Biometric Consent Withdrawn')

    # Attendance
    CHECK_IN = 'check_in', _('Check-in Recorded')
    CHECK_OUT = 'check_out', _('Check-out Recorded')
    CHECK_IN_REJECTED = 'check_in_rejected', _('Check-in Rejected')
    ATTENDANCE_OVERRIDDEN = 'attendance_overridden', _('Attendance Manually Overridden')

    # Leave
    LEAVE_REQUESTED = 'leave_requested', _('Leave Requested')
    LEAVE_APPROVED = 'leave_approved', _('Leave Approved')
    LEAVE_REJECTED = 'leave_rejected', _('Leave Rejected')
    LEAVE_CANCELLED = 'leave_cancelled', _('Leave Cancelled')

    # Documents
    DOCUMENT_UPLOADED = 'document_uploaded', _('Document Uploaded')
    DOCUMENT_VERIFIED = 'document_verified', _('Document Verified')
    DOCUMENT_REJECTED = 'document_rejected', _('Document Rejected')

    # Configuration
    LOCATION_CREATED = 'location_created', _('Work Location Created')
    LOCATION_UPDATED = 'location_updated', _('Work Location Updated')
    THRESHOLD_CHANGED = 'threshold_changed', _('Verification Threshold Changed')

    OTHER = 'other', _('Other')


class AuditLog(models.Model):
    """
    One recorded action, kept permanently.

    ``actor`` is whoever performed the action and ``subject`` is the worker it
    was performed on; for a self-service action such as a check-in the two are
    the same person. Both use ``SET_NULL`` so that deleting a user account
    never destroys the history of what was done.
    """

    action = models.CharField(
        _('action'),
        max_length=40,
        choices=AuditAction.choices,
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_actions_performed',
        verbose_name=_('actor'),
        help_text=_('Who performed the action; empty for automated system actions.'),
    )
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_actions_received',
        verbose_name=_('subject'),
        help_text=_('The worker the action concerns.'),
    )

    # Loose reference to whatever object the action touched. Kept as an app
    # label plus id rather than a real FK so that removing the target row
    # never cascades into the audit history.
    target_app = models.CharField(_('target app'), max_length=50, blank=True)
    target_model = models.CharField(_('target model'), max_length=50, blank=True)
    target_id = models.CharField(_('target id'), max_length=50, blank=True)

    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Human-readable summary shown in the admin audit view.'),
    )
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True,
        help_text=_('Scores, thresholds, before/after values — whatever explains the decision.'),
    )

    # Request context.
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.CharField(_('user agent'), max_length=500, blank=True)

    timestamp = models.DateTimeField(_('timestamp'), auto_now_add=True)

    class Meta:
        verbose_name = _('audit log entry')
        verbose_name_plural = _('audit log')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['subject', '-timestamp']),
            models.Index(fields=['actor', '-timestamp']),
            models.Index(fields=['target_app', 'target_model', 'target_id']),
        ]

    def __str__(self):
        return f'{self.get_action_display()} at {self.timestamp:%Y-%m-%d %H:%M}'

    # ── Append-only enforcement ──

    def save(self, *args, **kwargs):
        """Allow the first write only; audit entries are never amended."""
        if self.pk is not None:
            raise ValueError('Audit log entries are immutable and cannot be modified.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit log entries are immutable and cannot be deleted.')

    @classmethod
    def log(cls, action, actor=None, subject=None, target=None,
            description='', metadata=None, request=None):
        """
        Record an action.

        ``target`` may be any model instance; its app label, model name and id
        are copied in so the entry survives the object being deleted. Passing
        ``request`` captures the caller's IP address and user agent.
        """
        entry = cls(
            action=action,
            actor=actor,
            subject=subject,
            description=description,
            metadata=metadata or {},
        )

        if target is not None:
            entry.target_app = target._meta.app_label
            entry.target_model = target._meta.model_name
            entry.target_id = str(target.pk)

        if request is not None:
            entry.ip_address = cls._client_ip(request)
            entry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        entry.save()
        return entry

    @staticmethod
    def _client_ip(request):
        """Prefer the forwarded-for address so a proxy does not mask the caller."""
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
