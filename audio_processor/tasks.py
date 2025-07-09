# audio_processor/tasks.py

import os
import io
import base64
import logging
from celery import shared_task
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async # Ensure both are imported
from openai import OpenAI
import httpx
from django.utils import timezone

logger = logging.getLogger(__name__)

# Retrieve Organization ID and Project ID from environment variables
OPENAI_ORGANIZATION_ID = os.environ.get('OPENAI_ORGANIZATION_ID')
OPENAI_PROJECT_ID = os.environ.get('OPENAI_PROJECT_ID')


@shared_task
def process_audio_file(file_path, session_id, speaker_type):
    """
    Celery task to transcribe an audio file and process the transcription.
    Used for file uploads.
    This task remains synchronous as it primarily deals with file I/O and
    then enqueues an asynchronous task.
    """
    logger.info(f"Task process_audio_file started for session {session_id}, file: {file_path}")
    openai_client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        organization=OPENAI_ORGANIZATION_ID,
        project=OPENAI_PROJECT_ID
    )
    try:
        with open(file_path, "rb") as audio_file:
            transcription_result = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", audio_file, "audio/wav")
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
    This task remains synchronous as it primarily deals with OpenAI API call
    and then enqueues an asynchronous task.
    """
    logger.info(f"Task process_audio_chunk started for session {session_id}, speaker {speaker_type}. Audio data length: {len(audio_data_b64)} bytes (base64 encoded)")
    openai_client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        organization=OPENAI_ORGANIZATION_ID,
        project=OPENAI_PROJECT_ID
    )
    try:
        audio_data = base64.b64decode(audio_data_b64)
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.webm" # Explicitly set mime type for webm
        transcription_result = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        transcribed_text = transcription_result.text
        logger.info(f"Chunk transcription for session {session_id}: {transcribed_text[:100]}...")
        process_transcription.delay(transcribed_text, session_id, speaker_type)
    except Exception as e:
        logger.error(f"Error transcribing audio chunk for session {session_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())

@shared_task(bind=True) # Use bind=True to access self for async_to_sync
async def process_transcription(self, transcribed_text, session_id, speaker_type):
    """
    Celery task to process transcribed text: save, detect keywords, and send alerts.
    This task is now asynchronous.
    """
    logger.info(f"Task process_transcription started for session {session_id}, speaker {speaker_type}. Text: {transcribed_text[:50]}...")
    channel_layer = get_channel_layer()

    # Import models *inside* the task function
    from .models import Transcription, Keyword

    current_timestamp = timezone.now() # Get current timestamp

    # Save transcription (optional, for historical records)
    try:
        # Wrap synchronous ORM call with sync_to_async
        await sync_to_async(Transcription.objects.create)(
            session_id=session_id,
            speaker_type=speaker_type,
            text=transcribed_text,
            timestamp=current_timestamp # Pass timestamp
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
        # Await group_send directly as we are in an async task
        await channel_layer.group_send(
            session_id,
            {
                'type': 'send_transcription',
                'message': {
                    'text': transcribed_text,
                    'speaker_type': speaker_type,
                    'timestamp': str(current_timestamp) # Use actual timestamp
                }
            }
        )
        logger.debug(f"Sent transcription via channel layer for session {session_id}")
    except Exception as e:
        logger.error(f"Error sending transcription via channel layer for session {session_id}: {e}")
        import traceback
        logger.error(f"Traceback for channel layer send error: {traceback.format_exc()}")


    # Keyword detection and alert
    if speaker_type == 'prospect':
        # Fetch keywords using sync_to_async
        keywords_queryset = await sync_to_async(Keyword.objects.filter)(is_active=True)
        keywords = await sync_to_async(list)(keywords_queryset.values('word', 'talking_point'))

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
                    # Await group_send directly as we are in an async task
                    await channel_layer.group_send(
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


@shared_task(bind=True) # Keep bind=True if you need 'self', otherwise remove it
def test_send_to_channel_layer(self, test_session_id, message_text): # Changed back to def (synchronous)
    """
    A simple test task to send a message to a Channels group.
    This task is now synchronous.
    """
    logger.info(f"Test task test_send_to_channel_layer received for session {test_session_id}.")
    
    try:
        channel_layer = get_channel_layer()
        logger.debug(f"Test task: Successfully obtained channel layer: {channel_layer}")
    except Exception as e:
        logger.error(f"Test task: Error obtaining channel layer: {e}")
        import traceback
        logger.error(f"Test task: Traceback for get_channel_layer error: {traceback.format_exc()}")
        return # Stop if channel layer cannot be obtained

    # New print statement for debugging
    print(f"DEBUG TEST TASK: Attempting to publish to Redis group: 'asgi__group__{test_session_id}' with message: '{message_text}'")
    try:
        logger.debug(f"Test task: Attempting async_to_sync(channel_layer.group_send)...")
        async_to_sync(channel_layer.group_send)(
            test_session_id, # This is the group name, e.g., "test_session_browser_connect"
            {
                'type': 'send_transcription',
                'message': {
                    'text': message_text,
                    'speaker_type': 'test_speaker',
                    'timestamp': 'test_time'
                }
            }
        )
        logger.info(f"Test task: Successfully sent '{message_text}' to group '{test_session_id}'.")
    except Exception as e:
        logger.error(f"Test task: Error sending message to channel layer for session {test_session_id}: {e}")
        import traceback
        logger.error(f"Traceback for channel layer send error: {traceback.format_exc()}")

