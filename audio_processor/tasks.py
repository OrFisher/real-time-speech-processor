# audio_processor/tasks.py

import os
import io
import base64
import logging
from celery import shared_task
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async
from openai import OpenAI
import httpx
from django.utils import timezone
import redis # Import redis client
import json # Import json for direct Redis publish

logger = logging.getLogger(__name__)

# Retrieve Organization ID and Project ID from environment variables
OPENAI_ORGANIZATION_ID = os.environ.get('OPENAI_ORGANIZATION_ID')
OPENAI_PROJECT_ID = os.environ.get('OPENAI_PROJECT_ID')


@shared_task
def process_audio_file(file_path, session_id, speaker_type):
    """
    Celery task to transcribe an audio file and process the transcription.
    Used for file uploads.
    """
    logger.info(f"Task process_audio_file started for session {session_id}, file: {file_path}")
    openai_client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        organization=OPENAI_ORGANIZATION_ID,
        project=OPENAI_PROJECT_ID
    )
    try:
        with open(file_path, "rb") as audio_file:
            # Pass file as a tuple (filename, file_object, mime_type)
            transcription_result = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", audio_file, "audio/wav") # Assuming WAV for uploaded files
            )
            transcribed_text = transcription_result.text
            logger.info(f"File transcription for session {session_id}: {transcribed_text[:100]}...")
            process_transcription.delay(transcribed_text, session_id, speaker_type)
    except Exception as e:
        logger.error(f"Error transcribing audio file {file_path}: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Removed temporary file: {file_path}")


