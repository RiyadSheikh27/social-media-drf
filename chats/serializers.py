from rest_framework import serializers 
from .models import Room, Message

""" Serializers for Chat """
class MessageSerializer(serializers.ModelSerializer):
    """ Serializer for Message """
    sender = serializers.StringRelatedField()
    class Meta:
        model = Message
        fields = ['id', 'sender', 'content', 'created_at']

class RoomSerializer(serializers.ModelSerializer):
    """ Serializer for Room """
    class Meta:
        model = Room
        fields = ['id', 'name', 'created_at']

""" End of Serializers for Chat """