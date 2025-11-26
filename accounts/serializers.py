from rest_framework import serializers
from .models import User, Profile
import re
from django.contrib.auth.password_validation import validate_password
from interest.models import SubCategory

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
        validate_password(value)  
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
    interests = serializers.SerializerMethodField()  # Add this
    subcategories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=SubCategory.objects.all(),
        required=False
    )

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'user_id', 'username', 'email',
            'display_name', 'about', 'social_link', 'avatar', 
            'cover_photo', 'subcategories', 'interests',  # Added interests
            'created_at', 'updated_at', 'can_edit', 'posts_count'
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
    
    def get_interests(self, obj):
        """Group interests by category for better display"""
        interests_by_category = {}
        subcategories = obj.subcategories.select_related('category').all()
        
        for sub in subcategories:
            category_name = sub.category.name
            if category_name not in interests_by_category:
                interests_by_category[category_name] = []
            interests_by_category[category_name].append({
                'id': sub.id,
                'name': sub.name
            })
        
        return interests_by_category

    def validate_social_link(self, value):
        """Validate social link URL"""
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Social link must be a valid URL starting with http:// or https://")
        return value

class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating profile - includes interests"""
    subcategories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=SubCategory.objects.all(),
        required=False,
        allow_empty=True
    )
    
    class Meta:
        model = Profile
        fields = [
            'display_name', 'about', 'social_link', 
            'avatar', 'cover_photo', 'subcategories'  # Added subcategories
        ]

    def validate_social_link(self, value):
        """Validate social link URL"""
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Social link must be a valid URL starting with http:// or https://")
        return value
    
    def validate_subcategories(self, value):
        """Optional: Add validation for subcategories"""
        if len(value) > 20:  # Example: limit to 20 interests
            raise serializers.ValidationError("You can select a maximum of 20 interests.")
        return value