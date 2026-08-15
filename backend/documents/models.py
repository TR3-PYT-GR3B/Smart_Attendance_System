"""
Worker document uploads.

Workers upload identification, certifications, contracts and medical notes;
administrators review each one and mark it verified or rejected. Documents
that expire (certifications, for example) carry an expiry date so renewals can
be chased before they lapse.

Files are written to ``MEDIA_ROOT`` and referenced by path. When this moves to
production the same field can point at encrypted S3-compatible storage without
the model changing.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class DocumentType(models.TextChoices):
    """What kind of document was uploaded."""

    ID_CARD = 'id_card', _('Identification Card')
    CERTIFICATION = 'certification', _('Certification')
    CONTRACT = 'contract', _('Contract')
    MEDICAL_NOTE = 'medical_note', _('Medical Note')
    OTHER = 'other', _('Other')


class DocumentStatus(models.TextChoices):
    """Where the document sits in the review queue."""

    PENDING_REVIEW = 'pending_review', _('Pending Review')
    VERIFIED = 'verified', _('Verified')
    REJECTED = 'rejected', _('Rejected')


class DocumentRequestStatus(models.TextChoices):
    """Lifecycle of a department-wide request issued by the office."""

    ACTIVE = 'active', _('Active')
    CLOSED = 'closed', _('Closed')
    CANCELLED = 'cancelled', _('Cancelled')


class DocumentRequest(models.Model):
    """A document the office has asked every worker in a department to provide."""

    department = models.ForeignKey(
        'organisations.Department',
        on_delete=models.CASCADE,
        related_name='document_requests',
        null=True,
        verbose_name=_('department'),
        help_text=_(
            'Every employee currently assigned to this department will see the request.'
        ),
    )
    document_type = models.CharField(
        _('document type'),
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    title = models.CharField(_('title'), max_length=255)
    instructions = models.TextField(_('instructions'), blank=True)
    due_date = models.DateField(_('due date'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=DocumentRequestStatus.choices,
        default=DocumentRequestStatus.ACTIVE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_document_requests',
        verbose_name=_('requested by'),
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('document request')
        verbose_name_plural = _('document requests')
        ordering = ['status', 'due_date', '-created_at']
        indexes = [
            models.Index(
                fields=['department', 'status'],
                name='documents_req_dept_status_idx',
            ),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f'{self.title} — {self.department}'

    @property
    def is_overdue(self):
        return (
            self.due_date is not None
            and self.due_date < timezone.localdate()
            and self.status == DocumentRequestStatus.ACTIVE
        )


def document_upload_path(instance, filename):
    """Keep each worker's uploads in their own folder, split by document type."""
    return f'documents/{instance.user_id}/{instance.document_type}/{filename}'


class WorkerDocument(models.Model):
    """A file a worker has submitted for administrative review."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('user'),
    )
    request = models.ForeignKey(
        DocumentRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submissions',
        verbose_name=_('document request'),
    )

    document_type = models.CharField(
        _('document type'),
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)

    file = models.FileField(
        _('file'),
        upload_to=document_upload_path,
        help_text=_('Stored under MEDIA_ROOT; move to encrypted object storage in production.'),
    )
    original_filename = models.CharField(_('original filename'), max_length=255, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(_('file size (bytes)'), null=True, blank=True)

    # ── Review ──
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.PENDING_REVIEW,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
        verbose_name=_('reviewed by'),
    )
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)

    # ── Validity ──
    issue_date = models.DateField(_('issue date'), null=True, blank=True)
    expiry_date = models.DateField(
        _('expiry date'),
        null=True,
        blank=True,
        help_text=_('Set for renewable documents so reminders can be sent.'),
    )

    uploaded_at = models.DateTimeField(_('uploaded at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('worker document')
        verbose_name_plural = _('worker documents')
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['user', '-uploaded_at']),
            models.Index(fields=['status', 'document_type']),
            models.Index(fields=['expiry_date']),
        ]

    def __str__(self):
        return f'{self.title} ({self.get_document_type_display()}) — {self.user}'

    # ── Status helpers ──

    @property
    def is_expired(self):
        return self.expiry_date is not None and self.expiry_date < timezone.localdate()

    @property
    def days_until_expiry(self):
        """Days remaining before expiry; negative once lapsed, ``None`` if not applicable."""
        if self.expiry_date is None:
            return None
        return (self.expiry_date - timezone.localdate()).days

    def expires_within(self, days):
        """Whether the document lapses inside the given window — drives renewal chasing."""
        remaining = self.days_until_expiry
        return remaining is not None and 0 <= remaining <= days

    # ── Review actions ──

    def verify(self, reviewer):
        """Accept the document."""
        self.status = DocumentStatus.VERIFIED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = ''
        self.save()

    def reject(self, reviewer, reason):
        """Reject the document, recording why so the worker can re-upload."""
        self.status = DocumentStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()
