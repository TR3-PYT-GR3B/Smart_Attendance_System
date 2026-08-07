"""
Serializers for registration, login and profile.

Registering is deliberately not the same as gaining access: a new worker is
created unapproved, and an ``AccountApprovalRequest`` is raised for an
administrator to review. Until that is approved the account can authenticate
but cannot record attendance.
"""

from django.contrib.auth import password_validation
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from approvals.models import AccountApprovalRequest
from audit.models import AuditAction, AuditLog
from organisations.models import Department

from .models import User


class DepartmentBriefSerializer(serializers.ModelSerializer):
    """Minimal department representation for nesting inside user payloads."""

    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'name', 'organization_name']


class UserSerializer(serializers.ModelSerializer):
    """
    Read-only view of a user, used by ``/api/auth/me/`` and nested elsewhere.

    ``can_record_attendance`` is included so the mobile app knows whether to
    show the check-in button without having to reason about approval, active
    state and employment status itself.
    """

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    department = DepartmentBriefSerializer(read_only=True)
    can_record_attendance = serializers.BooleanField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'first_name',
            'last_name',
            'phone',
            'employee_id',
            'role',
            'department',
            'is_approved',
            'employment_status',
            'can_record_attendance',
            'is_enrolled',
            'biometric_consent_at',
            'date_joined',
        ]
        read_only_fields = [
            'id',
            'email',
            'role',
            'is_approved',
            'employment_status',
            'biometric_consent_at',
            'date_joined',
        ]

    def get_is_enrolled(self, obj):
        """Whether the worker has an active face profile to verify against."""
        face_profile = getattr(obj, 'face_profile', None)
        return bool(face_profile and face_profile.is_active)


class RegisterSerializer(serializers.ModelSerializer):
    """
    Worker self-registration.

    Creates the account unapproved and raises an approval request in the same
    transaction, so a worker can never exist without a corresponding entry in
    the admin queue.

    ``role`` is intentionally absent from the input fields — allowing a caller
    to choose their own role would let anyone register as an administrator.
    """

    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        required=False,
        allow_null=True,
    )
    biometric_consent = serializers.BooleanField(
        write_only=True,
        help_text='Must be true — face data cannot be stored without explicit consent.',
    )

    class Meta:
        model = User
        fields = [
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'phone',
            'employee_id',
            'department_id',
            'biometric_consent',
        ]

    def validate_password(self, value):
        """Run Django's configured password validators."""
        password_validation.validate_password(value)
        return value

    def validate_biometric_consent(self, value):
        """
        Consent is a hard requirement, not a preference.

        Biometric data counts as sensitive personal data in most jurisdictions,
        so the plan requires explicit consent to be captured at enrolment.
        """
        if not value:
            raise serializers.ValidationError(
                'Biometric consent is required to use face-based attendance.'
            )
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create the worker, raise the approval request, and log both."""
        validated_data.pop('password_confirm')
        validated_data.pop('biometric_consent')
        password = validated_data.pop('password')

        # create_user() defaults role=worker and is_approved=False.
        user = User.objects.create_user(
            password=password,
            biometric_consent_at=timezone.now(),
            **validated_data,
        )

        # Every new worker lands in the admin approval queue.
        approval_request = AccountApprovalRequest.objects.create(user=user)

        request = self.context.get('request')
        AuditLog.log(
            AuditAction.ACCOUNT_REGISTERED,
            actor=user,
            subject=user,
            target=approval_request,
            description=f'{user.email} registered and is awaiting approval.',
            metadata={'department_id': user.department_id},
            request=request,
        )
        AuditLog.log(
            AuditAction.CONSENT_GIVEN,
            actor=user,
            subject=user,
            target=user,
            description='Biometric consent given at registration.',
            request=request,
        )

        return user


class LoginSerializer(TokenObtainPairSerializer):
    """
    JWT login that also returns the user profile.

    Saves the client an extra round-trip to ``/me/`` right after signing in, and
    lets it decide immediately whether to route the worker to enrolment, to a
    "pending approval" screen, or straight to check-in.
    """

    # The custom user model authenticates by email.
    username_field = User.USERNAME_FIELD

    @classmethod
    def get_token(cls, user):
        """Embed a little context in the token to save lookups downstream."""
        token = super().get_token(user)
        token['role'] = user.role
        token['is_approved'] = user.is_approved
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """Password change for an already-authenticated user."""

    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context['request'].user)
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
