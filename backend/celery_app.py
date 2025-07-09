# backend/celery_app.py

import os
from celery import Celery
from django.conf import settings # Import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Explicitly import tasks from audio_processor.tasks
# This can sometimes help with task discovery issues on Windows
# from audio_processor.tasks import test_send_to_channel_layer, process_audio_chunk, process_audio_file, process_transcription

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
