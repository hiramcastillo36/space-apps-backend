"""
WebSocket consumer para chat en tiempo real con agentes
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation, Message
from .services import WeatherAgentService


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Recibe mensaje del WebSocket"""
        data = json.loads(text_data)
        message = data.get('message', '')

        if not message:
            await self.send(text_data=json.dumps({
                'error': 'Mensaje vacío'
            }))
            return

        try:
            # Obtener conversación
            conversation = await self.get_conversation(self.conversation_id)

            # Procesar mensaje con el agente (incluye function calling)
            response = await self.process_message(conversation, message)

            # Enviar respuesta del agente
            await self.send(text_data=json.dumps({
                'type': 'agent_message',
                'message': response
            }))

        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e)
            }))

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        """Obtiene la conversación de la base de datos"""
        return Conversation.objects.get(id=conversation_id)

    @database_sync_to_async
    def process_message(self, conversation, message):
        """Procesa el mensaje con el servicio del agente"""
        return WeatherAgentService.process_user_message(conversation, message)
