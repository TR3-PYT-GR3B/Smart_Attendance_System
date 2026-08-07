"""
Face processing service layer.

Everything that turns an uploaded image into numbers lives here, behind three
functions the rest of the codebase calls:

* ``generate_embedding(image)`` — a 512-value ArcFace vector for one face.
* ``estimate_liveness(image)`` — anti-spoofing confidence for one frame.
* ``average_embeddings(vectors)`` — combine enrolment frames into one reference.

=============================================================================
PLACEHOLDER IMPLEMENTATION — NOT PRODUCTION FACE RECOGNITION
=============================================================================
``generate_embedding`` and ``estimate_liveness`` are currently *stubs*. They
derive a deterministic pseudo-vector from the bytes of the uploaded image rather
than detecting a face, so the same image always produces the same embedding and
two different images produce different ones. That is enough to exercise and test
the enrolment and check-in flows end to end, and nothing more.

It cannot tell one person from another. Do not deploy it.

Replacing it means editing only the two ``_stub_*`` calls below: load the SCRFD
detector and ArcFace recogniser from ``settings.FACE_MODEL_DIR`` with ONNX
Runtime, and return the real vector and the real anti-spoofing score. Every
caller — serializers, views, the check-in gates — keeps working unchanged,
because they only ever see the function signatures.
=============================================================================
"""

import hashlib
import math

from django.conf import settings

# Marks embeddings produced by the stub. Real weights should report the actual
# model name (e.g. 'buffalo_l/w600k_r50') so old profiles can be spotted and
# re-enrolled after a model upgrade.
STUB_MODEL_VERSION = 'stub-v1'


class FaceProcessingError(Exception):
    """
    Raised when an image cannot be processed at all.

    Distinct from "this face does not match": a failure here means no face was
    found, the file was unreadable, or the model could not run — a 400-level
    problem with the upload rather than a verification decision.
    """


def _read_image_bytes(image):
    """
    Pull raw bytes out of whatever the caller passed.

    Accepts an ``UploadedFile``, an open file object, or plain ``bytes``, so
    callers do not have to normalise before calling.
    """
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)

    if hasattr(image, 'read'):
        # Rewind first — DRF may already have consumed the stream during
        # validation, which would otherwise yield zero bytes here.
        if hasattr(image, 'seek'):
            image.seek(0)
        data = image.read()
        if hasattr(image, 'seek'):
            image.seek(0)
        return data

    raise FaceProcessingError('Unsupported image input; expected a file or bytes.')


def _stub_vector_from_bytes(data, dimensions):
    """
    Build a deterministic unit vector from image bytes.

    Uses SHA-256 as a cheap pseudo-random source seeded by the image content:
    identical images give identical vectors (so a re-upload verifies against
    itself), while different images give near-orthogonal ones (so they fail to
    match). The vector is L2-normalised because cosine similarity is what the
    comparison uses.

    This is a stand-in for a real embedding and carries no facial meaning.
    """
    components = []
    counter = 0

    # Extend the digest until there are enough values for the full vector.
    while len(components) < dimensions:
        digest = hashlib.sha256(data + counter.to_bytes(4, 'big')).digest()
        # Map each byte into roughly -1.0 to 1.0.
        components.extend((byte - 127.5) / 127.5 for byte in digest)
        counter += 1

    components = components[:dimensions]

    norm = math.sqrt(sum(value * value for value in components))
    if norm == 0:
        raise FaceProcessingError('Could not derive an embedding from this image.')

    return [value / norm for value in components]


def generate_embedding(image):
    """
    Return the face embedding for one image.

    STUB: derives a deterministic vector from the file's bytes instead of
    detecting and encoding a face. See the module docstring.
    """
    data = _read_image_bytes(image)

    if not data:
        raise FaceProcessingError('The uploaded image is empty.')

    dimensions = getattr(settings, 'FACE_EMBEDDING_DIM', 512)
    return _stub_vector_from_bytes(data, dimensions)


def estimate_liveness(image):
    """
    Return an anti-spoofing confidence between 0.0 and 1.0.

    STUB: returns a fixed passing score for any readable image. A real
    implementation runs a spoof-detection model so that a printed photo or a
    screen held to the camera scores low and is refused.

    Deliberately returns a *passing* value so the rest of the pipeline is
    testable — which is exactly why this must be replaced before deployment.
    """
    data = _read_image_bytes(image)

    if not data:
        raise FaceProcessingError('The uploaded image is empty.')

    # Comfortably above the configured threshold, but not a suspiciously
    # perfect 1.0, which would look odd in the stored verification log.
    return 0.95


def average_embeddings(embeddings):
    """
    Combine several enrolment frames into one reference embedding.

    Averaging over a guided sequence ("look straight", "turn slightly left")
    produces a reference that tolerates small changes in angle and lighting far
    better than a single photograph. The mean is re-normalised so the result is
    still a unit vector and stays comparable by cosine similarity.
    """
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


def is_stub_active():
    """
    Whether face processing is still running on the placeholder.

    Handy for a health endpoint or a startup warning, so a deployment cannot
    quietly go live with fake matching enabled.
    """
    return True
