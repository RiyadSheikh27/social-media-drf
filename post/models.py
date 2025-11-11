from django.db import models
from django.conf import settings
from ckeditor.fields import RichTextField

class Post(models.Model):
    POST_TYPE_CHOICES = [
        ('text', 'Text'),
        ('media', 'Image/Video'),
        ('link', 'Link'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=255)
    post_type = models.CharField(max_length=10, choices=POST_TYPE_CHOICES)
    content = RichTextField(blank=True, null=True)
    media_file = models.JSONField(default=list, blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['user', '-created_at']),
        ]
        # speeds up queries like,
        # Post.objects.filter(status='approved').order_by('-created_at')
        
    def likes_count(self):
        return self.likes.count()
    # Creates a reverse relationship from Post back to that model --> Like Model e 
    # related name hisebe like use kora ache

    def comments_count(self):
        return self.comments.count()

    def shares_count(self):
        return self.shares.count()
    
    def engagement_score(self):
        return (self.likes.count() * 1) + (self.comments.count() * 2) + (self.shares.count() * 3)

    def __str__(self):
        return f"{self.title} by {self.user.username}"
    

class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} likes {self.post.title}"


class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"

class Share(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='shares')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} shared {self.post.title}"
    

class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='following'
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='followers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        indexes = [
            models.Index(fields=['follower', '-created_at']),
            models.Index(fields=['following', '-created_at']),
        ]

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"
    
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('share', 'Share'),
        ('follow', 'Follow'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_notifications'
    )
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at', 'is_read']),
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender.username} {self.notification_type} - {self.recipient.username}"

class PostView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='post_views')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='views')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['post', '-viewed_at']),
        ]

    def __str__(self):
        return f"{self.user.username} viewed {self.post.title}"