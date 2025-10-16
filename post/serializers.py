from rest_framework import serializers
from .models import Post, Like, Comment, Share


class LikeSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Like
        fields = ['id', 'user', 'user_name', 'post', 'created_at']
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        post = validated_data['post']
        
        if post.status != 'approved':
            raise serializers.ValidationError("You can only like approved posts.")
        
        like, created = Like.objects.get_or_create(user=user, post=post)
        return like


class RecursiveSerializer(serializers.Serializer):
    """Serializer for recursive nested comments"""
    def to_representation(self, instance):
        serializer = self.parent.parent.__class__(instance, context=self.context)
        return serializer.data

class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    replies = RecursiveSerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'user', 'user_name', 'post', 'parent', 'content', 'created_at', 'updated_at', 'replies', 'replies_count', 'can_edit', 'can_delete']
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_replies_count(self, obj):
        return obj.replies.count()

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user or obj.post.user == request.user
        return False

    def validate(self, data):
        if data.get('post') and data['post'].status != 'approved':
            raise serializers.ValidationError("You can only comment on approved posts.")
        
        if data.get('parent') and data.get('post'):
            if data['parent'].post != data['post']:
                raise serializers.ValidationError("Parent comment must belong to the same post.")
        
        return data


class ShareSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    post_title = serializers.CharField(source='post.title', read_only=True)
    
    class Meta:
        model = Share
        fields = ['id', 'user', 'user_name', 'post', 'post_title', 'created_at']
        read_only_fields = ['user', 'created_at']

    def validate_post(self, value):
        """Ensure only approved posts can be shared"""
        if value.status != 'approved':
            raise serializers.ValidationError("You can only share approved posts.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        post = validated_data['post']
        
        # Allow multiple shares of the same post by the same user
        share = Share.objects.create(user=user, post=post)
        return share


class PostSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    shares_count = serializers.IntegerField(source='shares.count', read_only=True)
    comments = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'user', 'user_name', 'title', 'post_type', 'content', 'media_file', 'link',
            'tags', 'status', 'created_at', 'updated_at',
            'likes_count', 'comments_count', 'shares_count', 'comments',
            'can_edit', 'can_delete'
        ]
        read_only_fields = ['user', 'likes_count', 'comments_count', 'shares_count', 'created_at', 'updated_at']

    def get_comments(self, obj):
        top_level_comments = obj.comments.filter(parent=None)
        return CommentSerializer(top_level_comments, many=True, context=self.context).data

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False