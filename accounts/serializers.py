from rest_framework import serializers
from .models import User, Profile
import re
from django.contrib.auth.password_validation import validate_password

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username']

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class SetCredentialsSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        """
        Username rules:
        - Minimum 6 characters
        - Only lowercase letters, numbers, _, @
        - No spaces
        """
        if len(value) < 6:
            raise serializers.ValidationError("Username must be at least 6 characters long.")

        if not re.match(r'^[a-z0-9_@.]+$', value):
            raise serializers.ValidationError(
                "Username can contain only lowercase letters, numbers, '_', '.' and '@'. No spaces allowed."
            )

        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")

        return value

    def validate_password(self, value):
        """
        Password rules:
        - Minimum 8 characters
        - Can include a-z, A-Z, 0-9, special characters
        """
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        validate_password(value)  # Django's built-in password validators
        return value

class LoginSerializer(serializers.Serializer):
    email_or_username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class OAuthRegisterSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])

class OAuthLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])

""" Profile Section """
class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    can_edit = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'user_id', 'username', 'email',
            'display_name', 'about', 'social_link', 'avatar', 
            'cover_photo', 'created_at', 'updated_at', 
            'can_edit', 'posts_count'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False

    def get_posts_count(self, obj):
        """Get count of approved posts by this user"""
        return obj.user.posts.filter(status='approved').count()

    def validate_social_link(self, value):
        """Validate social link URL"""
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Social link must be a valid URL starting with http:// or https://")
        return value


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating profile - excludes read-only user info"""
    class Meta:
        model = Profile
        fields = [
            'display_name', 'about', 'social_link', 
            'avatar', 'cover_photo'
        ]

    def validate_social_link(self, value):
        """Validate social link URL"""
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Social link must be a valid URL starting with http:// or https://")
        return value