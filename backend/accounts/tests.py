import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class FirstLoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='worker@example.test',
            password='Temporary-Pass-123!',
            first_name='Ada',
            last_name='Obi',
            is_approved=True,
        )

    def login(self):
        return self.client.post(
            reverse('accounts:login'),
            {'email': self.user.email, 'password': 'Temporary-Pass-123!'},
            format='json',
        )

    def test_login_routes_new_worker_to_password_change(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['next_step'], 'change_password')
        self.assertTrue(response.data['user']['must_change_password'])

    def test_password_change_routes_worker_to_face_enrollment(self):
        login = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.post(
            reverse('accounts:change-password'),
            {
                'current_password': 'Temporary-Pass-123!',
                'new_password': 'Permanent-Pass-456!',
                'new_password_confirm': 'Permanent-Pass-456!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['next_step'], 'enroll_face')
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password('Permanent-Pass-456!'))

    def test_public_registration_endpoint_is_not_exposed(self):
        response = self.client.post('/api/auth/register/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_rotated_refresh_token_cannot_be_replayed(self):
        login = self.login()
        original_refresh = login.data['refresh']

        rotated = self.client.post(
            reverse('accounts:token-refresh'),
            {'refresh': original_refresh},
            format='json',
        )
        replay = self.client.post(
            reverse('accounts:token-refresh'),
            {'refresh': original_refresh},
            format='json',
        )

        self.assertEqual(rotated.status_code, status.HTTP_200_OK)
        self.assertIn('refresh', rotated.data)
        self.assertEqual(replay.status_code, status.HTTP_401_UNAUTHORIZED)


class EnsureAdminCommandTests(APITestCase):
    def test_command_creates_admin_then_remains_idempotent(self):
        environment = {
            'DJANGO_SUPERUSER_EMAIL': 'owner@example.test',
            'DJANGO_SUPERUSER_PASSWORD': 'Deployment-Pass-123!',
        }
        output = StringIO()

        with patch.dict(os.environ, environment, clear=False):
            call_command('ensure_admin', stdout=output)
            call_command('ensure_admin', stdout=output)

        user = User.objects.get(email=environment['DJANGO_SUPERUSER_EMAIL'])
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_approved)
        self.assertTrue(user.check_password(environment['DJANGO_SUPERUSER_PASSWORD']))
        self.assertEqual(User.objects.filter(email=user.email).count(), 1)

    def test_existing_admin_password_is_not_reset_by_default(self):
        user = User.objects.create_superuser(
            email='owner@example.test',
            password='Existing-Pass-123!',
        )
        environment = {
            'DJANGO_SUPERUSER_EMAIL': user.email,
            'DJANGO_SUPERUSER_PASSWORD': 'Different-Pass-456!',
        }

        with patch.dict(os.environ, environment, clear=False):
            call_command('ensure_admin', stdout=StringIO())

        user.refresh_from_db()
        self.assertTrue(user.check_password('Existing-Pass-123!'))
