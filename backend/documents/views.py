"""Authenticated worker APIs for office-issued document requests."""

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    DocumentRequest,
    DocumentRequestStatus,
    DocumentStatus,
    WorkerDocument,
)
from .serializers import DocumentRequestSerializer, DocumentSubmissionSerializer


class DocumentRequestListView(generics.ListAPIView):
    """List requests issued to the caller's current department."""

    serializer_class = DocumentRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.department_id is None:
            return DocumentRequest.objects.none()

        return (
            DocumentRequest.objects.filter(department_id=user.department_id)
            .select_related('department')
            .prefetch_related(
                Prefetch(
                    'submissions',
                    queryset=WorkerDocument.objects.filter(user=user).order_by(
                        '-uploaded_at'
                    ),
                    to_attr='current_user_submissions',
                )
            )
            .order_by('status', 'due_date', '-created_at')
        )


class SubmitDocumentRequestView(APIView):
    """Attach a phone capture to one pending request and queue it for review."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = DocumentSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.department_id is None:
            return Response(
                {'detail': 'Your account is not assigned to a department.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            document_request = get_object_or_404(
                DocumentRequest.objects.select_for_update(),
                pk=pk,
                department_id=request.user.department_id,
            )
            if document_request.status == DocumentRequestStatus.CANCELLED:
                return Response(
                    {'detail': 'This document request was cancelled.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if document_request.status == DocumentRequestStatus.CLOSED:
                return Response(
                    {'detail': 'This department document request is closed.'},
                    status=status.HTTP_409_CONFLICT,
                )

            latest_submission = (
                document_request.submissions.filter(user=request.user)
                .order_by('-uploaded_at')
                .first()
            )
            if (
                latest_submission is not None
                and latest_submission.status == DocumentStatus.PENDING_REVIEW
            ):
                return Response(
                    {'detail': 'This document is already awaiting review.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if (
                latest_submission is not None
                and latest_submission.status == DocumentStatus.VERIFIED
            ):
                return Response(
                    {'detail': 'You have already completed this document request.'},
                    status=status.HTTP_409_CONFLICT,
                )

            upload = serializer.validated_data['file']
            WorkerDocument.objects.create(
                request=document_request,
                user=request.user,
                document_type=document_request.document_type,
                title=document_request.title,
                description=serializer.validated_data.get('description', ''),
                file=upload,
                original_filename=upload.name,
                file_size_bytes=upload.size,
                status=DocumentStatus.PENDING_REVIEW,
            )

        return Response(
            DocumentRequestSerializer(
                document_request,
                context={'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )
