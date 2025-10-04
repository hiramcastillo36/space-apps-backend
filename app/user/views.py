"""
Views for the user API.
"""
from rest_framework import generics, authentication, permissions, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings
from rest_framework.response import Response
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings

from user.serializers import (
    UserSerializer,
    AuthTokenSerializer,
    PasswordResetSerializer,
    PasswordResetConfirmSerializer
)


class CreateUserView(generics.CreateAPIView):
    """Create a new user in the system."""
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]


class CreateTokenView(ObtainAuthToken):
    """Create a new auth token for the user."""
    serializer_class = AuthTokenSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES


class ManageUserView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated user."""
    serializer_class = UserSerializer
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return the authenticated user."""
        return self.request.user


class PasswordResetView(generics.GenericAPIView):
    """Request a password reset."""
    serializer_class = PasswordResetSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)

        # Validate input
        if serializer.is_valid():
            # Call instance method to send the reset email
            serializer.send_password_reset_email(request.data)
            return Response({'detail': 'Password reset email sent.'},
                            status=status.HTTP_200_OK)

        # Return error response if validation fails
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(generics.GenericAPIView):
    """Confirm a password reset."""
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        """Confirm a password reset."""
        serializer = self.serializer_class(data=request.data)

        # Validate input
        if serializer.is_valid():
            # Call instance method to reset the password
            serializer.confirm_password_reset(request.data)
            return Response({'detail': 'Password reset successful.'},
                            status=status.HTTP_200_OK)

        # Return error response if validation fails
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleLoginView(SocialLoginView):
    """Login using Google OAuth2."""
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_CALLBACK_URL
    client_class = OAuth2Client
