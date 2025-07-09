# audio_processor/routing.py

from django.urls import re_path
from . import consumers # Import your main consumers module
import logging # Import logging

logger = logging.getLogger(__name__) # Initialize logger

websocket_urlpatterns = [
    re_path(r'ws/audio/(?P<session_id>\w+)/$', consumers.AudioConsumer.as_asgi()), # Original audio route
]
logger.info(f"WebSocket URL patterns loaded: {websocket_urlpatterns}") # Added log
