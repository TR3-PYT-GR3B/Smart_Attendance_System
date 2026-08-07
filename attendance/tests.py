"""
End-to-end tests for the attendance flow.

Covers the whole journey — register, approve, enrol, check in, check out, read
history — plus the cases that matter most: a worker outside the geofence, a
worker whose face does not match, and an unapproved account.

The face pipeline is the deterministic stub from ``enrollment.services``, which
is what makes these assertions possible: the same image bytes always produce the
same embedding, so "same photo" reliably matches and "different photo" reliably
does not.
"""

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from approvals.models import AccountApprovalRequest, ApprovalStatus
from enrollment.models import FaceProfile
from organisations.models import Department, Organization, WorkLocation


from .models import AttendanceRecord, AttendanceStatus, AttemptType, VerificationAttempt

User = get_user_model()


def make_image(colour, name='face.jpg'):
    """
    Build a real JPEG in memory.

    The colour is what makes two images differ, and since the stub embeds the
    file's bytes, a different colour stands in for a different person.
    """
    buffer = io.BytesIO()
    Image.new('RGB', (64, 64), colour).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class AttendanceFlowTests(APITestCase):
    """The full worker journey, and the ways it can legitimately fail."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Acme Ltd')
        cls.department = Department.objects.create(
            name='Operations',
            organization=cls.organization,
        )

        # A tight 100 m fence in central Lagos, so a nearby-but-outside point is
        # easy to construct.
        cls.location = WorkLocation.objects.create(
            name='Head Office',
            department=cls.department,
            latitude=6.5244,
            longitude=3.3792,
            radius_meters=100,
        )

    def setUp(self):
        # The face used at enrolment. Reused for a matching check-in.
        self.enrolled_face = lambda: make_image('blue')
        self.other_face = lambda: make_image('red')

    # ── Helpers ──

    def register_worker(self, email='worker@acme.test'):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'email': email,
                'password': 'Str0ng-Passw0rd!',
                'password_confirm': 'Str0ng-Passw0rd!',
                'first_name': 'Ada',
                'last_name': 'Obi',
                'department_id': self.department.id,
                'biometric_consent': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return User.objects.get(email=email)

    def login(self, email='worker@acme.test', password='Str0ng-Passw0rd!'):
        response = self.client.post(
            reverse('accounts:login'),
            {'email': email, 'password': password},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return response.data

    def approve(self, user):
        """Stand in for the admin approval queue, which is not built yet."""
        user.is_approved = True
        user.save(update_fields=['is_approved'])

    def enroll(self):
        response = self.client.post(
            reverse('enrollment:liveness-capture'),
            {'frames': [self.enrolled_face()]},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response

    # ── Registration and approval ──

    def test_registration_creates_unapproved_worker_and_approval_request(self):
        user = self.register_worker()

        self.assertFalse(user.is_approved)
        self.assertEqual(user.role, User._meta.get_field('role').default)
        self.assertIsNotNone(user.biometric_consent_at)

        # The worker must be sitting in the admin queue, pending review.
        approval_request = AccountApprovalRequest.objects.get(user=user)
        self.assertEqual(approval_request.status, ApprovalStatus.PENDING)
        self.assertTrue(approval_request.is_pending)

        # And they cannot record attendance until that request is approved.
        self.assertFalse(user.can_record_attendance)


    def test_registration_requires_biometric_consent(self):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'email': 'nope@acme.test',
                'password': 'Str0ng-Passw0rd!',
                'password_confirm': 'Str0ng-Passw0rd!',
                'first_name': 'No',
                'last_name': 'Consent',
                'biometric_consent': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('biometric_consent', response.data)
        self.assertFalse(User.objects.filter(email='nope@acme.test').exists())

    # ── Enrolment ──

    def test_enrollment_stores_a_face_profile_without_exposing_the_embedding(self):
        self.register_worker()
        self.login()

        response = self.enroll()

        profile = FaceProfile.objects.get()
        self.assertEqual(len(profile.embedding), 512)
        self.assertTrue(profile.is_active)

        # The vector itself is biometric data and must never be returned.
        self.assertNotIn('embedding', response.data['profile'])

    def test_enrollment_status_reports_the_next_step(self):
        self.register_worker()
        self.login()

        # Not enrolled yet.
        response = self.client.get(reverse('enrollment:status'))
        self.assertEqual(response.data['next_step'], 'enroll_face')

        self.enroll()

        # Enrolled, but still awaiting approval.
        response = self.client.get(reverse('enrollment:status'))
        self.assertTrue(response.data['is_enrolled'])
        self.assertEqual(response.data['next_step'], 'await_approval')

    # ── Check-in ──

    def test_full_flow_check_in_then_check_out_then_history(self):
        user = self.register_worker()
        self.login()
        self.enroll()
        self.approve(user)

        # Check in at the office with the enrolled face.
        response = self.client.post(
            reverse('attendance:check-in'),
            {
                'work_location_id': self.location.id,
                'latitude': 6.5244,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['verification']['passed'])
        self.assertTrue(response.data['verification']['gps_passed'])
        self.assertTrue(response.data['verification']['face_passed'])

        record = AttendanceRecord.objects.get()
        self.assertEqual(record.status, AttendanceStatus.PRESENT)
        self.assertTrue(record.is_open)

        # All three gates were recorded and tied to the record.
        attempts = VerificationAttempt.objects.filter(attendance_record=record)
        self.assertEqual(attempts.count(), 3)
        self.assertTrue(all(attempt.result for attempt in attempts))

        # Check out from the same place with the same face.
        response = self.client.post(
            reverse('attendance:check-out'),
            {
                'latitude': 6.5244,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertFalse(record.is_open)
        self.assertEqual(record.status, AttendanceStatus.PRESENT)

        # History shows the completed session.
        response = self.client.get(reverse('attendance:history'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0]['check_out_time'])

    def test_check_in_outside_the_geofence_is_refused_but_still_logged(self):
        user = self.register_worker()
        self.login()
        self.enroll()
        self.approve(user)

        # Roughly 1.5 km north of the office — well outside a 100 m fence.
        response = self.client.post(
            reverse('attendance:check-in'),
            {
                'work_location_id': self.location.id,
                'latitude': 6.5380,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data['verification']['gps_passed'])

        # Nothing recorded as attendance...
        self.assertFalse(AttendanceRecord.objects.exists())

        # ...but the failed GPS check is on file for the dispute trail.
        gps_attempt = VerificationAttempt.objects.get(attempt_type=AttemptType.GPS)
        self.assertFalse(gps_attempt.result)
        self.assertGreater(gps_attempt.score, self.location.radius_meters)

    def test_check_in_with_a_different_face_is_refused(self):
        user = self.register_worker()
        self.login()
        self.enroll()
        self.approve(user)

        # Right place, wrong person.
        response = self.client.post(
            reverse('attendance:check-in'),
            {
                'work_location_id': self.location.id,
                'latitude': 6.5244,
                'longitude': 3.3792,
                'face_image': self.other_face(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.data['verification']['gps_passed'])
        self.assertFalse(response.data['verification']['face_passed'])
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_unapproved_worker_cannot_check_in(self):
        self.register_worker()
        self.login()
        self.enroll()
        # Deliberately not approved.

        response = self.client.post(
            reverse('attendance:check-in'),
            {
                'work_location_id': self.location.id,
                'latitude': 6.5244,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_cannot_check_in_twice_without_checking_out(self):
        user = self.register_worker()
        self.login()
        self.enroll()
        self.approve(user)

        payload = {
            'work_location_id': self.location.id,
            'latitude': 6.5244,
            'longitude': 3.3792,
        }

        first = self.client.post(
            reverse('attendance:check-in'),
            {**payload, 'face_image': self.enrolled_face()},
            format='multipart',
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            reverse('attendance:check-in'),
            {**payload, 'face_image': self.enrolled_face()},
            format='multipart',
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_check_out_without_an_open_session_is_rejected(self):
        user = self.register_worker()
        self.login()
        self.enroll()
        self.approve(user)

        response = self.client.post(
            reverse('attendance:check-out'),
            {
                'latitude': 6.5244,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_failed_check_out_is_recorded_and_flagged(self):
        user = self.register_worker()
        self.login()
        self.enroll()
        self.approve(user)

        self.client.post(
            reverse('attendance:check-in'),
            {
                'work_location_id': self.location.id,
                'latitude': 6.5244,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        # Check out from far away — the session closes, but gets flagged rather
        # than being left open forever.
        response = self.client.post(
            reverse('attendance:check-out'),
            {
                'latitude': 6.5380,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        record = AttendanceRecord.objects.get()
        self.assertFalse(record.is_open)
        self.assertEqual(record.status, AttendanceStatus.FLAGGED)
        self.assertIn('Check-out verification failed', record.notes)

    # ── Scoping ──

    def test_history_shows_only_the_callers_own_records(self):
        first = self.register_worker('first@acme.test')
        self.login('first@acme.test')
        self.enroll()
        self.approve(first)

        self.client.post(
            reverse('attendance:check-in'),
            {
                'work_location_id': self.location.id,
                'latitude': 6.5244,
                'longitude': 3.3792,
                'face_image': self.enrolled_face(),
            },
            format='multipart',
        )

        # A second worker must not see the first one's attendance.
        self.client.credentials()
        second = self.register_worker('second@acme.test')
        self.login('second@acme.test')
        self.approve(second)

        response = self.client.get(reverse('attendance:history'))
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 0)
