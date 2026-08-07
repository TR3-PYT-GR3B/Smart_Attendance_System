"""
Account approval workflow.

Registering does not grant access. Each new worker raises an approval request
that an administrator must review before the account can record attendance.
A rejected worker may correct their details and re-submit, so the model keeps
a resubmission counter rather than deleting the earlier decision.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ApprovalStatus(models.TextChoices):
    """Where a request sits in the review queue."""

    PENDING = 'pending', _('Pending Review')
    APPROVED = 'approved', _('Approved')
    REJECTED = 'rejected', _('Rejected')


class AccountApprovalRequest(models.Model):
    """An administrator's decision on whether a new account may be activated."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='approval_requests',
        verbose_name=_('user'),
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )

    # ── Review ──
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_approval_requests',
        verbose_name=_('reviewed by'),
    )
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Shown to the worker so they know what to correct.'),
    )
    review_notes = models.TextField(
        _('internal notes'),
        blank=True,
        help_text=_('Visible to administrators only.'),
    )

    submission_count = models.PositiveIntegerField(
        _('submission count'),
        default=1,
        help_text=_('Increases each time a rejected worker re-submits.'),
    )

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('account approval request')
        verbose_name_plural = _('account approval requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f'{self.user} — {self.get_status_display()}'

    @property
    def is_pending(self):
        return self.status == ApprovalStatus.PENDING

    def approve(self, reviewer, notes=''):
        """Approve the request and let the worker start recording attendance."""
        self.status = ApprovalStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.rejection_reason = ''
        self.save()

        self.user.is_approved = True
        self.user.save(update_fields=['is_approved'])

    def reject(self, reviewer, reason, notes=''):
        """Reject the request, recording why so the worker can re-submit."""
        self.status = ApprovalStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.review_notes = notes
        self.save()

        self.user.is_approved = False
        self.user.save(update_fields=['is_approved'])
