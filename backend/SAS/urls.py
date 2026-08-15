"""
Root URL configuration.

The API is versionless for now and grouped by app under ``/api/``. Each app owns
its own ``urls.py``, so adding the remaining modules (leave, documents,
analytics, admin queues) is a matter of adding one ``include()`` here.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False), name='home'),
    path('admin/', admin.site.urls),

    # ── Worker-facing API ──
    path('api/auth/', include('accounts.urls')),
    path('api/enrollment/', include('enrollment.urls')),
    path('api/attendance/', include('attendance.urls')),
    path('api/leave/', include('leave.urls')),
    path('api/documents/', include('documents.urls')),
]

# Serve uploaded media through Django in development only. In production this
# is the web server's job, and documents and face media should sit in encrypted
# object storage rather than on the application server's disk.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
