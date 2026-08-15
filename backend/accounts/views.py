"""Authentication endpoints for administrator-provisioned accounts."""

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    """
    ``POST /api/auth/login/``

    Returns an access/refresh token pair, profile, and the one first-login step
    the mobile client must perform next.
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

        return Response(
            {
                'detail': 'Password updated.',
                'next_step': request.user.next_step,
                'user': UserSerializer(request.user).data,
            },
            status=status.HTTP_200_OK,
        )
