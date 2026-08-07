"""
Authentication endpoints.

Registration is open to unauthenticated callers by design — workers sign
themselves up from the mobile app. That is safe because a new account is
created unapproved and cannot record attendance until an administrator clears
it, so an unwanted registration is inert rather than dangerous. Everything else
here requires a valid JWT.
"""

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    ``POST /api/auth/register/``

    Creates an unapproved worker and raises an approval request. The response
    reports the pending state explicitly so the app can show a "waiting for
    approval" screen rather than dropping the worker at a dead end.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'user': UserSerializer(user).data,
                'detail': (
                    'Registration received. An administrator must approve your '
                    'account before you can record attendance.'
                ),
                'next_step': 'await_approval',
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """
    ``POST /api/auth/login/``

    Returns an access/refresh token pair plus the user profile. Note that an
    unapproved worker can still sign in — they need to be able to check whether
    they have been approved yet. The approval gate sits on the attendance
    endpoints, not on login.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    """
    ``GET|PATCH /api/auth/me/``

    The caller's own profile. Sensitive fields (role, approval state,
    employment status) are read-only in the serializer, so a worker can correct
    their phone number but cannot promote themselves.
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_queryset(self):
        """Present only for DRF's introspection; ``get_object`` is what runs."""
        from .models import User

        return User.objects.filter(pk=self.request.user.pk)


class ChangePasswordView(APIView):
    """``POST /api/auth/change-password/``"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Existing tokens stay valid — the client should re-authenticate to get
        # a fresh pair if it wants old sessions invalidated.
        return Response({'detail': 'Password updated.'}, status=status.HTTP_200_OK)
