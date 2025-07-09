# audio_processor/urls.py

from django.urls import path
from .views import AudioUploadView, KeywordListCreateView, KeywordRetrieveUpdateDestroyView

urlpatterns = [
    path('upload-audio/', AudioUploadView.as_view(), name='upload_audio'),
    path('keywords/', KeywordListCreateView.as_view(), name='keyword_list_create'),
    path('keywords/<int:pk>/', KeywordRetrieveUpdateDestroyView.as_view(), name='keyword_retrieve_update_destroy'),
]
