# backend/asgi.py

import os
import logging
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack # Keep AuthMiddlewareStack
import audio_processor.routing # Revert to importing your main routing

logger = logging.getLogger(__name__) # Initialize logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# --- Removed early diagnostic check and direct Redis ping ---
# The previous logs confirmed connectivity, so we remove the test code.

django_asgi_app = get_asgi_application()
logger.info("Django ASGI application loaded.") # Added log

application = ProtocolTypeRouter({
    "http": django_asgi_app, # Use the loaded Django ASGI app for HTTP
    # WebSocket chat handler
    "websocket": AuthMiddlewareStack( # Re-enable AuthMiddlewareStack
        URLRouter(
            audio_processor.routing.websocket_urlpatterns # Use your main WebSocket URL patterns
        )
    ),
})

logger.info("ASGI ProtocolTypeRouter configured.") # Added log
