"""API and lifecycle tests for department-wide document requests."""

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organisations.models import Department, Organization

from .models import (
    DocumentRequest,
    DocumentRequestStatus,
    DocumentStatus,
    DocumentType,
    WorkerDocument,
)


class DocumentRequestApiTests(APITestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()

        organization = Organization.objects.create(name='Example Organization')
        self.department = Department.objects.create(
            name='Operations',
            organization=organization,
        )
        self.other_department = Department.objects.create(
            name='Finance',
            organization=organization,
        )
        self.worker = User.objects.create_user(
            email='worker@example.com',
            password='StrongPass123!',
            first_name='Ada',
            department=self.department,
            is_approved=True,
            must_change_password=False,
        )
        self.colleague = User.objects.create_user(
            email='colleague@example.com',
            password='StrongPass123!',
            department=self.department,
        )
        self.outside_worker = User.objects.create_user(
            email='outside@example.com',
            password='StrongPass123!',
            department=self.other_department,
        )
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='StrongPass123!',
        )
        self.document_request = DocumentRequest.objects.create(
            department=self.department,
            created_by=self.admin_user,
            document_type=DocumentType.ID_CARD,
            title='Updated staff ID',
            instructions='Photograph both the name and expiry date clearly.',
        )
        self.other_request = DocumentRequest.objects.create(
            department=self.other_department,
            created_by=self.admin_user,
            title='Finance declaration',
        )
        self.client.force_authenticate(self.worker)

    def tearDown(self):
        self.settings_override.disable()
        self.media_directory.cleanup()

    def test_workers_list_requests_for_their_department(self):
        response = self.client.get(reverse('documents:request-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Updated staff ID')
        self.assertEqual(response.data['results'][0]['department_name'], 'Operations')
        self.assertEqual(response.data['results'][0]['status'], 'pending')

        self.client.force_authenticate(self.colleague)
        colleague_response = self.client.get(reverse('documents:request-list'))
        self.assertEqual(colleague_response.data['count'], 1)
        self.assertEqual(colleague_response.data['results'][0]['status'], 'pending')

    def test_admin_can_render_department_request_form(self):
        self.client.force_authenticate(user=None)
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin:documents_documentrequest_add'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'Add document request')
        self.assertContains(response, 'Department')

    def test_each_department_worker_can_submit_independently(self):
        first_response = self._submit_as(self.worker, 'worker-id.jpg')
        second_response = self._submit_as(self.colleague, 'colleague-id.jpg')

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first_response.data['status'], 'submitted')
        self.assertEqual(second_response.data['status'], 'submitted')
        self.assertEqual(
            WorkerDocument.objects.filter(request=self.document_request).count(),
            2,
        )
        self.document_request.refresh_from_db()
        self.assertEqual(
            self.document_request.status,
            DocumentRequestStatus.ACTIVE,
        )

    def test_worker_cannot_submit_another_departments_request(self):
        self.client.force_authenticate(self.worker)
        upload = SimpleUploadedFile(
            'staff-id.jpg',
            b'camera-image-bytes',
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('documents:request-submit', args=[self.other_request.pk]),
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            WorkerDocument.objects.filter(
                request=self.other_request,
                user=self.worker,
            ).exists()
        )

    def test_review_outcome_changes_only_the_current_workers_status(self):
        submission = WorkerDocument.objects.create(
            request=self.document_request,
            user=self.worker,
            document_type=DocumentType.ID_CARD,
            title=self.document_request.title,
            file=SimpleUploadedFile('id.jpg', b'image', content_type='image/jpeg'),
        )

        submitted = self.client.get(reverse('documents:request-list'))
        self.assertEqual(submitted.data['results'][0]['status'], 'submitted')

        submission.reject(self.admin_user, 'The expiry date is not visible.')
        rejected = self.client.get(reverse('documents:request-list'))
        self.assertEqual(rejected.data['results'][0]['status'], 'pending')
        self.assertEqual(
            rejected.data['results'][0]['latest_submission']['rejection_reason'],
            'The expiry date is not visible.',
        )

        submission.verify(self.admin_user)
        completed = self.client.get(reverse('documents:request-list'))
        self.assertEqual(completed.data['results'][0]['status'], 'completed')

        self.client.force_authenticate(self.colleague)
        colleague = self.client.get(reverse('documents:request-list'))
        self.assertEqual(colleague.data['results'][0]['status'], 'pending')

    def test_deleting_submission_removes_its_private_storage_object(self):
        submission = WorkerDocument.objects.create(
            request=self.document_request,
            user=self.worker,
            document_type=DocumentType.ID_CARD,
            title=self.document_request.title,
            file=SimpleUploadedFile('id.jpg', b'image', content_type='image/jpeg'),
        )
        stored_path = Path(submission.file.path)
        self.assertTrue(stored_path.exists())

        submission.delete()

        self.assertFalse(stored_path.exists())

    def _submit_as(self, user, filename):
        self.client.force_authenticate(user)
        upload = SimpleUploadedFile(
            filename,
            b'camera-image-bytes',
            content_type='image/jpeg',
        )
        return self.client.post(
            reverse('documents:request-submit', args=[self.document_request.pk]),
            {'file': upload, 'description': 'Captured in the mobile app.'},
            format='multipart',
        )