@shared_task
def process_audio_chunk(audio_data_b64, session_id, speaker_type):
    """
    Celery task to transcribe an audio chunk (from WebSocket) and process the transcription.
    """
    logger.info(f"Task process_audio_chunk started for session {session_id}, speaker {speaker_type}. Audio data length: {len(audio_data_b64)} bytes (base64 encoded)")
    openai_client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        organization=OPENAI_ORGANIZATION_ID,
        project=OPENAI_PROJECT_ID
    )
    try:
        audio_data = base64.b64decode(audio_data_b64)
        # We no longer need io.BytesIO(audio_data) if we pass the raw bytes directly in the tuple.
        # The filename and mime type are explicitly provided in the tuple.
        transcription_result = openai_client.audio.transcriptions.create(
            model="whisper-1",
            # Pass the raw bytes along with the filename and mime type in a tuple
            file=("audio.webm", audio_data, "audio/webm") # CHANGED THIS LINE
        )
        transcribed_text = transcription_result.text
        logger.info(f"Chunk transcription for session {session_id}: {transcribed_text[:100]}...")
        process_transcription.delay(transcribed_text, session_id, speaker_type)
    except Exception as e:
        logger.error(f"Error transcribing audio chunk for session {session_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())

@shared_task(bind=True)
def process_transcription(self, transcribed_text, session_id, speaker_type):
    """
    Celery task to process transcribed text: save, detect keywords, and send alerts.
    This task is synchronous.
    """
    logger.info(f"Task process_transcription started for session {session_id}, speaker {speaker_type}. Text: {transcribed_text[:50]}...")
    channel_layer = get_channel_layer()

    # Import models *inside* the task function
    from .models import Transcription, Keyword

    current_timestamp = timezone.now()

    # Save transcription (optional, for historical records)
    try:
        Transcription.objects.create(
            session_id=session_id,
            speaker_type=speaker_type,
            text=transcribed_text,
            timestamp=current_timestamp
        )
        logger.debug(f"Saved transcription for session {session_id}")
    except Exception as e:
        logger.error(f"Error saving transcription for session {session_id}: {e}")
        import traceback
        logger.error(f"Traceback for save error: {traceback.format_exc()}")


    # Send real-time transcription to frontend
    print(f"DEBUG: About to call group_send for session {session_id} with text: {transcribed_text[:30]}...")
    try:
        logger.debug(f"Attempting to send transcription to channel layer for session {session_id}...")
        async_to_sync(channel_layer.group_send)(
            session_id,
            {
                'type': 'send_transcription',
                'message': {
                    'text': transcribed_text,
                    'speaker_type': speaker_type,
                    'timestamp': str(current_timestamp)
                }
            }
        )
        logger.info(f"Sent transcription via channel layer for session {session_id}")
    except Exception as e:
        logger.error(f"Error sending transcription via channel layer for session {session_id}: {e}")
        import traceback
        logger.error(f"Traceback for channel layer send error: {traceback.format_exc()}")


    # Keyword detection and alert
    if speaker_type == 'prospect':
        keywords = Keyword.objects.filter(is_active=True).values('word', 'talking_point')
        detected_keywords = []

        for keyword_obj in keywords:
            word = keyword_obj['word'].lower()
            talking_point = keyword_obj['talking_point']
            if word in transcribed_text.lower():
                detected_keywords.append({
                    'keyword': keyword_obj['word'],
                    'talking_point': talking_point,
                    'transcribed_text': transcribed_text
                })
                logger.info(f"Detected keyword '{word}' from prospect in session {session_id}")

        if detected_keywords:
            print(f"DEBUG: About to call group_send for alerts for session {session_id}...")
            try:
                logger.debug(f"Attempting to send {len(detected_keywords)} alerts to channel layer for session {session_id}...")
                for detected in detected_keywords:
                    async_to_sync(channel_layer.group_send)(
                        session_id,
                        {
                            'type': 'send_alert',
                            'message': {
                                'keyword': detected['keyword'],
                                'talking_point': detected['talking_point'],
                                'full_text': detected['transcribed_text'],
                                'speaker_type': speaker_type
                            }
                        }
                    )
                logger.debug(f"Sent {len(detected_keywords)} alerts via channel layer for session {session_id}")
            except Exception as e:
                logger.error(f"Error sending alert via channel layer for session {session_id}: {e}")
                import traceback
                logger.error(f"Traceback for alert channel layer send error: {traceback.format_exc()}")

# Define a specific channel name for direct testing
TEST_REDIS_CHANNEL = "my_direct_test_channel"

@shared_task(bind=True)
def test_send_to_channel_layer(self, test_session_id, message_text):
    """
    A simple test task to send a message to a Channels group.
    This task is synchronous.
    """
    logger.info(f"Test task test_send_to_channel_layer received for session {test_session_id}.")

    # --- Direct Redis PUBLISH (Temporary Test) ---
    try:
        # Connect directly to Redis using settings
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        test_payload = json.dumps({
            'type': 'direct_redis_test_message', # A new type for direct test
            'session_id': test_session_id,
            'message': message_text,
            'timestamp': str(timezone.now())
        })
        r.publish(TEST_REDIS_CHANNEL, test_payload)
        logger.info(f"Test task: Directly PUBLISHED message to Redis channel '{TEST_REDIS_CHANNEL}'. Payload: {test_payload[:100]}...")
    except Exception as e:
        logger.error(f"Test task: Error directly publishing to Redis: {e}")
        import traceback
        logger.error(f"Test task: Traceback for direct Redis publish error: {traceback.format_exc()}")
    # ---------------------------------------------

    # Original Channels group_send (keep for comparison)
    try:
        channel_layer = get_channel_layer()
        logger.debug(f"Test task: Successfully obtained channel layer: {channel_layer}")
        logger.debug(f"Test task: Attempting async_to_sync(channel_layer.group_send)...")
        async_to_sync(channel_layer.group_send)(
            test_session_id,
            {
                'type': 'send_transcription',
                'message': {
                    'text': message_text,
                    'speaker_type': 'test_speaker',
                    'timestamp': str(timezone.now())
                }
            }
        )
        logger.info(f"Test task: Successfully sent '{message_text}' to group '{test_session_id}' via Channels layer.")
    except Exception as e:
        logger.error(f"Error sending message to channel layer for session {test_session_id}: {e}")
        import traceback
        logger.error(f"Traceback for channel layer send error: {traceback.format_exc()}")
