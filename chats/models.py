from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

""" Chat Models """
class Room(models.Model):
    """ Room model for Chat """
    name = models.CharField(max_length=255, null=True, blank=True)
    participants = models.ManyToManyField(User, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    """ Message model for Chat """
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

""" End of Chat Models """