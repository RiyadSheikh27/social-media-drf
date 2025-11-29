from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinLengthValidator
from django.db.models import F
from django.conf import settings
from post.models import *

User = settings.AUTH_USER_MODEL

class Community(models.Model):
    """Community model for creating and managing communities"""
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('restricted', 'Restricted'),
        ('private', 'Private'),
    ]
    
    name = models.CharField(
        max_length=50, 
        unique=True, 
        validators=[
            RegexValidator(
                r'^[A-Za-z0-9_-]+$', 
                'Name must be a single word (letters, numbers, _ or -)'
            ), 
            MinLengthValidator(4, 'Name must be at least 4 characters long')
        ],
        help_text='Unique single-word identifier (no spaces).'
    )
    title = models.CharField(max_length=100, help_text='Display name for the community')
    description = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='communities/profiles/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='communities/covers/', blank=True, null=True)
    visibility = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='public')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_communities')
    updated_at = models.DateTimeField(auto_now=True)
    members_count = models.PositiveIntegerField(default=1)
    posts_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-members_count', '-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['visibility']),
            models.Index(fields=['-members_count']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name_plural = 'Communities'

    def __str__(self):
        return f"{self.name} ({self.title})"
    
    def update_members_count(self):
        """Update the cached members count"""
        count = self.members.filter(is_approved=True).count()
        self.members_count = count
        self.save(update_fields=['members_count'])
    
    def update_posts_count(self):
        """Update the cached posts count"""
        count = Post.objects.filter(community=self, status='approved').count()
        self.posts_count = count
        self.save(update_fields=['posts_count'])

class CommunityMember(models.Model):
    """Membership relationship between users and communities"""
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_memberships')
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    is_approved = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    # Legacy fields for backward compatibility
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_moderator(self):
        return self.role in ['moderator', 'admin']

    class Meta:
        unique_together = ('user', 'community')
        indexes = [
            models.Index(fields=['community', '-joined_at']),
            models.Index(fields=['user', '-joined_at']),
            models.Index(fields=['community', 'is_approved']),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.community.name} ({self.role})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_approved = None
        
        if not is_new:
            old_approved = CommunityMember.objects.filter(pk=self.pk).values_list('is_approved', flat=True).first()
        super().save(*args, **kwargs)

        # Auto-approve public communities
        if is_new and self.community.visibility == 'public':
            self.is_approved = True
            super().save(update_fields=['is_approved'])

        # Update members count
        if is_new and self.is_approved:
            Community.objects.filter(pk=self.community.pk).update(members_count=F('members_count') + 1)
        elif old_approved is False and self.is_approved is True:
            Community.objects.filter(pk=self.community.pk).update(members_count=F('members_count') + 1)

    def delete(self, *args, **kwargs):
        """Decrease members_count when approved member leaves"""
        if self.is_approved:
            Community.objects.filter(pk=self.community.pk).update(members_count=F('members_count') - 1)
        super().delete(*args, **kwargs)

class CommunityRule(models.Model):
    """Rules for community behavior"""
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='rules')
    title = models.CharField(max_length=100)
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['community', 'order']),
        ]
    
    def __str__(self):
        return f"{self.community.name} - Rule {self.order}: {self.title}"
    
class CommunityInvitation(models.Model):
    """Invitations to join private/restricted communities"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='invitations')
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_community_invitations')
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_community_invitations')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('community', 'invitee')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invitee', 'status', '-created_at']),
            models.Index(fields=['community', 'status']),
        ]
    
    def __str__(self):
        return f"{self.inviter.username} invited {self.invitee.username} to {self.community.name}"


class CommunityJoinRequest(models.Model):
    """Join requests for restricted/private communities"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_join_requests')
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='join_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, help_text='Why do you want to join?')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_join_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('user', 'community')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['community', 'status', '-created_at']),
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} wants to join {self.community.name} - {self.status}"