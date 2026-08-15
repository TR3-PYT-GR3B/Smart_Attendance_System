"""Admin registration for notifications and device tokens."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from django.utils.translation import gettext_lazy as _

from .models import DeviceToken, Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = [
        'title',
        'recipient',
        'notification_type',
        'channel',
        'delivery_status',
        'is_read',
        'created_at',
    ]
    list_filter = ['notification_type', 'channel', 'delivery_status', 'is_read', 'created_at']
    search_fields = ['title', 'body', 'recipient__email', 'recipient__first_name', 'recipient__last_name']
    list_select_related = ['recipient']
    autocomplete_fields = ['recipient']
    date_hierarchy = 'created_at'

    readonly_fields = ['created_at', 'sent_at', 'read_at', 'retry_count']

    fieldsets = [
        (None, {'fields': ['recipient', 'notification_type', 'channel']}),
        (_('Content'), {'fields': ['title', 'body', 'payload']}),
        (_('Target reference'), {'fields': ['target_app', 'target_model', 'target_id']}),
        (_('Read state'), {'fields': ['is_read', 'read_at']}),
        (_('Delivery'), {
            'fields': ['delivery_status', 'sent_at', 'delivery_error', 'retry_count'],
        }),
        (_('Timestamps'), {'fields': ['created_at']}),
    ]


@admin.register(DeviceToken)
class DeviceTokenAdmin(ModelAdmin):
    list_display = [
        'user',
        'platform',
        'device_name',
        'is_active',
        'last_used_at',
        'created_at',
    ]
    list_filter = ['platform', 'is_active', 'created_at']
    search_fields = ['user__email', 'token', 'device_name']
    list_select_related = ['user']
    autocomplete_fields = ['user']

    readonly_fields = ['created_at']
