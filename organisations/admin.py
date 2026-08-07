"""Admin registration for organisational structure."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Department, Organization, WorkLocation


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'manager', 'created_at']
    list_filter = ['organization']
    search_fields = ['name', 'manager__email']
    list_select_related = ['organization', 'manager']
    autocomplete_fields = ['manager']


@admin.register(WorkLocation)
class WorkLocationAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'department',
        'latitude',
        'longitude',
        'radius_meters',
        'shift_start_time',
        'is_active',
    ]
    list_filter = ['is_active', 'department']
    search_fields = ['name', 'address']
    list_select_related = ['department']

    fieldsets = [
        (None, {'fields': ['name', 'department', 'address', 'is_active']}),
        (_('Geofence'), {
            'fields': ['latitude', 'longitude', 'radius_meters'],
            'description': _(
                'Centre point of the site and how far from it a check-in is accepted.'
            ),
        }),
        (_('Shift window'), {
            'fields': ['shift_start_time', 'shift_end_time', 'late_grace_minutes'],
            'description': _('Used to decide whether a check-in counts as late.'),
        }),
    ]
