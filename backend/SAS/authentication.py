from rest_framework import authentication
from django.contrib.auth import get_user_model

class DevelopmentAuthentication(authentication.BaseAuthentication):
    """
    Mock authentication for local Flutter app testing.
    It automatically logs in as the first user in the database.
    """
    def authenticate(self, request):
        User = get_user_model()
        user = User.objects.first()
        if not user:
            # Create a fallback user if the database is completely empty
            user = User.objects.create(email='test@example.com', role='admin', is_approved=True)

        # Ensure the user has the required underlying fields for the ML endpoints
        user.is_approved = True
        user.is_active = True
        user.role = 'admin'
        user.employment_status = 'active'
        return (user, None)
