"""
Tests for the user API.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from unittest.mock import patch

from django.contrib.auth.tokens import PasswordResetTokenGenerator

from allauth.socialaccount.models import SocialLogin, SocialAccount
from allauth.socialaccount.models import SocialToken


CREATE_USER_URL = reverse('user:create')
TOKEN_URL = reverse('user:token')
ME_URL = reverse('user:me')
RESET_PASSWORD_URL = reverse('user:password_reset')
RESET_PASSWORD_CONFIRM_URL = reverse('user:password_reset_confirm')
GOOGLE_LOGIN_URL = reverse('user:google_login')


def create_user(**params):
    """Helper function to create a user."""
    return get_user_model().objects.create_user(**params)


class PublicUserApiTests(TestCase):
    """Test the user API (public)."""

    def setUp(self):
        self.client = APIClient()

    def test_create_user_success(self):
        """Test creating a user is successful."""
        payload = {
            'email': 'test@example.com',
            'password': 'TestPass123',
            'name': 'Test User',
        }

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(email=payload['email'])
        self.assertTrue(user.check_password(payload['password']))
        self.assertNotIn('password', res.data)

    def test_user_with_email_exists_error(self):
        """Test creating a user that already exists raises an error."""
        payload = {
            'email': 'test@example.com',
            'password': 'TestPass123',
            'name': 'Test User',
        }
        create_user(**payload)

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self):
        """Test that the password must be more than 5 characters."""
        payload = {
            'email': 'test@example.com',
            'password': 'pw',
            'name': 'Test User',
        }

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        user_exists = get_user_model().objects.filter(
            email=payload['email']
        ).exists()

        self.assertFalse(user_exists)

    def test_create_token_for_user(self):
        """Test that a token is created for the user."""
        user_details = {
            'email': 'test@example.com',
            'password': 'TestPass123',
            'name': 'Test User',
        }
        create_user(**user_details)

        payload = {
            'email': user_details['email'],
            'password': user_details['password'],
        }

        res = self.client.post(TOKEN_URL, payload)

        self.assertIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_create_token_invalid_credentials(self):
        """Test that token is not created for invalid credentials."""
        create_user(
            email='test@example.com',
            password='TestPass123',
        )

        payload = {'email': 'test@example.com', 'password': 'wrongpassword'}

        res = self.client.post(TOKEN_URL, payload)

        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_token_email_not_exists(self):
        """Test that token is not created for non-existing email."""
        payload = {'email': 'test@example.com', 'password': 'TestPass123'}
        res = self.client.post(TOKEN_URL, payload)

        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_token_blank_password(self):
        """Test that token is not created for blank password."""
        payload = {'email': 'test@example.com', 'password': ''}
        res = self.client.post(TOKEN_URL, payload)

        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_user_unauthorized(self):
        """Test that authentication is required for users."""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reset_password(self):
        """Test that password reset is successful."""
        user = create_user(
            email='test@example.com',
            password='TestPass123',
            name='Test User',
        )
        payload = {"email": user.email}

        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_reset_password_invalid_email(self):
        """Test that password reset fails for invalid email."""
        payload = {"email": ""}
        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_not_exists(self):
        """Test that password reset fails for non-existing email."""
        payload = {"email": "no-exists@mail.com"}
        res = self.client.post(RESET_PASSWORD_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_confirm(self):
        """Test that password reset confirmation is successful."""
        user = create_user(
            email='test@example.com',
            password='TestPass123',
            name='Test User',
        )
        token = PasswordResetTokenGenerator().make_token(user)
        payload = {
                    "token": token,
                    "new_password": "NewPass123",
                    "password_confirm": "NewPass123",
                    "email": user.email
                   }

        res = self.client.post(RESET_PASSWORD_CONFIRM_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_reset_password_confirm_invalid_token(self):
        """Test that password reset confirmation fails for invalid token."""
        user = create_user(
            email='test@example.com',
            password='TestPass123',
            name='Test User',
        )

        payload = {
                    "token": "invalid-token",
                    "new_password": "NewPass123",
                    "password_confirm": "NewPass123",
                    "email": user.email
                   }

        res = self.client.post(RESET_PASSWORD_CONFIRM_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_confirm_passwords_not_match(self):
        """
        Test that password reset confirmation fails for non-matching passwords.
        """
        user = create_user(
            email='test@example.com',
            password='TestPass123',
            name='Test User',
        )

        token = PasswordResetTokenGenerator().make_token(user)
        payload = {
                    "token": token,
                    "new_password": "NewPass123",
                    "password_confirm": "NewPass1234",
                    "email": user.email
                   }

        res = self.client.post(RESET_PASSWORD_CONFIRM_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_for_social_account(self):
        new_user = create_user(
            email='test@example.com',
            name='Test User'
        )

        SocialAccount.objects.create(
            user=new_user,
            provider='google',
            uid='unique_id_from_google',
        )

        res = self.client.post(RESET_PASSWORD_URL, {"email": new_user.email})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = 'No es posible restablecer la contraseña para una cuenta vinculada a Google. Por favor, inicia sesión utilizando tu cuenta de Google.'  # noqa
        self.assertEqual(res.data['detail'][0], expected_message)
        self.assertEqual(res.data['detail'][0].code, 'social_account')


class PrivateUserApiTests(TestCase):
    """Test API requests that require authentication."""

    def setUp(self):
        self.user = create_user(
            email='test@example.com',
            password='TestPass123',
            name='Test User',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_success(self):
        """Test retrieving profile for logged in user."""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {
            'name': self.user.name,
            'email': self.user.email,
        })

    def test_post_me_not_allowed(self):
        """Test that POST is not allowed on the me URL."""
        res = self.client.post(ME_URL, {})

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_user_profile(self):
        """Test updating the user profile for authenticated user."""
        payload = {'name': 'New Name', 'password': 'newpassword123'}

        res = self.client.patch(ME_URL, payload)

        self.user.refresh_from_db()
        self.assertEqual(self.user.name, payload['name'])
        self.assertTrue(self.user.check_password(payload['password']))
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class GoogleAuthTest(TestCase):
    """Test Google authentication."""
    def setUp(self):
        self.client = APIClient()

    @patch('allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.complete_login') # noqa
    @patch('allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token') # noqa
    def test_google_login_success(self,
                                  mock_get_access_token,
                                  mock_complete_login):
        """Test that Google login is successful."""

        new_user = get_user_model()(email="new@email.com")

        social_account = SocialAccount(
            user=new_user,
            provider='google',
            uid='unique_id_from_google',
        )

        social_token = SocialToken(
            account=social_account,
            token='test-token',
        )
        social_login = SocialLogin(user=new_user,
                                   account=social_account,
                                   token=social_token)

        mock_get_access_token.return_value = {'access_token': 'test-token'}
        mock_complete_login.return_value = social_login

        res = self.client.post(GOOGLE_LOGIN_URL,
                               {'access_token': 'test-token'})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
