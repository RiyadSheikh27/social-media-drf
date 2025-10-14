from rest_framework import serializers
from .models import Post, Like, Comment, Share


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'user', 'post', 'created_at']
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        return Like.objects.get_or_create(user=user, post=validated_data['post'])[0]

class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = Comment
        fields = ['id', 'user', 'user_name', 'post', 'content', 'created_at']
        read_only_fields = ['user', 'created_at']

class ShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Share
        fields = ['id', 'user', 'post', 'created_at']
        read_only_fields = ['user', 'created_at']

class PostSerializer(serializers.ModelSerializer):
    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)
    shares_count = serializers.IntegerField(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'user', 'title', 'post_type', 'content', 'media_file', 'link',
            'tags', 'status', 'created_at', 'updated_at',
            'likes_count', 'comments_count', 'shares_count', 'comments',
        ]
        read_only_fields = ['user', 'likes_count', 'comments_count', 'shares_count', 'created_at', 'updated_at']