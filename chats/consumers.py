import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'chat_{self.room_id}'

        # Join room
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        # Leave room
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        user = self.scope['user']

        # Save to database
        await self.save_message(user, message)

        # Get username for broadcast
        username = user.username if user.is_authenticated else 'Anonymous'

        # Broadcast to everyone in room
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
            }
        )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
        }))

    @database_sync_to_async
    def save_message(self, user, content):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        room = Room.objects.get(id=self.room_id)

        # Convert lazy user object to actual User instance
        if user.is_authenticated:
            actual_user = User.objects.get(id=user.id)
        else:
            return None

        return Message.objects.create(
            room=room,
            sender=actual_user,
            content=content
        )