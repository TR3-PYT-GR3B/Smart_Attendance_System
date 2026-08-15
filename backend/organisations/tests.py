from django.contrib.staticfiles import finders
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .admin import WorkLocationAdmin


class WorkLocationAdminMediaTests(SimpleTestCase):
    def test_geolocation_assets_are_attached_and_discoverable(self):
        self.assertIn(
            'organisations/js/work_location_geolocation.js',
            WorkLocationAdmin.Media.js,
        )
        self.assertIn(
            'organisations/css/work_location_geolocation.css',
            WorkLocationAdmin.Media.css['all'],
        )
        self.assertIsNotNone(
            finders.find('organisations/js/work_location_geolocation.js')
        )
        self.assertIsNotNone(
            finders.find('organisations/css/work_location_geolocation.css')
        )


class WorkLocationAdminPageTests(TestCase):
    def test_add_page_keeps_manual_fields_and_loads_gps_button_script(self):
        admin_user = get_user_model().objects.create_superuser(
            email='admin@example.test',
            password='Admin-Pass-123!',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:organisations_worklocation_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_latitude')
        self.assertContains(response, 'id_longitude')
        self.assertContains(response, 'organisations/js/work_location_geolocation.js')
