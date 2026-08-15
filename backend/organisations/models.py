"""
Organisational structure: companies, their departments, and the physical
locations where attendance may be recorded.

Geofences are stored as a latitude/longitude pair plus a radius in metres.
Distance checks are performed in Python with geopy, so no PostGIS extension
is required while the project runs on SQLite.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from geopy.distance import geodesic


class Organization(models.Model):
    """A company or tenant. Kept as the top-level node so that multi-tenant
    support can be introduced later without restructuring the schema."""

    name = models.CharField(_('name'), max_length=255, unique=True)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')
        ordering = ['name']

    def __str__(self):
        return self.name


class Department(models.Model):
    """A unit within an organisation. Department managers see only the data
    belonging to the department they manage."""

    name = models.CharField(_('name'), max_length=255)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='departments',
        verbose_name=_('organization'),
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments',
        verbose_name=_('manager'),
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('department')
        verbose_name_plural = _('departments')
        ordering = ['organization__name', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'name'],
                name='unique_department_name_per_organization',
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.organization.name})'


class WorkLocation(models.Model):
    """
    A geofenced site where workers may check in.

    ``latitude``/``longitude`` mark the centre of the fence and
    ``radius_meters`` its size; a check-in is inside the fence when the
    distance from the centre is no greater than the radius.
    """

    name = models.CharField(_('name'), max_length=255)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='work_locations',
        verbose_name=_('department'),
    )
    address = models.CharField(_('address'), max_length=500, blank=True)

    latitude = models.FloatField(
        _('latitude'),
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
    )
    longitude = models.FloatField(
        _('longitude'),
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
    )
    radius_meters = models.PositiveIntegerField(
        _('radius (metres)'),
        default=100,
        validators=[MinValueValidator(10), MaxValueValidator(10_000)],
        help_text=_('How far from the centre point a check-in is still accepted.'),
    )

    # Shift window, used to decide whether a check-in counts as late.
    shift_start_time = models.TimeField(_('shift start time'), null=True, blank=True)
    shift_end_time = models.TimeField(_('shift end time'), null=True, blank=True)
    late_grace_minutes = models.PositiveIntegerField(
        _('late grace period (minutes)'),
        default=15,
        help_text=_('Minutes after shift start before a check-in is marked late.'),
    )

    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('work location')
        verbose_name_plural = _('work locations')
        ordering = ['department__name', 'name']
        indexes = [models.Index(fields=['department', 'is_active'])]

    def __str__(self):
        return f'{self.name} ({self.department.name})'

    # ── Geofence helpers ──

    @property
    def coordinates(self):
        """Centre of the geofence as a ``(latitude, longitude)`` tuple."""
        return (self.latitude, self.longitude)

    def distance_to(self, latitude, longitude):
        """Distance in metres from this location's centre to the given point."""
        return geodesic(self.coordinates, (latitude, longitude)).meters

    def contains(self, latitude, longitude):
        """Whether the given point falls inside the geofence."""
        return self.distance_to(latitude, longitude) <= self.radius_meters
