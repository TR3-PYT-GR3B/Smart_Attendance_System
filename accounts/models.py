"""
Identity models for the Smart Attendance System.

Contains the custom ``User`` model, which replaces Django's default user and
serves as the single identity record for workers, department managers and
administrators.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    """Who a user is, and therefore what they are allowed to see."""

    WORKER = 'worker', _('Worker')
    DEPT_MANAGER = 'dept_manager', _('Department Manager')
    ADMIN = 'admin', _('Administrator')


class EmploymentStatus(models.TextChoices):
    """Current standing of the person within the organisation."""

    ACTIVE = 'active', _('Active')
    SUSPENDED = 'suspended', _('Suspended')
    TERMINATED = 'terminated', _('Terminated')


class UserManager(BaseUserManager):
    """Manager for a user model that logs in with an email address."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create a standard user — a worker awaiting approval by default."""
        extra_fields.setdefault('role', UserRole.WORKER)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_approved', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create an administrator with full access, pre-approved."""
        extra_fields.setdefault('role', UserRole.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_approved', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('A superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('A superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    A person who uses the system.

    Registration alone does not grant access: a new worker starts with
    ``is_approved=False`` and cannot record attendance until an administrator
    reviews the account (see the ``approvals`` app).
    """

    # ── Identity ──
    email = models.EmailField(_('email address'), unique=True)
    phone = models.CharField(_('phone number'), max_length=20, blank=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    employee_id = models.CharField(
        _('employee ID'),
        max_length=50,
        blank=True,
        help_text=_('Optional payroll or HR reference for this worker.'),
    )

    # ── Role & placement ──
    role = models.CharField(
        _('role'),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.WORKER,
    )
    department = models.ForeignKey(
        'organisations.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name=_('department'),
    )

    # ── Account state ──
    is_approved = models.BooleanField(
        _('approved'),
        default=False,
        help_text=_('An administrator has approved this account for attendance.'),
    )
    employment_status = models.CharField(
        _('employment status'),
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
    )
    biometric_consent_at = models.DateTimeField(
        _('biometric consent given at'),
        null=True,
        blank=True,
        help_text=_('When the user explicitly consented to face data being stored.'),
    )

    # ── Django plumbing ──
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['email']
        indexes = [
            models.Index(fields=['role', 'is_approved']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        full_name = self.get_full_name()
        return f'{full_name} <{self.email}>' if full_name else self.email

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name or self.email.split('@')[0]

    # ── Convenience role checks ──

    @property
    def is_worker(self):
        return self.role == UserRole.WORKER

    @property
    def is_department_manager(self):
        return self.role == UserRole.DEPT_MANAGER

    @property
    def is_administrator(self):
        return self.role == UserRole.ADMIN

    @property
    def can_record_attendance(self):
        """Approved, active, and still employed."""
        return (
            self.is_approved
            and self.is_active
            and self.employment_status == EmploymentStatus.ACTIVE
        )
