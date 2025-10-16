from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register('user-profiles', ProfileViewSet, basename='profiles')

urlpatterns = [
    path('', include(router.urls)),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('set-credentials/', SetCredentialsView.as_view(), name='set-credentials'),
    path('login/', LoginView.as_view(), name='login'),
    # path('oauth/register/', OAuthRegisterView.as_view(), name='oauth-register'),
    # path('oauth/login/', OAuthLoginView.as_view(), name='oauth-login'),
    path('oauth/register/', OAuthRegisterView.as_view(), name='oauth-register'),
    path('oauth/login/', OAuthLoginView.as_view(), name='oauth-login'),
]