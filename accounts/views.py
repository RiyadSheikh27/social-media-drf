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
from .utils import *
import logging

logger = logging.getLogger(__name__)

from .utils import (
    verify_google_access_token, 
    verify_apple_access_token,
    get_google_user_info,
    get_apple_user_info
)


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

        return Response({
            "success": True,
            "message": "OTP sent to your email."
            }, status=201)


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
            return Response({
                "success": True,
                "message": "Email verified successfully. Now set username and password."
                })

        return Response({
            "success": False,
            "error": "Invalid code"
            }, status=400)


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
                return Response({
                    "success": False,
                    "error": "If not authenticated, include 'email' field."
                    }, status=400)
            try:
                user = User.objects.get(email=email.lower())
            except User.DoesNotExist:
                return Response({
                    "success": False,
                    "error": "User not found"
                    }, status=404)
            if not user.email_verified:
                return Response({
                    "success": False,
                    "error": "Email not verified"
                    }, status=400)

        if user.username_set:
            return Response({
                "success": False,
                "error": "Credentials already set."
                }, status=403)

        username = ser.validated_data['username']
        password = ser.validated_data['password']

        if User.objects.filter(username=username).exclude(pk=user.pk).exists():
            return Response({
                "success": False,
                "username": "Already taken."
                }, status=400)

        user.username = username
        user.set_password(password)
        user.username_set = True
        user.save()

        return Response({
            "success": True,
            "message": "Credentials set successfully. You can now log in."
            }, status=201)

