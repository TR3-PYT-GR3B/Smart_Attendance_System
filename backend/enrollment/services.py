"""Low-resource face recognition and server-issued active liveness checks."""

import logging
import math
import secrets
import threading
from dataclasses import dataclass
from datetime import timedelta

import cv2
import numpy as np
from django.conf import settings
from django.utils import timezone
from insightface.app import FaceAnalysis

from .models import ChallengePurpose, LivenessChallenge


logger = logging.getLogger(__name__)

FACE_MODEL_VERSION = 'arcface-buffalo_l-v1'
ACTIVE_LIVENESS_ACTIONS = ('straight', 'turn_left', 'turn_right')


class FaceProcessingError(Exception):
    """Raised when a capture cannot produce a safe verification decision."""


@dataclass
class FaceAnalysisResult:
    embedding: list[float]
    yaw_degrees: float
    detection_score: float
    pitch_degrees: float = 0.0
    roll_degrees: float = 0.0
    centre_x_ratio: float = 0.5
    centre_y_ratio: float = 0.5
    face_area_ratio: float = 0.25


@dataclass
class GuidedPoseResult:
    accepted: bool
    message: str
    yaw_degrees: float


@dataclass
class ActiveLivenessResult:
    passed: bool
    score: float
    reason: str
    yaw_by_action: dict[str, float]
    continuity_score: float


@dataclass
class ProcessedLiveness:
    challenge: LivenessChallenge
    analyses: list[FaceAnalysisResult]
    liveness: ActiveLivenessResult

    @property
    def embeddings(self):
        return [analysis.embedding for analysis in self.analyses]

    @property
    def straight_embedding(self):
        index = self.challenge.actions.index('straight')
        return self.analyses[index].embedding


_face_app = None
_face_app_error = None
_face_app_lock = threading.Lock()


def _get_face_app():
    """Load only the three CPU models this workflow needs, on first use."""
    global _face_app, _face_app_error

    if _face_app is not None:
        return _face_app
    if _face_app_error is not None:
        raise FaceProcessingError('Face ML model is not initialized on the server.')

    with _face_app_lock:
        if _face_app is not None:
            return _face_app
        try:
            app = FaceAnalysis(
                name='buffalo_l',
                root=str(settings.FACE_MODEL_DIR),
                allowed_modules=['detection', 'recognition', 'landmark_3d_68'],
                providers=['CPUExecutionProvider'],
            )
            detection_size = int(getattr(settings, 'FACE_DETECTION_SIZE', 320))
            app.prepare(ctx_id=0, det_size=(detection_size, detection_size))
            _face_app = app
            return _face_app
        except Exception as error:  # pragma: no cover - depends on local model files
            _face_app_error = error
            logger.exception('Failed to initialize InsightFace')
            raise FaceProcessingError(
                'Face ML model is not initialized on the server.'
            ) from error


def _read_image_bytes(image):
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)

    if hasattr(image, 'read'):
        if hasattr(image, 'seek'):
            image.seek(0)
        data = image.read()
        if hasattr(image, 'seek'):
            image.seek(0)
        return data

    raise FaceProcessingError('Unsupported image input; expected a file or bytes.')


def _get_cv2_image(image):
    data = _read_image_bytes(image)
    if not data:
        raise FaceProcessingError('The uploaded image is empty.')

    image_array = np.frombuffer(data, np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded is None:
        raise FaceProcessingError('Could not decode image.')
    return decoded


def analyze_face(image):
    """Detect one face once and reuse its pose and ArcFace embedding."""
    decoded = _get_cv2_image(image)
    faces = _get_face_app().get(decoded)
    if not faces:
        raise FaceProcessingError('No face detected in the image.')
    if len(faces) > 1:
        raise FaceProcessingError('Multiple faces detected. Ensure only one face is visible.')

    face = faces[0]
    if face.embedding is None:
        raise FaceProcessingError('The recognition model did not produce an embedding.')
    if face.pose is None or len(face.pose) < 2:
        raise FaceProcessingError('The pose model is unavailable; active liveness cannot be verified.')

    embedding = face.embedding.tolist()
    norm = math.sqrt(sum(value * value for value in embedding))
    if norm == 0:
        raise FaceProcessingError('Invalid face embedding generated.')

    image_height, image_width = decoded.shape[:2]
    left, top, right, bottom = [float(value) for value in face.bbox]
    box_width = max(0.0, right - left)
    box_height = max(0.0, bottom - top)

    return FaceAnalysisResult(
        embedding=[value / norm for value in embedding],
        yaw_degrees=float(face.pose[1]),
        detection_score=float(face.det_score),
        pitch_degrees=float(face.pose[0]),
        roll_degrees=float(face.pose[2]),
        centre_x_ratio=((left + right) / 2.0) / max(image_width, 1),
        centre_y_ratio=((top + bottom) / 2.0) / max(image_height, 1),
        face_area_ratio=(box_width * box_height) / max(image_width * image_height, 1),
    )


def validate_guided_pose(analysis, action):
    """Give the browser a lightweight, server-authoritative capture prompt."""
    if action not in ACTIVE_LIVENESS_ACTIONS:
        return GuidedPoseResult(False, 'Unsupported face position.', analysis.yaw_degrees)

    if abs(analysis.centre_x_ratio - 0.5) > 0.18 or abs(analysis.centre_y_ratio - 0.5) > 0.20:
        return GuidedPoseResult(
            False,
            'Centre your face inside the circle.',
            analysis.yaw_degrees,
        )
    if analysis.face_area_ratio < 0.09:
        return GuidedPoseResult(False, 'Move a little closer.', analysis.yaw_degrees)
    if analysis.face_area_ratio > 0.62:
        return GuidedPoseResult(False, 'Move a little farther away.', analysis.yaw_degrees)
    if abs(analysis.pitch_degrees) > 15:
        return GuidedPoseResult(False, 'Keep your chin level.', analysis.yaw_degrees)
    if abs(analysis.roll_degrees) > 15:
        return GuidedPoseResult(False, 'Keep your head upright.', analysis.yaw_degrees)

    straight_limit = float(getattr(settings, 'LIVENESS_STRAIGHT_MAX_YAW', 12.0))
    turn_minimum = float(getattr(settings, 'LIVENESS_TURN_MIN_YAW', 15.0))
    yaw = analysis.yaw_degrees

    if action == 'straight' and abs(yaw) > straight_limit:
        return GuidedPoseResult(False, 'Look straight at the camera.', yaw)
    # InsightFace uses negative yaw for the subject's left and positive yaw for
    # the subject's right on the unmirrored image uploaded by the camera.
    if action == 'turn_left' and yaw > -turn_minimum:
        return GuidedPoseResult(False, 'Turn your head farther to the left.', yaw)
    if action == 'turn_right' and yaw < turn_minimum:
        return GuidedPoseResult(False, 'Turn your head farther to the right.', yaw)

    return GuidedPoseResult(True, 'Position confirmed.', yaw)


def generate_embedding(image):
    """Compatibility helper for callers that only need one embedding."""
    return analyze_face(image).embedding


def cosine_similarity(first, second):
    if not first or not second or len(first) != len(second):
        return 0.0
    dot = sum(a * b for a, b in zip(first, second))
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        return 0.0
    return dot / (first_norm * second_norm)


def average_embeddings(embeddings):
    """Average several unit embeddings and normalize the result."""
    if not embeddings:
        raise FaceProcessingError('At least one embedding is required.')

    dimensions = len(embeddings[0])
    if any(len(embedding) != dimensions for embedding in embeddings):
        raise FaceProcessingError('All embeddings must have the same number of dimensions.')

    count = len(embeddings)
    mean = [sum(embedding[i] for embedding in embeddings) / count for i in range(dimensions)]
    norm = math.sqrt(sum(value * value for value in mean))
    if norm == 0:
        raise FaceProcessingError('Averaged embedding is degenerate; re-capture the frames.')
    return [value / norm for value in mean]


def issue_liveness_challenge(user, purpose):
    """Issue one expiring challenge and invalidate older unused ones."""
    if purpose not in ChallengePurpose.values:
        raise ValueError('Unsupported liveness challenge purpose.')

    now = timezone.now()
    LivenessChallenge.objects.filter(
        user=user,
        purpose=purpose,
        used_at__isnull=True,
    ).update(used_at=now)

    side_actions = ['turn_left', 'turn_right']
    if purpose == ChallengePurpose.ATTENDANCE:
        secrets.SystemRandom().shuffle(side_actions)
    # Enrollment deliberately teaches the predictable straight -> left ->
    # right sequence. Attendance keeps the two turns randomized so a daily
    # verification is still an actual server-issued challenge.
    actions = ['straight', *side_actions]
    lifetime_seconds = int(getattr(settings, 'LIVENESS_CHALLENGE_TTL_SECONDS', 90))

    return LivenessChallenge.objects.create(
        user=user,
        purpose=purpose,
        actions=actions,
        expires_at=now + timedelta(seconds=lifetime_seconds),
    )


def _verify_active_liveness(actions, analyses):
    if len(actions) != len(analyses) or set(actions) != set(ACTIVE_LIVENESS_ACTIONS):
        return ActiveLivenessResult(False, 0.0, 'Invalid liveness sequence.', {}, 0.0)

    yaw_by_action = {
        action: analyses[index].yaw_degrees
        for index, action in enumerate(actions)
    }
    straight_limit = float(getattr(settings, 'LIVENESS_STRAIGHT_MAX_YAW', 12.0))
    turn_minimum = float(getattr(settings, 'LIVENESS_TURN_MIN_YAW', 15.0))
    continuity_threshold = float(
        getattr(settings, 'LIVENESS_SEQUENCE_FACE_THRESHOLD', 0.45)
    )

    straight_yaw = yaw_by_action['straight']
    first_turn = yaw_by_action['turn_left']
    second_turn = yaw_by_action['turn_right']

    similarities = []
    reference = analyses[actions.index('straight')].embedding
    for analysis in analyses:
        similarities.append(cosine_similarity(reference, analysis.embedding))
    continuity_score = min(similarities)

    reasons = []
    if abs(straight_yaw) > straight_limit:
        reasons.append('The straight-ahead frame was not centred.')
    if abs(first_turn) < turn_minimum or abs(second_turn) < turn_minimum:
        reasons.append('Both head turns must be clearly visible.')
    if first_turn * second_turn >= 0:
        reasons.append('The two head-turn frames must show opposite directions.')
    if continuity_score < continuity_threshold:
        reasons.append('The same person must remain visible throughout the challenge.')

    motion_score = min(
        1.0,
        abs(first_turn) / turn_minimum,
        abs(second_turn) / turn_minimum,
    )
    centering_score = max(0.0, 1.0 - abs(straight_yaw) / max(straight_limit, 1.0))
    score = min(motion_score, continuity_score, max(centering_score, 0.01))

    return ActiveLivenessResult(
        passed=not reasons,
        score=score,
        reason=' '.join(reasons),
        yaw_by_action=yaw_by_action,
        continuity_score=continuity_score,
    )


def consume_and_process_liveness_challenge(user, challenge_id, purpose, frames):
    """Consume a challenge exactly once, analyze its frames, and verify motion."""
    try:
        challenge = LivenessChallenge.objects.get(
            pk=challenge_id,
            user=user,
            purpose=purpose,
        )
    except (LivenessChallenge.DoesNotExist, ValueError, TypeError) as error:
        raise FaceProcessingError('Invalid liveness challenge.') from error

    now = timezone.now()
    if challenge.expires_at <= now:
        raise FaceProcessingError('The liveness challenge expired. Start a new capture.')

    consumed = LivenessChallenge.objects.filter(
        pk=challenge.pk,
        used_at__isnull=True,
        expires_at__gt=now,
    ).update(used_at=now)
    if consumed != 1:
        raise FaceProcessingError('The liveness challenge has already been used.')
    challenge.used_at = now

    if len(frames) != len(challenge.actions):
        raise FaceProcessingError(
            f'Expected {len(challenge.actions)} challenge frames, received {len(frames)}.'
        )

    analyses = [analyze_face(frame) for frame in frames]
    liveness = _verify_active_liveness(challenge.actions, analyses)
    return ProcessedLiveness(challenge=challenge, analyses=analyses, liveness=liveness)


def is_model_unavailable():
    try:
        _get_face_app()
    except FaceProcessingError:
        return True
    return False


def is_stub_active():
    """Backward-compatible health-check name used by older callers."""
    return is_model_unavailable()
