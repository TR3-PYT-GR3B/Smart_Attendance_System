"""Document routes, mounted at ``/api/documents/``."""

from django.urls import path

from .views import DocumentRequestListView, SubmitDocumentRequestView

app_name = 'documents'

urlpatterns = [
    path('requests/', DocumentRequestListView.as_view(), name='request-list'),
    path(
        'requests/<int:pk>/submit/',
        SubmitDocumentRequestView.as_view(),
        name='request-submit',
    ),
]
