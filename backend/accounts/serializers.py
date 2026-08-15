"""Serializers for administrator-provisioned worker authentication."""

from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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
    next_step = serializers.CharField(read_only=True)

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
            'next_step',
            'biometric_consent_at',
            'biometric_consent_version',
            'must_change_password',
            'date_joined',
        ]
        read_only_fields = [
            'id',
            'email',
            'role',
            'employee_id',
            'is_approved',
            'employment_status',
            'biometric_consent_at',
            'biometric_consent_version',
            'must_change_password',
            'date_joined',
        ]

    def get_is_enrolled(self, obj):
        """Whether the worker has an active face profile to verify against."""
        face_profile = getattr(obj, 'face_profile', None)
        return bool(face_profile and face_profile.is_active)


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
        data['next_step'] = self.user.next_step
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """Password change for an already-authenticated user."""

    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context['request'].user)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {'new_password_confirm': 'Passwords do not match.'}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])
        return user
