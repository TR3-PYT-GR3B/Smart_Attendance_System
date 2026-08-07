"""
Leave and absence management.

A worker submits a request against a leave type; an administrator approves or
rejects it. Approved leave draws down that worker's balance for the year and
marks the affected days as "on leave" rather than "absent" in attendance.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class LeaveStatus(models.TextChoices):
    """Where a request sits in the approval workflow."""

    PENDING = 'pending', _('Pending')
    APPROVED = 'approved', _('Approved')
    REJECTED = 'rejected', _('Rejected')
    CANCELLED = 'cancelled', _('Cancelled')


class LeaveType(models.Model):
    """A category of leave, e.g. Annual, Sick or Compassionate."""

    name = models.CharField(_('name'), max_length=100, unique=True)
    description = models.TextField(_('description'), blank=True)
    default_days_per_year = models.PositiveIntegerField(
        _('default days per year'),
        default=0,
        help_text=_('Allocation granted to a worker each year by default.'),
    )
    requires_document = models.BooleanField(
        _('requires supporting document'),
        default=False,
        help_text=_('Sick leave, for example, may require a medical note.'),
    )
    is_paid = models.BooleanField(_('paid leave'), default=True)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('leave type')
        verbose_name_plural = _('leave types')
        ordering = ['name']

    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    """A worker's application to be away between two dates."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_requests',
        verbose_name=_('user'),
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name='requests',
        verbose_name=_('leave type'),
    )

    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'))
    reason = models.TextField(_('reason'))

    supporting_document = models.ForeignKey(
        'documents.WorkerDocument',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_requests',
        verbose_name=_('supporting document'),
    )

    # ── Review ──
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=LeaveStatus.choices,
        default=LeaveStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_leave_requests',
        verbose_name=_('reviewed by'),
    )
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    review_notes = models.TextField(_('internal notes'), blank=True)

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('leave request')
        verbose_name_plural = _('leave requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='leave_end_date_after_start_date',
            )
        ]

    def __str__(self):
        return f'{self.user} — {self.leave_type.name} ({self.start_date} to {self.end_date})'

    def clean(self):
        """Reject date ranges and missing paperwork before anything is saved."""
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': _('End date cannot be before the start date.')})

        if self.leave_type_id and self.leave_type.requires_document and not self.supporting_document_id:
            raise ValidationError({
                'supporting_document': _('This leave type requires a supporting document.'),
            })

    # ── Derived values ──

    @property
    def total_days(self):
        """Number of calendar days covered, inclusive of both end points."""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_pending(self):
        return self.status == LeaveStatus.PENDING

    @property
    def can_be_cancelled(self):
        """Only a request still awaiting review may be withdrawn."""
        return self.status == LeaveStatus.PENDING

    def covers_date(self, date):
        """Whether a given day falls inside this request's range."""
        return self.start_date <= date <= self.end_date

    # ── Workflow actions ──

    def approve(self, reviewer, notes=''):
        """Approve the request and draw the days down from the worker's balance."""
        self.status = LeaveStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.rejection_reason = ''
        self.save()

        balance, _created = LeaveBalance.objects.get_or_create(
            user=self.user,
            leave_type=self.leave_type,
            year=self.start_date.year,
            defaults={'days_allocated': self.leave_type.default_days_per_year},
        )
        balance.days_used += self.total_days
        balance.save(update_fields=['days_used'])

    def reject(self, reviewer, reason, notes=''):
        """Reject the request, recording why."""
        self.status = LeaveStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.review_notes = notes
        self.save()

    def cancel(self):
        """Withdraw a request that has not yet been reviewed."""
        if not self.can_be_cancelled:
            raise ValidationError(_('Only a pending request can be cancelled.'))
        self.status = LeaveStatus.CANCELLED
        self.save(update_fields=['status', 'updated_at'])


class LeaveBalance(models.Model):
    """How much of one leave type a worker has left in a given year."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_balances',
        verbose_name=_('user'),
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name='balances',
        verbose_name=_('leave type'),
    )
    year = models.PositiveIntegerField(_('year'))

    days_allocated = models.PositiveIntegerField(_('days allocated'), default=0)
    days_used = models.PositiveIntegerField(_('days used'), default=0)

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('leave balance')
        verbose_name_plural = _('leave balances')
        ordering = ['-year', 'leave_type__name']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'leave_type', 'year'],
                name='unique_leave_balance_per_user_type_year',
            )
        ]
        indexes = [models.Index(fields=['user', 'year'])]

    def __str__(self):
        return f'{self.user} — {self.leave_type.name} {self.year}: {self.days_remaining} left'

    @property
    def days_remaining(self):
        """Unused allocation; never reported below zero."""
        return max(self.days_allocated - self.days_used, 0)

    @property
    def is_exhausted(self):
        return self.days_used >= self.days_allocated

    def has_capacity_for(self, days):
        """Whether a request of the given length still fits in the allocation."""
        return self.days_remaining >= days
