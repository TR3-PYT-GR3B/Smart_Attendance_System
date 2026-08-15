import io
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ChallengePurpose, FaceProfile, LivenessChallenge
from .services import (
    FaceAnalysisResult,
    FaceProcessingError,
    consume_and_process_liveness_challenge,
    issue_liveness_challenge,
    validate_guided_pose,
)


User = get_user_model()


def make_frame(index):
    buffer = io.BytesIO()
    Image.new('RGB', (96, 96), (40 + index, 80, 120)).save(buffer, format='JPEG')
    return SimpleUploadedFile(
        f'frame-{index}.jpg',
        buffer.getvalue(),
        content_type='image/jpeg',
    )


def successful_processing():
    embedding = [1.0] + [0.0] * 511
    liveness = SimpleNamespace(
        passed=True,
        score=0.91,
        reason='',
        yaw_by_action={'straight': 1.0, 'turn_left': -24.0, 'turn_right': 23.0},
        continuity_score=0.96,
    )
    return SimpleNamespace(
        liveness=liveness,
        embeddings=[embedding, embedding, embedding],
        analyses=[object(), object(), object()],
    )


class EnrollmentLifecycleTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='worker@example.test',
            password='Permanent-Pass-456!',
            is_approved=True,
            must_change_password=False,
            face_enrollment_allowed=True,
        )
        self.client.force_authenticate(self.user)

    def test_server_issues_short_lived_enrollment_challenge(self):
        response = self.client.post(
            reverse('enrollment:liveness-challenge'),
            {'purpose': ChallengePurpose.ENROLLMENT},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['actions'],
            ['straight', 'turn_left', 'turn_right'],
        )
        self.assertTrue(LivenessChallenge.objects.filter(pk=response.data['id']).exists())

    @patch('enrollment.serializers.consume_and_process_liveness_challenge')
    def test_consent_and_three_frames_create_one_face_profile(self, process):
        process.return_value = successful_processing()
        challenge = LivenessChallenge.objects.create(
            user=self.user,
            purpose=ChallengePurpose.ENROLLMENT,
            actions=['straight', 'turn_left', 'turn_right'],
            expires_at=timezone.now() + timedelta(seconds=45),
        )

        response = self.client.post(
            reverse('enrollment:liveness-capture'),
            {
                'challenge_id': str(challenge.pk),
                'biometric_consent': True,
                'frames': [make_frame(1), make_frame(2), make_frame(3)],
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['next_step'], 'ready_to_check_in')
        self.assertNotIn('embedding', response.data['profile'])
        profile = FaceProfile.objects.get(user=self.user)
        self.assertEqual(profile.frames_captured, 3)
        self.assertEqual(len(profile.embedding), 512)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.biometric_consent_at)
        self.assertFalse(self.user.face_enrollment_allowed)

    def test_enrollment_refuses_missing_biometric_consent(self):
        response = self.client.post(
            reverse('enrollment:liveness-capture'),
            {
                'challenge_id': '00000000-0000-0000-0000-000000000001',
                'biometric_consent': False,
                'frames': [make_frame(1), make_frame(2), make_frame(3)],
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('biometric_consent', response.data)

    @patch('enrollment.views.analyze_face')
    def test_pose_check_confirms_a_browser_frame_without_consuming_challenge(
        self,
        analyze,
    ):
        challenge = LivenessChallenge.objects.create(
            user=self.user,
            purpose=ChallengePurpose.ENROLLMENT,
            actions=['straight', 'turn_left', 'turn_right'],
            expires_at=timezone.now() + timedelta(seconds=45),
        )
        analyze.return_value = FaceAnalysisResult(
            embedding=[1.0] + [0.0] * 511,
            yaw_degrees=1.0,
            detection_score=0.99,
        )

        response = self.client.post(
            reverse('enrollment:liveness-pose-check'),
            {
                'challenge_id': str(challenge.pk),
                'action': 'straight',
                'frame': make_frame(1),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['accepted'])
        challenge.refresh_from_db()
        self.assertIsNone(challenge.used_at)


class ActiveLivenessServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='liveness@example.test',
            password='Permanent-Pass-456!',
        )
        self.embedding = [1.0] + [0.0] * 511

    def analysis_for(self, action):
        yaw = {'straight': 0.0, 'turn_left': -24.0, 'turn_right': 24.0}[action]
        return FaceAnalysisResult(
            embedding=self.embedding,
            yaw_degrees=yaw,
            detection_score=0.99,
        )

    @patch('enrollment.services.analyze_face')
    def test_valid_challenge_passes_once_and_cannot_be_replayed(self, analyze):
        challenge = issue_liveness_challenge(self.user, ChallengePurpose.ATTENDANCE)
        analyze.side_effect = [self.analysis_for(action) for action in challenge.actions]

        processed = consume_and_process_liveness_challenge(
            self.user,
            challenge.pk,
            ChallengePurpose.ATTENDANCE,
            [b'frame-1', b'frame-2', b'frame-3'],
        )

        self.assertTrue(processed.liveness.passed)
        challenge.refresh_from_db()
        self.assertIsNotNone(challenge.used_at)
        with self.assertRaises(FaceProcessingError):
            consume_and_process_liveness_challenge(
                self.user,
                challenge.pk,
                ChallengePurpose.ATTENDANCE,
                [b'frame-1', b'frame-2', b'frame-3'],
            )

    def test_guided_pose_rejects_wrong_turn_direction(self):
        result = validate_guided_pose(
            FaceAnalysisResult(
                embedding=self.embedding,
                yaw_degrees=24.0,
                detection_score=0.99,
            ),
            'turn_left',
        )

        self.assertFalse(result.accepted)
        self.assertIn('left', result.message.lower())
