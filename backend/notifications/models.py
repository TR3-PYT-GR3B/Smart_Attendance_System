"""
Notifications.

Covers the messages the system sends out: an account approval, a leave
decision, a document verification, a certification about to expire, a late
sign-in warning. Each notification is persisted so the mobile app can show an
inbox, and delivery is tracked separately from the message itself — a push that
fails should not lose the record that the worker needed telling.

Sending is handled by a Celery task, which sets ``sent_at`` on success or
records the problem in ``delivery_error`` and increments ``retry_count``.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class NotificationType(models.TextChoices):
    """What the notification is about."""

    ACCOUNT_APPROVED = 'account_approved', _('Account Approved')
    ACCOUNT_REJECTED = 'account_rejected', _('Account Rejected')

    LEAVE_APPROVED = 'leave_approved', _('Leave Approved')
    LEAVE_REJECTED = 'leave_rejected', _('Leave Rejected')
    LEAVE_REQUEST_PENDING = 'leave_request_pending', _('Leave Request Awaiting Review')

    DOCUMENT_VERIFIED = 'document_verified', _('Document Verified')
    DOCUMENT_REJECTED = 'document_rejected', _('Document Rejected')
    DOCUMENT_EXPIRING = 'document_expiring', _('Document Expiring Soon')

    LATE_SIGN_IN = 'late_sign_in', _('Late Sign-in')
    MISSING_CHECK_OUT = 'missing_check_out', _('Missing Check-out')
    VERIFICATION_FLAGGED = 'verification_flagged', _('Verification Attempt Flagged')

    ENROLLMENT_REQUIRED = 'enrollment_required', _('Face Enrolment Required')
    GENERAL = 'general', _('General')


class NotificationChannel(models.TextChoices):
    """How the notification should reach the recipient."""

    PUSH = 'push', _('Push Notification')
    EMAIL = 'email', _('Email')
    IN_APP = 'in_app', _('In-app Only')


class DeliveryStatus(models.TextChoices):
    """Where delivery got to."""

    PENDING = 'pending', _('Pending')
    SENT = 'sent', _('Sent')
    FAILED = 'failed', _('Failed')


class Notification(models.Model):
    """A single message addressed to one user."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('recipient'),
    )

    notification_type = models.CharField(
        _('type'),
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )
    channel = models.CharField(
        _('channel'),
        max_length=10,
        choices=NotificationChannel.choices,
        default=NotificationChannel.PUSH,
    )

    title = models.CharField(_('title'), max_length=255)
    body = models.TextField(_('body'))
    payload = models.JSONField(
        _('payload'),
        default=dict,
        blank=True,
        help_text=_('Extra data for the client, e.g. the leave request id to deep-link to.'),
    )

    # Loose reference to whatever prompted the notification. Not a real FK, so
    # deleting the source object leaves the message history intact.
    target_app = models.CharField(_('target app'), max_length=50, blank=True)
    target_model = models.CharField(_('target model'), max_length=50, blank=True)
    target_id = models.CharField(_('target id'), max_length=50, blank=True)

    # ── Read state ──
    is_read = models.BooleanField(_('read'), default=False)
    read_at = models.DateTimeField(_('read at'), null=True, blank=True)

    # ── Delivery ──
    delivery_status = models.CharField(
        _('delivery status'),
        max_length=10,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    sent_at = models.DateTimeField(_('sent at'), null=True, blank=True)
    delivery_error = models.TextField(_('delivery error'), blank=True)
    retry_count = models.PositiveSmallIntegerField(_('retry count'), default=0)

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['delivery_status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.title} → {self.recipient}'

    # ── State transitions ──

    def mark_read(self):
        """Flag as read; repeat calls keep the original timestamp."""
        if self.is_read:
            return
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])

    def mark_sent(self):
        self.delivery_status = DeliveryStatus.SENT
        self.sent_at = timezone.now()
        self.delivery_error = ''
        self.save(update_fields=['delivery_status', 'sent_at', 'delivery_error'])

    def mark_failed(self, error):
        """Record a delivery failure so the retry task can pick it up."""
        self.delivery_status = DeliveryStatus.FAILED
        self.delivery_error = str(error)
        self.retry_count += 1
        self.save(update_fields=['delivery_status', 'delivery_error', 'retry_count'])

    @classmethod
    def create_for(cls, recipient, notification_type, title, body,
                   channel=NotificationChannel.PUSH, payload=None, target=None):
        """Queue a notification. Delivery is left to the Celery send task."""
        notification = cls(
            recipient=recipient,
            notification_type=notification_type,
            channel=channel,
            title=title,
            body=body,
            payload=payload or {},
        )

        if target is not None:
            notification.target_app = target._meta.app_label
            notification.target_model = target._meta.model_name
            notification.target_id = str(target.pk)

        notification.save()
        return notification


class DeviceToken(models.Model):
    """
    A push token for one of a user's devices.

    Workers may sign in on more than one handset, so tokens are held per device
    and deactivated rather than deleted when they stop working — that keeps the
    delivery history readable.
    """

    class Platform(models.TextChoices):
        ANDROID = 'android', _('Android')
        IOS = 'ios', _('iOS')
        WEB = 'web', _('Web')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens',
        verbose_name=_('user'),
    )
    token = models.CharField(_('push token'), max_length=500, unique=True)
    platform = models.CharField(
        _('platform'),
        max_length=10,
        choices=Platform.choices,
        default=Platform.ANDROID,
    )
    device_name = models.CharField(_('device name'), max_length=255, blank=True)

    is_active = models.BooleanField(_('active'), default=True)
    last_used_at = models.DateTimeField(_('last used at'), null=True, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('device token')
        verbose_name_plural = _('device tokens')
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_active'])]

    def __str__(self):
        return f'{self.get_platform_display()} token for {self.user}'

    def deactivate(self):
        """Stop using a token the push service has rejected."""
        self.is_active = False
        self.save(update_fields=['is_active'])
