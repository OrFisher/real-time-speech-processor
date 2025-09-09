# trigger_test_task.py

import os
import sys
from django.conf import settings
from django.apps import apps

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# This is crucial for Django apps to be ready when importing tasks
# Ensure Django is set up before importing any models or tasks that rely on it
if not apps.ready:
    import django
    django.setup()

# Import your Celery task
from audio_processor.tasks import test_send_to_channel_layer

# Define a session ID for testing.
# This should match the session ID you're using in your frontend for the WebSocket connection.
# For a quick test, you can hardcode it or make it dynamic.
# If you start recording in the browser, check the console for the generated session ID.
# For this test, let's use a fixed one you can manually enter in the browser's console
# or ensure your browser's session ID matches this.
# Example: If your browser's session ID is 'session_abc123', use that here.
test_session_id = "1pxqzmy4uhi5ky96uqyvfj" # <--- IMPORTANT: Change this to your actual session_id if needed

message_to_send = "This is a direct Redis test message from Celery!"

print(f"Attempting to send test message to session: {test_session_id}")
# Call the Celery task using .delay()
test_send_to_channel_layer.delay(test_session_id, message_to_send)
print("Celery test task dispatched. Check your Daphne and browser consoles.")

