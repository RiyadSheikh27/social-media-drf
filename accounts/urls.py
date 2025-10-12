from django.urls import path, include
from .views import *
urlpatterns = [
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('set-credentials/', SetCredentialsView.as_view(), name='set-credentials'),
    path('login/', LoginView.as_view(), name='login'),
    path('oauth/register/', OAuthRegisterView.as_view(), name='oauth-register'),
    path('oauth/login/', OAuthLoginView.as_view(), name='oauth-login'),
]