"""Login View"""
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        if not ser.is_valid():
            return Response({
                "success": False,
                "message": "Invalid data",
                "details": ser.errors
                }, status=400)

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
            return Response({
                "success": False,
                "error": "Invalid credentials"
                }, status=401)

        if not user.email_verified:
            return Response({
                "success": False,
                "error": "Email not verified"
                }, status=403)

        return Response({
            "success": True,
            "message": "Login successful", 
            "tokens": tokens_for_user(user)
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
        return Response({
            "success": False,
            "error": "Profiles are automatically created with user accounts. Use PUT/PATCH to update your profile."},
            status=status.HTTP_403_FORBIDDEN
        )

    def update(self, request, *args, **kwargs):
        """Only the profile owner can update their profile."""
        profile = self.get_object()
        
        if profile.user != request.user:
            return Response({
                "success": False,
                "error": "You do not have permission to edit this profile."
            })
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Only the profile owner can partially update their profile."""
        profile = self.get_object()
        
        if profile.user != request.user:
            return Response({
                "success": False,
                "error": "You do not have permission to edit this profile."
            })
        
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Prevent profile deletion - profiles should exist as long as user exists.
        If you want to delete profile, delete the user account instead.
        """
        return Response(
            {
                "success": False,
                "error": "Profiles cannot be deleted directly. Delete the user account to remove the profile."},
            status=status.HTTP_403_FORBIDDEN
        )

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get the current user's profile"""
        if not request.user.is_authenticated:
            return Response(
                {
                    "success": False,
                    "error": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        profile = get_object_or_404(Profile, user=request.user)
        serializer = self.get_serializer(profile)
        return Response({
            "success": True,
            "message": "Data retrieved successfully",
            "data": serializer.data
            })

    @action(detail=False, methods=['put', 'patch'])
    def update_me(self, request):
        """Update the current user's profile"""
        if not request.user.is_authenticated:
            return Response(
                {
                    "success": False,
                    "error": "Authentication credentials were not provided."},
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
            return Response({
                "success": True,
                "message": "Profile updated successfullty.",
                "data": response_serializer.data})
        
        return Response({
            "success": False,
            "error": "Invalid data."},
            serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search profiles by username or display name"""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response({
                "success": False,
                "error": "Please provide a search query using ?q=searchterm"},
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
        return Response({
            "success": True,
            "message": "Data retrieved successfully.",
            "data" : serializer.data})
    

"""OAuth Register View - Using Access Token"""
class OAuthRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Log incoming request data for debugging
        logger.info(f"OAuth Register Request Data: {request.data}")
        
        serializer = OAuthRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer Validation Error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        access_token = serializer.validated_data['access_token']
        provider = serializer.validated_data['provider'].lower()

        logger.info(f"Provider: {provider}")

        # Verify access token and get user email based on provider
        email = None
        user_info = None

        try:
            if provider == 'google':
                # For Google: Use userinfo endpoint (PRIMARY METHOD)
                user_info = get_google_user_info(access_token)
                if user_info:
                    email = user_info.get('email')
                    logger.info(f"Google user info retrieved: {user_info}")
                else:
                    # Fallback: Try tokeninfo endpoint
                    email = verify_google_access_token(access_token)
                    logger.info(f"Google tokeninfo result: {email}")

            elif provider == 'apple':
                # For Apple: Verify JWT token
                email = verify_apple_access_token(access_token)
                logger.info(f"Apple token verification result: {email}")
                
                # Fallback: Get user info without verification
                if not email:
                    user_info = get_apple_user_info(access_token)
                    if user_info:
                        email = user_info.get('email')
                        logger.info(f"Apple user info: {user_info}")
            else:
                return Response(
                    {"error": "Unsupported provider. Use 'google' or 'apple'."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not email:
                logger.error(f"Failed to get email from {provider} token")
                return Response(
                    {
                        "error": f"Invalid {provider} access token or unable to retrieve user information.",
                        "details": "Please ensure the token is valid and has not expired."
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate username from email (part before @)
            base_username = email.split('@')[0].lower()
            # Remove special characters from username
            base_username = ''.join(c if c.isalnum() or c in ['_', '.'] else '_' for c in base_username)
            username = base_username

            # Check if user already exists
            try:
                existing_user = User.objects.get(email=email)
                logger.info(f"User already exists: {email}")
                return Response(
                    {
                        "message": "User already registered with this email.",
                        "email": email,
                        "username": existing_user.username,
                        "provider": provider
                    }, 
                    status=status.HTTP_200_OK
                )
            except User.DoesNotExist:
                pass

            # Ensure username is unique
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            # Create new user
            user = User.objects.create(
                email=email,
                username=username,
                email_verified=True,
                is_oauth_user=True,
                username_set=True
            )

            # Set unusable password for OAuth users
            user.set_unusable_password()
            user.save()

            logger.info(f"User created successfully: {email}")

            return Response(
                {
                    "message": f"User registered successfully via {provider.title()}.",
                    "email": email,
                    "username": username,
                    "provider": provider
                }, 
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"OAuth Register Error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred during registration: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


"""OAuth Login View - Using Access Token"""
class OAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Log incoming request data for debugging
        logger.info(f"OAuth Login Request Data: {request.data}")
        
        serializer = OAuthLoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer Validation Error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        access_token = serializer.validated_data['access_token']
        provider = serializer.validated_data['provider'].lower()

        logger.info(f"Provider: {provider}")

        # Verify access token and get user email based on provider
        email = None
        user_info = None

        try:
            if provider == 'google':
                # For Google: Use userinfo endpoint (PRIMARY METHOD)
                user_info = get_google_user_info(access_token)
                if user_info:
                    email = user_info.get('email')
                    logger.info(f"Google user info retrieved: {user_info}")
                else:
                    # Fallback: Try tokeninfo endpoint
                    email = verify_google_access_token(access_token)
                    logger.info(f"Google tokeninfo result: {email}")

            elif provider == 'apple':
                # For Apple: Verify JWT token
                email = verify_apple_access_token(access_token)
                logger.info(f"Apple token verification result: {email}")
                
                # Fallback: Get user info without verification
                if not email:
                    user_info = get_apple_user_info(access_token)
                    if user_info:
                        email = user_info.get('email')
                        logger.info(f"Apple user info: {user_info}")
            else:
                return Response(
                    {"error": "Unsupported provider. Use 'google' or 'apple'."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not email:
                logger.error(f"Failed to get email from {provider} token")
                return Response(
                    {
                        "error": f"Invalid {provider} access token or unable to retrieve user information.",
                        "details": "Please ensure the token is valid and has not expired."
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if user exists
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.error(f"User not found: {email}")
                return Response(
                    {
                        "error": "User not registered. Please register first.",
                        "email": email
                    }, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Verify user is an OAuth user
            if not user.is_oauth_user:
                logger.error(f"User is not OAuth user: {email}")
                return Response(
                    {"error": "This account was not registered via OAuth. Please use email/password login."}, 
                    status=status.HTTP_403_FORBIDDEN
                )

            # Generate tokens
            tokens = tokens_for_user(user)

            logger.info(f"User logged in successfully: {email}")

            return Response(
                {
                    "message": f"Logged in successfully via {provider.title()}.",
                    "tokens": tokens,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                        "provider": provider
                    }
                }, 
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"OAuth Login Error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"An error occurred during login: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )