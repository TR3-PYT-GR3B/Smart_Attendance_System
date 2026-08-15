"""
Server-side verification for attendance.

This module is where a check-in is accepted or refused. Three gates run in a
fixed order, and every one of them writes a ``VerificationAttempt`` row whether
it passes or fails:

1. **GPS** — is the worker actually inside the site's geofence?
2. **Liveness** — is this a live face rather than a photo of one?
3. **Face match** — is it the right person?

The order matters. GPS is cheap, so a worker in the wrong place is turned away
before any face processing happens. Liveness runs before matching because there
is no point comparing a face that is already known to be a spoof.

**The client never decides.** The mobile app uploads a frame and a pair of
coordinates; it does not send a score, a verdict, or a "verified" flag. Anything
of that sort arriving in a request is ignored. A rooted device can lie about
what it captured, but it cannot lie about the outcome, because the outcome is
computed here.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from enrollment.models import ChallengePurpose
from enrollment.services import FaceProcessingError, consume_and_process_liveness_challenge

from .models import AttemptType, AttendanceStatus, VerificationAttempt


@dataclass
class GateResult:
    """Outcome of a single gate, with the numbers behind the decision."""

    passed: bool
    score: float = None
    threshold: float = None
    reason: str = ''


@dataclass
class VerificationResult:
    """
    Combined outcome of all gates for one check-in or check-out attempt.

    Carries the individual results so the response can tell the worker *which*
    check failed — "you are 340 m from the site" is far more use than a bare
    "verification failed".
    """

    passed: bool
    gps: GateResult = None
    liveness: GateResult = None
    face: GateResult = None
    failure_reasons: list = field(default_factory=list)
    attempts: list = field(default_factory=list)

    @property
    def distance_meters(self):
        return self.gps.score if self.gps else None

    @property
    def face_score(self):
        return self.face.score if self.face else None


def _request_context(request):
    """Device and network details worth recording against an attempt."""
    if request is None:
        return {'device_info': '', 'ip_address': None}

    return {
        'device_info': request.META.get('HTTP_USER_AGENT', '')[:255],
        'ip_address': _client_ip(request),
    }


def _client_ip(request):
    """Prefer the forwarded-for address so a proxy does not mask the caller."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _record_attempt(user, attempt_type, gate_result, work_location=None,
                    latitude=None, longitude=None, request=None,
                    attendance_record=None):
    """
    Persist one gate's outcome.

    Called for failures as well as successes — a rejected check-in that left no
    trace would be impossible to investigate later, and the plan requires a full
    audit trail for disputes.
    """
    context = _request_context(request)

    return VerificationAttempt.objects.create(
        user=user,
        attendance_record=attendance_record,
        work_location=work_location,
        attempt_type=attempt_type,
        result=gate_result.passed,
        score=gate_result.score,
        threshold_used=gate_result.threshold,
        reason_failed=gate_result.reason,
        latitude=latitude,
        longitude=longitude,
        device_info=context['device_info'],
        ip_address=context['ip_address'],
    )


# ── Individual gates ──


def check_gps(work_location, latitude, longitude):
    """
    Gate 1: is the worker inside the geofence?

    ``score`` here is the distance in metres and ``threshold`` the site's
    radius, so the stored attempt shows exactly how far outside the fence a
    failed attempt was.
    """
    distance = work_location.distance_to(latitude, longitude)
    radius = work_location.radius_meters
    inside = distance <= radius

    reason = ''
    if not inside:
        reason = (
            f'{distance:.0f} m from {work_location.name}, which allows '
            f'{radius} m.'
        )

    return GateResult(passed=inside, score=distance, threshold=float(radius), reason=reason)


def check_face_match(face_profile, candidate_embedding):
    """
    Gate 3: is this the enrolled worker?

    Compares the already-processed straight-ahead frame against the stored
    reference. Reusing it avoids a second expensive model pass.
    """
    threshold = getattr(settings, 'FACE_MATCH_THRESHOLD', 0.60)

    if face_profile is None or not face_profile.is_active:
        return GateResult(
            passed=False,
            threshold=threshold,
            reason='No active face profile. Please complete enrolment first.',
        )

    if candidate_embedding is None:
        return GateResult(
            passed=False,
            threshold=threshold,
            reason='A face could not be extracted from the liveness sequence.',
        )

    try:
        similarity = face_profile.similarity_to(candidate_embedding)
    except ValueError as error:
        # Dimension mismatch — usually an embedding produced by a different
        # model version, which means the worker needs to re-enrol.
        return GateResult(
            passed=False,
            threshold=threshold,
            reason=f'{error} Please enrol again.',
        )

    passed = similarity >= threshold
    # Scores and thresholds remain available in the audit fields, but the
    # worker-facing reason should be clear without exposing model internals.
    reason = '' if passed else (
        'Face mismatch. We could not confirm that this person matches the '
        'face enrolled for this account. Please try again in good lighting.'
    )

    return GateResult(passed=passed, score=similarity, threshold=threshold, reason=reason)


# ── Full verification ──


def verify_attendance(user, work_location, latitude, longitude, challenge_id, frames,
                      request=None, attendance_record=None):
    """
    Run all three gates and record each outcome.

    Every gate runs even after one has failed. Stopping early would be slightly
    cheaper, but a complete set of attempts is much more useful when reviewing a
    flagged check-in: it shows whether the worker was in the wrong place, or the
    wrong person, or both.
    """
    face_profile = getattr(user, 'face_profile', None)
    failure_reasons = []
    attempts = []

    # Gate 1 — GPS.
    gps_result = check_gps(work_location, latitude, longitude)
    attempts.append(_record_attempt(
        user, AttemptType.GPS, gps_result, work_location,
        latitude, longitude, request, attendance_record,
    ))
    if not gps_result.passed:
        failure_reasons.append(gps_result.reason)

    # Gate 2 — liveness.
    processed = None
    try:
        processed = consume_and_process_liveness_challenge(
            user=user,
            challenge_id=challenge_id,
            purpose=ChallengePurpose.ATTENDANCE,
            frames=frames,
        )
        liveness_result = GateResult(
            passed=processed.liveness.passed,
            score=processed.liveness.score,
            threshold=None,
            reason=processed.liveness.reason,
        )
    except FaceProcessingError as error:
        liveness_result = GateResult(
            passed=False,
            threshold=None,
            reason=str(error),
        )

    attempts.append(_record_attempt(
        user, AttemptType.LIVENESS, liveness_result, work_location,
        latitude, longitude, request, attendance_record,
    ))
    if not liveness_result.passed:
        failure_reasons.append(liveness_result.reason)

    # Gate 3 — face match.
    candidate_embedding = processed.straight_embedding if processed is not None else None
    face_result = check_face_match(face_profile, candidate_embedding)
    attempts.append(_record_attempt(
        user, AttemptType.FACE, face_result, work_location,
        latitude, longitude, request, attendance_record,
    ))
    if not face_result.passed:
        failure_reasons.append(face_result.reason)

    return VerificationResult(
        passed=gps_result.passed and liveness_result.passed and face_result.passed,
        gps=gps_result,
        liveness=liveness_result,
        face=face_result,
        failure_reasons=failure_reasons,
        attempts=attempts,
    )


# ── Shift timing ──


def evaluate_punctuality(work_location, check_in_time=None):
    """
    Decide whether a check-in counts as present or late.

    A site without a configured shift start has no notion of lateness, so those
    check-ins are simply present. Otherwise the grace period is added to the
    shift start and anything after that is late, with the overshoot recorded in
    minutes for the punctuality trend on the dashboards.

    Returns ``(status, minutes_late)``.
    """
    if work_location.shift_start_time is None:
        return AttendanceStatus.PRESENT, 0

    check_in_time = check_in_time or timezone.now()
    local_time = timezone.localtime(check_in_time)

    # Build the shift start on the same calendar day as the check-in.
    shift_start = timezone.make_aware(
        datetime.combine(local_time.date(), work_location.shift_start_time),
        local_time.tzinfo,
    )

    cutoff = shift_start + timedelta(minutes=work_location.late_grace_minutes)

    if local_time <= cutoff:
        return AttendanceStatus.PRESENT, 0

    # Lateness is measured from the shift start, not from the end of the grace
    # period — the grace period decides *whether* someone is late, not by how
    # much.
    minutes_late = int((local_time - shift_start).total_seconds() // 60)
    return AttendanceStatus.LATE, minutes_late
