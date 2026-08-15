"""Worker-facing serializers for office document requests and submissions."""

from pathlib import Path

from django.utils import timezone
from rest_framework import serializers

from .models import (
    DocumentRequest,
    DocumentRequestStatus,
    DocumentStatus,
    WorkerDocument,
)


ALLOWED_UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf'}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'application/pdf',
    # Some mobile multipart clients send a generic type; the extension is
    # still validated and the file remains queued for human review.
    'application/octet-stream',
}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


class WorkerDocumentSerializer(serializers.ModelSerializer):
    """Review metadata for a worker's latest response to a request."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WorkerDocument
        fields = [
            'id',
            'status',
            'status_display',
            'original_filename',
            'file_size_bytes',
            'uploaded_at',
            'reviewed_at',
            'rejection_reason',
        ]
        read_only_fields = fields


class DocumentRequestSerializer(serializers.ModelSerializer):
    """A department request with status calculated for the current worker."""

    document_type_display = serializers.CharField(
        source='get_document_type_display',
        read_only=True,
    )
    department_name = serializers.CharField(source='department.name', read_only=True)
    status = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    latest_submission = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRequest
        fields = [
            'id',
            'document_type',
            'document_type_display',
            'department_name',
            'title',
            'instructions',
            'due_date',
            'status',
            'status_display',
            'is_overdue',
            'created_at',
            'updated_at',
            'latest_submission',
        ]
        read_only_fields = fields

    def _latest_submission(self, obj):
        prefetched = getattr(obj, 'current_user_submissions', None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None

        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return None
        return obj.submissions.filter(user=request.user).order_by('-uploaded_at').first()

    def get_status(self, obj):
        if obj.status == DocumentRequestStatus.CANCELLED:
            return 'cancelled'

        submission = self._latest_submission(obj)
        if submission is not None:
            if submission.status == DocumentStatus.VERIFIED:
                return 'completed'
            if submission.status == DocumentStatus.PENDING_REVIEW:
                return 'submitted'

        if obj.status == DocumentRequestStatus.CLOSED:
            return 'closed'
        return 'pending'

    def get_status_display(self, obj):
        return {
            'pending': 'Awaiting Upload',
            'submitted': 'Submitted for Review',
            'completed': 'Completed',
            'closed': 'Closed',
            'cancelled': 'Cancelled',
        }[self.get_status(obj)]

    def get_is_overdue(self, obj):
        return (
            obj.due_date is not None
            and obj.due_date < timezone.localdate()
            and self.get_status(obj) == 'pending'
        )

    def get_latest_submission(self, obj):
        submission = self._latest_submission(obj)
        if submission is None:
            return None
        return WorkerDocumentSerializer(submission).data


class DocumentSubmissionSerializer(serializers.Serializer):
    """Validate a phone capture before it is written to the review queue."""

    file = serializers.FileField(write_only=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )

    def validate_file(self, value):
        if value.size > MAX_DOCUMENT_BYTES:
            raise serializers.ValidationError('The document must be no larger than 10 MB.')

        extension = Path(value.name).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            raise serializers.ValidationError(
                'Upload a JPG, PNG, or PDF document.'
            )

        content_type = getattr(value, 'content_type', '')
        if content_type and content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
            raise serializers.ValidationError(
                'Upload a JPG, PNG, or PDF document.'
            )
        return value
