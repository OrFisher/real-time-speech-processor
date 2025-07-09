# audio_processor/views.py

import uuid
import os
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics # Import generics for simple API views
from .tasks import process_audio_file
from .models import Keyword
from .serializers import KeywordSerializer # Import the new serializer
import logging

logger = logging.getLogger(__name__)

class AudioUploadView(APIView):
    """
    REST endpoint to receive audio file uploads.
    """
    def post(self, request, *args, **kwargs):
        audio_file = request.FILES.get('audio')
        session_id = request.data.get('session_id', str(uuid.uuid4()))
        speaker_type = request.data.get('speaker_type', 'prospect') # Default to prospect

        if not audio_file:
            return Response({"error": "No audio file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a temporary directory if it doesn't exist
        temp_dir = os.path.join(settings.BASE_DIR, 'temp_audio')
        os.makedirs(temp_dir, exist_ok=True)

        # Save the audio file temporarily
        file_extension = os.path.splitext(audio_file.name)[1]
        temp_file_name = f"{session_id}_{uuid.uuid4()}{file_extension}"
        temp_file_path = os.path.join(temp_dir, temp_file_name)

        try:
            with open(temp_file_path, 'wb+') as destination:
                for chunk in audio_file.chunks():
                    destination.write(chunk)

            # Enqueue the task to process the audio file
            process_audio_file.delay(temp_file_path, session_id, speaker_type)

            return Response(
                {"message": "Audio file received and queued for processing.", "session_id": session_id},
                status=status.HTTP_202_ACCEPTED
            )
        except Exception as e:
            logger.error(f"Error processing audio file upload: {e}")
            return Response({"error": "Failed to process audio file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class KeywordListCreateView(generics.ListCreateAPIView):
    """
    API endpoint to list all keywords or create a new keyword.
    """
    queryset = Keyword.objects.all()
    serializer_class = KeywordSerializer

class KeywordRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint to retrieve, update, or delete a specific keyword.
    """
    queryset = Keyword.objects.all()
    serializer_class = KeywordSerializer
    lookup_field = 'pk' # Use primary key for lookup
