# audio_processor/consumers.py

import json
import asyncio
import base64
import uuid
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async # Keep this import, it's used for group_send
from .tasks import process_audio_chunk, TEST_REDIS_CHANNEL # Import the test channel name
from django.conf import settings
import redis.asyncio as aioredis # Import async redis client

logger = logging.getLogger(__name__)

class AudioConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time audio streaming and transcription.
    Handles receiving audio chunks and sending back transcription updates and alerts.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.speaker_type = 'prospect' # Default speaker type for this channel
        self.audio_buffer = b""
        self.buffer_lock = asyncio.Lock()
        self.processing_task = None
        self.channel_layer = get_channel_layer()
        logger.info("AudioConsumer initialized.")
        logger.debug(f"AudioConsumer channel layer instance in __init__: {self.channel_layer}")
        self.redis_pubsub = None # For direct Redis pubsub
        self.redis_client = None # Initialize redis_client

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        logger.info(f"WebSocket connected for session: {self.session_id}")

        # Join session group (keep this for original Channels functionality)
        logger.debug(f"Attempting to add channel {self.channel_name} to group {self.session_id}")
        await self.channel_layer.group_add(
            self.session_id,
            self.channel_name
        )
        logger.debug(f"Successfully added channel {self.channel_name} to group {self.session_id}")
        await self.accept()

        # --- Self-test: Send a message from the consumer to its own group ---
        test_message = {
            'type': 'test_message_from_consumer',
            'message': 'Consumer self-test message received!'
        }
        logger.info(f"Consumer self-test: Sending message to group {self.session_id} from {self.channel_name}")
        await self.channel_layer.group_send(
            self.session_id,
            test_message
        )
        # -------------------------------------------------------------------------

        # --- Direct Redis SUBSCRIBE (Temporary Test) ---
        try:
            # Ping Redis directly to verify connectivity before subscribing
            redis_ping_client = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
            await redis_ping_client.ping()
            logger.info(f"Consumer: Successfully pinged Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            await redis_ping_client.close() # Close the ping client

            self.redis_client = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
            self.redis_pubsub = self.redis_client.pubsub()
            await self.redis_pubsub.subscribe(TEST_REDIS_CHANNEL)
            logger.info(f"Consumer: Successfully subscribed to direct Redis channel '{TEST_REDIS_CHANNEL}'.")
            # Start a listener task for this direct channel
            self.direct_redis_listener_task = asyncio.create_task(self.listen_to_direct_redis_channel())
        except Exception as e:
            logger.error(f"Consumer: Error subscribing to direct Redis channel: {e}")
            import traceback
            logger.error(f"Consumer: Traceback for direct Redis subscribe error: {traceback.format_exc()}")
        # -----------------------------------------------

        # Start a periodic task to process the audio buffer
        self.processing_task = asyncio.create_task(self.process_buffer_periodically())
        logger.info(f"Started periodic buffer processing for session: {self.session_id}")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for session: {self.session_id} with code: {close_code}")
        # Leave session group
        logger.debug(f"Attempting to discard channel {self.channel_name} from group {self.session_id}")
        await self.channel_layer.group_discard(
            self.session_id,
            self.channel_name
        )
        logger.debug(f"Successfully discarded channel {self.channel_name} from group {self.session_id}")

        if self.processing_task:
            self.processing_task.cancel()
            logger.info(f"Cancelled periodic buffer processing task for session: {self.session_id}")

        # Cancel direct Redis listener task
        if self.direct_redis_listener_task:
            self.direct_redis_listener_task.cancel()
            logger.info(f"Cancelled direct Redis listener task for session: {self.session_id}")
        if self.redis_pubsub:
            await self.redis_pubsub.unsubscribe(TEST_REDIS_CHANNEL)
            await self.redis_pubsub.close()
            logger.info(f"Unsubscribed and closed direct Redis pubsub for session: {self.session_id}")
        if self.redis_client:
            await self.redis_client.close()
            logger.info(f"Closed direct Redis client for session: {self.session_id}")


        # Process any remaining audio in the buffer
        await self.process_audio_buffer(force_send=True)
        logger.info(f"Final buffer processing initiated on disconnect for session: {self.session_id}")


    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            async with self.buffer_lock:
                self.audio_buffer += bytes_data
                logger.debug(f"Received {len(bytes_data)} bytes. Current buffer size: {len(self.audio_buffer)} for session: {self.session_id}")
        elif text_data:
            try:
                message = json.loads(text_data)
                if message.get('type') == 'set_speaker_type':
                    self.speaker_type = message.get('speaker_type', 'prospect')
                    logger.info(f"Session {self.session_id}: Speaker type set to {self.speaker_type}")
            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON text data: {text_data} for session: {self.session_id}")

    async def process_buffer_periodically(self):
        """
        Periodically processes the accumulated audio buffer.
        """
        while True:
            await asyncio.sleep(1)  # Process every 1 second (adjust as needed)
            await self.process_audio_buffer()

    async def process_audio_buffer(self, force_send=False):
        """
        Sends accumulated audio buffer to Celery for transcription.
        """
        async with self.buffer_lock:
            current_buffer_size = len(self.audio_buffer)
            logger.debug(f"Processing audio buffer for session {self.session_id}. Current size: {current_buffer_size}, Force send: {force_send}")

            if not self.audio_buffer and not force_send:
                logger.debug(f"Buffer empty and not forced send for session {self.session_id}.")
                return

            # Only send if buffer size is significant or forced (on disconnect)
            MIN_BUFFER_SIZE_FOR_SEND = 16000 * 2 * 1 # 32000 bytes for 1 second of 16-bit mono 16kHz audio

            if current_buffer_size < MIN_BUFFER_SIZE_FOR_SEND and not force_send:
                logger.debug(f"Buffer size ({current_buffer_size}) below threshold ({MIN_BUFFER_SIZE_FOR_SEND}) and not forced for session {self.session_id}.")
                return

            audio_data_b64 = base64.b64encode(self.audio_buffer).decode('utf-8')
            self.audio_buffer = b"" # Clear the buffer after sending
            logger.info(f"Sending {current_buffer_size} bytes (base64 encoded) to Celery for session {self.session_id}, speaker {self.speaker_type}")

            # Send to Celery task
            process_audio_chunk.delay(
                audio_data_b64,
                self.session_id,
                self.speaker_type
            )
            logger.debug(f"Celery task process_audio_chunk.delay() invoked for session {self.session_id}.")

    # --- Listener for direct Redis channel (NEW) ---
    async def listen_to_direct_redis_channel(self):
        """
        Listens for messages on the direct Redis channel and sends them to the client.
        """
        logger.info(f"Consumer: Starting listener for direct Redis channel '{TEST_REDIS_CHANNEL}' for session {self.session_id}.")
        while True:
            try:
                message = await self.redis_pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                if message:
                    logger.info(f"Consumer: Received direct Redis message on channel '{message['channel']}': {message['data']}")
                    try:
                        parsed_data = json.loads(message['data'])
                        # Send this direct message to the client
                        await self.send(text_data=json.dumps({
                            'type': 'direct_redis_message', # A new type for browser handling
                            'data': parsed_data
                        }))
                        logger.info(f"Consumer: Sent direct Redis message to client for session {self.session_id}.")
                    except json.JSONDecodeError:
                        logger.error(f"Consumer: Could not decode JSON from direct Redis message: {message['data']}")
                    except Exception as e:
                        logger.error(f"Consumer: Error sending direct Redis message to client: {e}")
                        import traceback
                        logger.error(f"Consumer: Traceback for direct Redis send error: {traceback.format_exc()}")
                await asyncio.sleep(0.01) # Small sleep to prevent busy-waiting
            except asyncio.CancelledError:
                logger.info(f"Consumer: Direct Redis listener task cancelled for session {self.session_id}.")
                break
            except Exception as e:
                logger.error(f"Consumer: Error in direct Redis listener: {e}")
                import traceback
                logger.error(f"Consumer: Traceback for direct Redis listener error: {traceback.format_exc()}")
                await asyncio.sleep(1) # Wait before retrying


    # Specific Handler for the self-test message
    async def test_message_from_consumer(self, event):
        """
        Handler for the self-test message received from the channel layer.
        """
        logger.info(f"AudioConsumer received 'test_message_from_consumer' event for session {self.session_id}. Full event: {event}")
        try:
            await self.send(text_data=json.dumps({
                'type': 'self_test_response',
                'data': event.get('message')
            }))
            logger.info(f"Consumer self-test: Sent response to client for session {self.session_id}")
        except Exception as e:
            logger.error(f"Consumer self-test: Error sending response to client: {e}")
            import traceback
            logger.error(f"Traceback for send_response error: {traceback.format_exc()}")


    # Receive messages from session group (transcriptions, alerts)
    async def send_transcription(self, event):
        """
        Handles sending transcription updates to the client.
        """
        logger.debug(f"AudioConsumer received 'send_transcription' event for session {self.session_id}. Event: {event}")
        message = event['message']
        try:
            await self.send(text_data=json.dumps({
                'type': 'transcription',
                'data': message
            }))
            logger.debug(f"Successfully sent transcription to client for session {self.session_id}: {message.get('text')[:50]}...")
        except Exception as e:
            logger.error(f"Error sending transcription to client for session {self.session_id}: {e}")
            import traceback
            logger.error(f"Traceback for send_transcription error: {traceback.format_exc()}")


    async def send_alert(self, event):
        """
        Handles sending keyword alerts to the client.
        """
        logger.debug(f"AudioConsumer received 'send_alert' event for session {self.session_id}. Event: {event}")
        message = event['message']
        try:
            await self.send(text_data=json.dumps({
                'type': 'alert',
                'data': message
            }))
            logger.info(f"Successfully sent alert to client for session {self.session_id}: {message.get('keyword')}")
        except Exception as e:
            logger.error(f"Error sending alert to client for session {self.session_id}: {e}")
            import traceback
            logger.error(f"Traceback for send_alert error: {traceback.format_exc()}")
