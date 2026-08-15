"""Auth routes, mounted at ``/api/auth/``."""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import ChangePasswordView, LoginView, MeView

app_name = 'accounts'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),

    # Token lifecycle handled by SimpleJWT's own views — no need to reimplement.
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token-verify'),

    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]
