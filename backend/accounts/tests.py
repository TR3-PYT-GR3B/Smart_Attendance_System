from django.contrib.auth import get_user_model
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
