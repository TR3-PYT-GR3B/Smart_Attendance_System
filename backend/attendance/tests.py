import io
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from enrollment.models import FaceProfile
from organisations.models import Department, Organization, WorkLocation

from .models import AttendanceRecord, AttemptType, VerificationAttempt
from .services import check_face_match


User = get_user_model()


def make_frame(index):
    buffer = io.BytesIO()
    Image.new('RGB', (96, 96), (30 + index, 70, 110)).save(buffer, format='JPEG')
    return SimpleUploadedFile(
        f'attendance-{index}.jpg',
        buffer.getvalue(),
        content_type='image/jpeg',
    )


def successful_processing(embedding):
    return SimpleNamespace(
        liveness=SimpleNamespace(passed=True, score=0.92, reason=''),
        straight_embedding=embedding,
    )


class AttendanceFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        organization = Organization.objects.create(name='Acme Ltd')
        cls.department = Department.objects.create(name='Operations', organization=organization)
        cls.other_department = Department.objects.create(name='Finance', organization=organization)
        cls.location = WorkLocation.objects.create(
            name='Head Office',
            department=cls.department,
            latitude=6.5244,
            longitude=3.3792,
            radius_meters=100,
        )
        cls.other_location = WorkLocation.objects.create(
            name='Finance Office',
            department=cls.other_department,
            latitude=6.5244,
            longitude=3.3792,
            radius_meters=100,
        )

    def setUp(self):
        self.embedding = [1.0] + [0.0] * 511
        self.user = User.objects.create_user(
            email='worker@example.test',
            password='Permanent-Pass-456!',
            department=self.department,
            is_approved=True,
            must_change_password=False,
        )
        FaceProfile.objects.create(
            user=self.user,
            embedding=self.embedding,
            embedding_dim=512,
            model_version='test',
            is_active=True,
        )
        self.client.force_authenticate(self.user)

    def payload(self, *, location=None, latitude=6.5244, longitude=3.3792):
        return {
            'work_location_id': (location or self.location).pk,
            'challenge_id': str(uuid.uuid4()),
            'latitude': latitude,
            'longitude': longitude,
            'frames': [make_frame(1), make_frame(2), make_frame(3)],
        }

    @patch('attendance.services.consume_and_process_liveness_challenge')
    def test_check_in_and_check_out_use_three_frame_verification(self, process):
        process.return_value = successful_processing(self.embedding)

        check_in = self.client.post(
            reverse('attendance:check-in'),
            self.payload(),
            format='multipart',
        )
        self.assertEqual(check_in.status_code, status.HTTP_201_CREATED)
        self.assertTrue(check_in.data['verification']['passed'])

        record = AttendanceRecord.objects.get(user=self.user)
        self.assertTrue(record.is_open)
        self.assertEqual(
            VerificationAttempt.objects.filter(attendance_record=record).count(),
            3,
        )

        check_out_payload = self.payload()
        check_out_payload.pop('work_location_id')
        check_out = self.client.post(
            reverse('attendance:check-out'),
            check_out_payload,
            format='multipart',
        )
        self.assertEqual(check_out.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertFalse(record.is_open)
        self.assertEqual(
            VerificationAttempt.objects.filter(attendance_record=record).count(),
            6,
        )

    @patch('attendance.services.consume_and_process_liveness_challenge')
    def test_outside_geofence_is_refused_and_audited(self, process):
        process.return_value = successful_processing(self.embedding)
        response = self.client.post(
            reverse('attendance:check-in'),
            self.payload(latitude=6.5380),
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data['verification']['gps_passed'])
        self.assertFalse(AttendanceRecord.objects.exists())
        attempt = VerificationAttempt.objects.get(attempt_type=AttemptType.GPS)
        self.assertFalse(attempt.result)
        self.assertGreater(attempt.score, self.location.radius_meters)

    def test_worker_cannot_submit_another_departments_location(self):
        response = self.client.post(
            reverse('attendance:check-in'),
            self.payload(location=self.other_location),
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('work_location_id', response.data)

    def test_location_list_is_scoped_to_workers_department(self):
        response = self.client.get(reverse('attendance:locations'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual([row['id'] for row in results], [self.location.id])
        self.assertIn('latitude', results[0])

    def test_face_mismatch_reason_is_professional_and_hides_threshold(self):
        different_face = [0.0, 1.0] + [0.0] * 510

        result = check_face_match(self.user.face_profile, different_face)

        self.assertFalse(result.passed)
        self.assertIn('Face mismatch', result.reason)
        self.assertNotIn('0.60', result.reason)
        self.assertNotIn('similarity', result.reason.lower())
