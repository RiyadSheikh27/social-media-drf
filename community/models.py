from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinLengthValidator
from django.db.models import F
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Community(models.Model):
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('restricted', 'Restricted'),
        ('private', 'Private'),
    ]
    name = models.CharField(
        max_length=50, 
        unique=True, 
        validators=[RegexValidator(
            r'^[A-Za-z0-9_-]+$', 
            'Name must be a single word (letters, numbers, _ or -'
        ), 
        MinLengthValidator(
            4, 'Name must be at least 4 character long'

        )],
        help_text='Unique single-word identifier (no spaces).'
    )
    description = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='communities/profiles/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='communities/covers/', blank=True, null=True)
    visibility = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='public')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_communities')
    updated_at = models.DateTimeField(auto_now=True)
    members_count = models.PositiveIntegerField(default=1)
    
    class Meta:
        ordering = ['-members_count', '-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['visibility']),
            models.Index(fields=['members_count']),
        ]

    def __str__(self):
        return f"{self.name} ({self.title})"
    
    def update_members_count(self):
        count = self.members.filter(is_approved=True).count()
        self.members_count = count
        self.save(update_fields=['members_count'])

class CommunityMember(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_membership')
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='members')
    is_admin = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'community')

    def __str__(self):
        return f"{self.user} → {self.community.name}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_approved = None
        if not is_new:
            old_approved = CommunityMember.objects.filter(pk=self.pk).values_list('is_approved', flat=True).first()

        super().save(*args, **kwargs)

        if is_new and self.is_approved:
            Community.objects.filter(pk=self.community.pk).update(members_count=F('members_count') + 1)
        elif old_approved is False and self.is_approved is True:
            Community.objects.filter(pk=self.community.pk).update(members_count=F('members_count') + 1)

    def delete(self, *args, **kwargs):
        """Decrease members_count when approved member leaves or removed."""
        if self.is_approved:
            Community.objects.filter(pk=self.community.pk).update(members_count=F('members_count') - 1)
        super().delete(*args, **kwargs)