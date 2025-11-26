from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Room, Message
from .serializers import RoomSerializer, MessageSerializer

""" Viewset for Chat """
class RoomViewSet(viewsets.ModelViewSet):
    """ Viewset for Room """
    queryset = Room.objects.all()
    serializer_class = RoomSerializer

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        room = self.get_object()
        messages = room.messages.all()
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)