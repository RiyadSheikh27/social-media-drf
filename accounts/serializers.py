from rest_framework import serializers
from .models import User
from django.contrib.auth.password_validation import validate_password

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class SetCredentialsSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        qs = User.objects.filter(username=data['username'])
        if qs.exists():
            raise serializers.ValidationError({"username":"Username already taken."})
        return data

class LoginSerializer(serializers.Serializer):
    email_or_username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class OAuthRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])

class OAuthLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    provider = serializers.ChoiceField(choices=['google', 'apple'])
