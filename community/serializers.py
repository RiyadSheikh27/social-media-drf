from rest_framework import serializers
from .models import *
from django.contrib.auth import get_user_model

User = get_user_model()

class CommunitySerializer(serializers.ModelSerializer):
    """Serializer for Community"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    is_member = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    can_post = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    
    class Meta:
        model = Community
        fields = [
            'id', 'name', 'title', 'description', 'profile_image', 'cover_image',
            'visibility', 'created_at', 'created_by', 'created_by_username',
            'updated_at', 'members_count', 'posts_count', 'is_member', 
            'user_role', 'can_post', 'can_manage'
        ]
        read_only_fields = ['created_by', 'members_count', 'posts_count', 'created_at', 'updated_at']
    
    def get_is_member(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return CommunityMember.objects.filter(
                user=request.user, 
                community=obj, 
                is_approved=True
            ).exists()
        return False
    
    def get_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = CommunityMember.objects.filter(
                user=request.user, 
                community=obj, 
                is_approved=True
            ).first()
            return membership.role if membership else None
        return None
    
    def get_can_post(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.created_by == request.user:
                return True
            membership = CommunityMember.objects.filter(
                user=request.user, 
                community=obj, 
                is_approved=True
            ).first()
            return membership is not None
        return False
    
    def get_can_manage(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if obj.created_by == request.user:
                return True
            membership = CommunityMember.objects.filter(
                user=request.user, 
                community=obj, 
                is_approved=True
            ).first()
            return membership and membership.role in ['admin', 'moderator']
        return False
    
    def create(self, validated_data):
        request = self.context.get('request')
        community = Community.objects.create(**validated_data, created_by=request.user)
        
        # Auto-add creator as admin member
        CommunityMember.objects.create(
            user=request.user,
            community=community,
            role='admin',
            is_approved=True
        )
        
        return community


class CommunityMemberSerializer(serializers.ModelSerializer):
    """Serializer for Community Members"""
    username = serializers.CharField(source='user.username', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True)
    
    class Meta:
        model = CommunityMember
        fields = [
            'id', 'user', 'username', 'community', 'community_name',
            'role', 'is_approved', 'joined_at'
        ]
        read_only_fields = ['user', 'joined_at']


class CommunityRuleSerializer(serializers.ModelSerializer):
    """Serializer for Community Rules"""
    
    class Meta:
        model = CommunityRule
        fields = ['id', 'community', 'title', 'description', 'order', 'created_at']
        read_only_fields = ['created_at']


class CommunityInvitationSerializer(serializers.ModelSerializer):
    """Serializer for Community Invitations"""
    inviter_username = serializers.CharField(source='inviter.username', read_only=True)
    invitee_username = serializers.CharField(source='invitee.username', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True)
    community_title = serializers.CharField(source='community.title', read_only=True)
    
    class Meta:
        model = CommunityInvitation
        fields = [
            'id', 'community', 'community_name', 'community_title',
            'inviter', 'inviter_username', 'invitee', 'invitee_username',
            'status', 'message', 'created_at', 'responded_at'
        ]
        read_only_fields = ['inviter', 'status', 'created_at', 'responded_at']
    
    def create(self, validated_data):
        request = self.context.get('request')
        invitation = CommunityInvitation.objects.create(**validated_data, inviter=request.user)
        
        # Create notification
        from posts.models import Notification
        Notification.objects.create(
            recipient=invitation.invitee,
            sender=request.user,
            notification_type='community_invite',
            community=invitation.community,
            message=f"invited you to join {invitation.community.title}"
        )
        
        return invitation


class CommunityJoinRequestSerializer(serializers.ModelSerializer):
    """Serializer for Community Join Requests"""
    username = serializers.CharField(source='user.username', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True)
    community_title = serializers.CharField(source='community.title', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    
    class Meta:
        model = CommunityJoinRequest
        fields = [
            'id', 'user', 'username', 'community', 'community_name', 'community_title',
            'status', 'message', 'created_at', 'reviewed_by', 'reviewed_by_username', 'reviewed_at'
        ]
        read_only_fields = ['user', 'status', 'created_at', 'reviewed_by', 'reviewed_at']
    
    def create(self, validated_data):
        request = self.context.get('request')
        join_request = CommunityJoinRequest.objects.create(**validated_data, user=request.user)
        
        # Notify community admins
        from posts.models import Notification
        admins = CommunityMember.objects.filter(
            community=join_request.community,
            role__in=['admin', 'moderator'],
            is_approved=True
        ).select_related('user')
        
        for admin in admins:
            Notification.objects.create(
                recipient=admin.user,
                sender=request.user,
                notification_type='community_join_request',
                community=join_request.community,
                message=f"wants to join {join_request.community.title}"
            )
        
        return join_request


class CommunityDetailSerializer(CommunitySerializer):
    """Detailed Community Serializer with rules and members preview"""
    rules = CommunityRuleSerializer(many=True, read_only=True)
    recent_members = serializers.SerializerMethodField()
    pending_requests_count = serializers.SerializerMethodField()
    
    class Meta(CommunitySerializer.Meta):
        fields = CommunitySerializer.Meta.fields + ['rules', 'recent_members', 'pending_requests_count']
    
    def get_recent_members(self, obj):
        members = CommunityMember.objects.filter(
            community=obj, 
            is_approved=True
        ).select_related('user').order_by('-joined_at')[:10]
        return CommunityMemberSerializer(members, many=True).data
    
    def get_pending_requests_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Only show to admins/moderators
            membership = CommunityMember.objects.filter(
                user=request.user,
                community=obj,
                is_approved=True
            ).first()
            
            if membership and membership.role in ['admin', 'moderator']:
                return CommunityJoinRequest.objects.filter(
                    community=obj,
                    status='pending'
                ).count()
        return 0