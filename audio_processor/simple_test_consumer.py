# audio_processor/simple_test_consumer.py

import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class SimpleTestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info("SimpleTestConsumer: WebSocket connected!")
        await self.accept()
        await self.send(text_data="Hello from SimpleTestConsumer!")
        logger.info("SimpleTestConsumer: Sent welcome message.")

    async def disconnect(self, close_code):
        logger.info(f"SimpleTestConsumer: WebSocket disconnected with code {close_code}")

    async def receive(self, text_data):
        logger.info(f"SimpleTestConsumer: Received message: {text_data}")
        await self.send(text_data=f"Echo: {text_data}")
