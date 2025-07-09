# backend/urls.py

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('audio_processor.urls')),
    path('', TemplateView.as_view(template_name='index.html')),
]

# ONLY add this in development/debug mode to serve static files
if settings.DEBUG:
    # In DEBUG mode, Django's staticfiles app serves files from STATICFILES_DIRS.
    # We explicitly point the document_root to the frontend's static directory.
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    # If you later add MEDIA_URL for user-uploaded files, you would also add:
    # urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
