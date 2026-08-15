from django.contrib.staticfiles import finders
from django.test import RequestFactory, TestCase
from django.urls import reverse

from SAS.dashboard import custom_dashboard_callback
from accounts.models import User


class DashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='dashboard-admin@example.com',
            password='test-password',
        )

    def test_callback_handles_supported_and_invalid_filters_without_data(self):
        request_factory = RequestFactory()

        for requested_filter, expected_filter in (
            ('this_week', 'this_week'),
            ('this_month', 'this_month'),
            ('this_year', 'this_year'),
            ('unsupported', 'this_week'),
        ):
            with self.subTest(requested_filter=requested_filter):
                request = request_factory.get('/', {'filter': requested_filter})
                request.user = self.admin
                context = custom_dashboard_callback(request, {})

                self.assertEqual(context['current_filter'], expected_filter)
                self.assertEqual(context['attendance_labels'], ['No data yet'])
                self.assertEqual(context['attendance_data'], [0])

    def test_admin_dashboard_renders_and_uses_packaged_javascript(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Attendance Overview')
        self.assertContains(response, 'Pending Actions')
        self.assertIsNotNone(finders.find('js/dashboard.js'))
