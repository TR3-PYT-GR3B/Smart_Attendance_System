"""
Pre-aggregated analytics.

Dashboards read from these summary tables rather than scanning
``attendance_records`` directly, which keeps load times flat as history grows.
A nightly Celery job rolls raw attendance up into daily rows and then folds the
daily rows into monthly ones.

Every summary carries a ``generated_at`` timestamp so a stale roll-up is
obvious, and each has a uniqueness constraint on its natural key so a re-run of
the job updates the existing row instead of duplicating it.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SummaryMixin(models.Model):
    """Shared counters and the rates derived from them."""

    days_present = models.PositiveIntegerField(_('days present'), default=0)
    days_late = models.PositiveIntegerField(_('days late'), default=0)
    days_absent = models.PositiveIntegerField(_('days absent'), default=0)
    days_on_leave = models.PositiveIntegerField(_('days on leave'), default=0)
    days_flagged = models.PositiveIntegerField(_('days flagged'), default=0)

    generated_at = models.DateTimeField(_('generated at'), auto_now=True)

    class Meta:
        abstract = True

    @property
    def days_expected(self):
        """Working days the worker was due in, excluding approved leave."""
        return self.days_present + self.days_late + self.days_absent

    @property
    def attendance_rate(self):
        """Share of expected days actually worked, as a percentage."""
        expected = self.days_expected
        if expected == 0:
            return 0.0
        return round((self.days_present + self.days_late) / expected * 100, 2)

    @property
    def punctuality_rate(self):
        """Share of days worked that were on time, as a percentage."""
        worked = self.days_present + self.days_late
        if worked == 0:
            return 0.0
        return round(self.days_present / worked * 100, 2)


class WorkerDailySummary(SummaryMixin):
    """
    One row per worker per day.

    Deliberately granular: the worker's attendance calendar and any date-range
    dashboard query both read from here, so a single roll-up serves both.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_summaries',
        verbose_name=_('user'),
    )
    department = models.ForeignKey(
        'organisations.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='worker_daily_summaries',
        verbose_name=_('department'),
        help_text=_('Copied in at roll-up time so later transfers do not rewrite history.'),
    )
    date = models.DateField(_('date'))

    minutes_late = models.PositiveIntegerField(_('minutes late'), default=0)
    minutes_worked = models.PositiveIntegerField(_('minutes worked'), default=0)

    class Meta(SummaryMixin.Meta):
        verbose_name = _('worker daily summary')
        verbose_name_plural = _('worker daily summaries')
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'date'],
                name='unique_worker_daily_summary',
            )
        ]
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['department', '-date']),
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f'{self.user} — {self.date}'


class WorkerMonthlySummary(SummaryMixin):
    """One row per worker per month, for trend charts and monthly reports."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='monthly_summaries',
        verbose_name=_('user'),
    )
    department = models.ForeignKey(
        'organisations.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='worker_monthly_summaries',
        verbose_name=_('department'),
    )
    year = models.PositiveIntegerField(_('year'))
    month = models.PositiveSmallIntegerField(_('month'), help_text=_('1-12'))

    total_minutes_late = models.PositiveIntegerField(_('total minutes late'), default=0)
    total_minutes_worked = models.PositiveIntegerField(_('total minutes worked'), default=0)
    leave_days_used = models.PositiveIntegerField(_('leave days used'), default=0)

    class Meta(SummaryMixin.Meta):
        verbose_name = _('worker monthly summary')
        verbose_name_plural = _('worker monthly summaries')
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'year', 'month'],
                name='unique_worker_monthly_summary',
            )
        ]
        indexes = [
            models.Index(fields=['user', '-year', '-month']),
            models.Index(fields=['department', '-year', '-month']),
        ]

    def __str__(self):
        return f'{self.user} — {self.year}-{self.month:02d}'

    @property
    def average_minutes_late(self):
        """Mean lateness across the days that were actually late."""
        if self.days_late == 0:
            return 0.0
        return round(self.total_minutes_late / self.days_late, 1)


class DepartmentDailySummary(SummaryMixin):
    """
    One row per department per day — powers the org-wide and per-department
    dashboards without touching individual worker rows.
    """

    department = models.ForeignKey(
        'organisations.Department',
        on_delete=models.CASCADE,
        related_name='daily_summaries',
        verbose_name=_('department'),
    )
    date = models.DateField(_('date'))

    headcount = models.PositiveIntegerField(
        _('headcount'),
        default=0,
        help_text=_('Approved, active workers in the department on this date.'),
    )
    flagged_attempts = models.PositiveIntegerField(
        _('flagged verification attempts'),
        default=0,
        help_text=_('Failed GPS/face/liveness checks awaiting review.'),
    )

    class Meta(SummaryMixin.Meta):
        verbose_name = _('department daily summary')
        verbose_name_plural = _('department daily summaries')
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['department', 'date'],
                name='unique_department_daily_summary',
            )
        ]
        indexes = [
            models.Index(fields=['department', '-date']),
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f'{self.department.name} — {self.date}'
