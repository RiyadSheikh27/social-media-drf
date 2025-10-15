from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, permissions, status
from django.core.mail import send_mail
from django.conf import settings
import random
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .permissions import IsOwnerOrReadOnly
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.decorators import action
from .models import *
from .serializers import *
from post.models import *
from post.serializers import *
from .utils import verify_google_token, verify_apple_token


"""Generate JWT tokens"""
def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


"""Email OTP Registration Flow"""
class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = SendOTPSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        email = ser.validated_data['email'].lower()
        code = f"{random.randint(0, 999999):06d}"

        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': email.split('@')[0]}
        )
        user.verification_code = code
        user.email_verified = False
        user.is_oauth_user = False
        user.username_set = False
        user.save()

        send_mail(
            subject='Your verification code',
            message=f'Your verification code is {code}',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response({"message": "OTP sent to your email."}, status=201)


"""Verify Token"""
class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = VerifyOTPSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        email = ser.validated_data['email'].lower()
        code = ser.validated_data['code']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        if user.verification_code == code:
            user.email_verified = True
            user.verification_code = ''
            user.save()
            return Response({"message": "Email verified successfully. Now set username and password."})

        return Response({"error": "Invalid code"}, status=400)


"""Set Credential"""
class SetCredentialsView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = request.user if request.user and request.user.is_authenticated else None
        ser = SetCredentialsSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        if user is None:
            email = request.data.get('email')
            if not email:
                return Response({"error": "If not authenticated, include 'email' field."}, status=400)
            try:
                user = User.objects.get(email=email.lower())
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=404)
            if not user.email_verified:
                return Response({"error": "Email not verified"}, status=400)

        if user.username_set:
            return Response({"error": "Credentials already set."}, status=403)

        username = ser.validated_data['username']
        password = ser.validated_data['password']

        if User.objects.filter(username=username).exclude(pk=user.pk).exists():
            return Response({"username": "Already taken."}, status=400)

        user.username = username
        user.set_password(password)
        user.username_set = True
        user.save()

        return Response({"message": "Credentials set successfully. You can now log in."}, status=201)

"""Login View"""
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        key = ser.validated_data['email_or_username']
        password = ser.validated_data['password']

        user = authenticate(username=key, password=password)
        if user is None:
            try:
                u = User.objects.get(email=key.lower())
                user = authenticate(username=u.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            return Response({"error": "Invalid credentials"}, status=401)

        if not user.email_verified:
            return Response({"error": "Email not verified"}, status=403)

        return Response({"message": "Login successful", "tokens": tokens_for_user(user)}, status=200)


"""OAuth Register View"""
class OAuthRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        id_token_str = request.data.get('id_token')
        provider = request.data.get('provider')
        if not id_token_str or not provider:
            return Response({"error": "id_token and provider are required"}, status=400)

        if provider.lower() == 'google':
            email = verify_google_token(id_token_str)
        elif provider.lower() == 'apple':
            email = verify_apple_token(id_token_str)
        else:
            return Response({"error": "Unsupported provider"}, status=400)

        if not email:
            return Response({"error": "Invalid OAuth token"}, status=400)

        user, created = User.objects.get_or_create(
            email=email.lower(),
            defaults={
                'username': email.split('@')[0],
                'email_verified': True,
                'is_oauth_user': True,
                'username_set': True
            }
        )

        if not created:
            return Response({"message": "User already registered."}, status=200)

        return Response({"message": f"User registered via {provider.title()} successfully."}, status=201)

"""Oauth Login View"""
class OAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        id_token_str = request.data.get('id_token')
        provider = request.data.get('provider')
        if not id_token_str or not provider:
            return Response({"error": "id_token and provider are required"}, status=400)

        if provider.lower() == 'google':
            email = verify_google_token(id_token_str)
        elif provider.lower() == 'apple':
            email = verify_apple_token(id_token_str)
        else:
            return Response({"error": "Unsupported provider"}, status=400)

        if not email:
            return Response({"error": "Invalid OAuth token"}, status=400)

        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            return Response({"error": "User not registered"}, status=404)

        if not user.is_oauth_user:
            return Response({"error": "This user is not registered via OAuth"}, status=403)

        tokens = tokens_for_user(user)
        return Response({
            "message": f"Logged in via {provider.title()} successfully",
            "tokens": tokens,
            "user": {
                "email": user.email,
                "username": user.username,
                "provider": provider
            }
        }, status=200)
    
""" User Profile Section """
class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_serializer_class(self):
        """Use different serializers for read and write operations"""
        if self.action in ['update', 'partial_update']:
            return ProfileUpdateSerializer
        return ProfileSerializer

    def get_queryset(self):
        """Return all profiles for list view"""
        return Profile.objects.select_related('user').all().order_by('-created_at')

    def create(self, request, *args, **kwargs):
        """
        Prevent manual profile creation - profiles are auto-created with user.
        """
        return Response(
            {"detail": "Profiles are automatically created with user accounts. Use PUT/PATCH to update your profile."},
            status=status.HTTP_403_FORBIDDEN
        )

    def update(self, request, *args, **kwargs):
        """Only the profile owner can update their profile."""
        profile = self.get_object()
        
        if profile.user != request.user:
            raise PermissionDenied("You do not have permission to edit this profile.")
        
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Only the profile owner can partially update their profile."""
        profile = self.get_object()
        
        if profile.user != request.user:
            raise PermissionDenied("You do not have permission to edit this profile.")
        
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Prevent profile deletion - profiles should exist as long as user exists.
        If you want to delete profile, delete the user account instead.
        """
        return Response(
            {"detail": "Profiles cannot be deleted directly. Delete the user account to remove the profile."},
            status=status.HTTP_403_FORBIDDEN
        )

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get the current user's profile"""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        profile = get_object_or_404(Profile, user=request.user)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'])
    def update_me(self, request):
        """Update the current user's profile"""
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        profile = get_object_or_404(Profile, user=request.user)
        serializer = ProfileUpdateSerializer(
            profile, 
            data=request.data, 
            partial=request.method == 'PATCH',
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            # Return full profile data
            response_serializer = ProfileSerializer(profile, context={'request': request})
            return Response(response_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search profiles by username or display name"""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response(
                {"detail": "Please provide a search query using ?q=searchterm"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        profiles = Profile.objects.filter(
            models.Q(user__username__icontains=query) |
            models.Q(display_name__icontains=query)
        ).select_related('user').order_by('-created_at')
        
        page = self.paginate_queryset(profiles)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(profiles, many=True)
        return Response(serializer.data)
    
    # Hello world