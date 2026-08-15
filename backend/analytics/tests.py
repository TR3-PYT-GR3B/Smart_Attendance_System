from django.contrib.staticfiles import finders
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import RequestFactory, TestCase, override_settings
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


class HealthProbeTests(TestCase):
    def test_liveness_does_not_depend_on_external_services(self):
        response = self.client.get(reverse('health-live'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertIn('no-store', response['Cache-Control'])

    def test_readiness_reports_database_and_models(self):
        with TemporaryDirectory() as model_directory:
            required_files = ('models/detection.onnx', 'models/recognition.onnx')
            for relative_path in required_files:
                model_path = Path(model_directory, relative_path)
                model_path.parent.mkdir(parents=True, exist_ok=True)
                model_path.touch()

            with override_settings(
                FACE_MODEL_DIR=Path(model_directory),
                FACE_MODEL_REQUIRED_FILES=required_files,
            ):
                response = self.client.get(reverse('health-ready'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                'status': 'ready',
                'checks': {'database': True, 'face_models': True},
            },
        )

    @override_settings(
        FACE_MODEL_DIR=Path('missing-model-directory'),
        FACE_MODEL_REQUIRED_FILES=('missing.onnx',),
    )
    def test_readiness_is_unavailable_when_models_are_missing(self):
        response = self.client.get(reverse('health-ready'))

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['checks']['face_models'])
