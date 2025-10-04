"""
Serializer for the user API View.
"""
from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import gettext as _
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework import serializers
from core.utils.email_service import EmailService, EmailSender
from allauth.socialaccount.models import SocialAccount


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the user object."""

    class Meta:
        model = get_user_model()
        fields = ("email", "password", "name")
        extra_kwargs = {"password": {"write_only": True, "min_length": 5}}

    def create(self, validated_data):
        """Create a new user with encrypted password and return it."""
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        """Update a user, setting the password correctly and return it."""
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()
        return user


class AuthTokenSerializer(serializers.Serializer):
    """Serializer for the user authentication token."""

    email = serializers.EmailField()
    password = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    def validate(self, attrs):
        """Validate and authenticate the user."""
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if not user:
            social_user = SocialAccount.objects.filter(
                                user__email=email
                            ).first()
            if social_user:
                msg = _("This user is a social user. Please use the social login.") # noqa
                raise serializers.ValidationError(msg, code="authorization")
            else:
                msg = _("Unable to log in with provided credentials.")
                raise serializers.ValidationError(msg, code="authorization")
        attrs["user"] = user
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for the password reset endpoint."""

    email = serializers.EmailField()

    def validate(self, attrs):
        """Validate the email."""
        email = attrs.get("email")

        if not get_user_model().objects.filter(email=email).exists():
            msg = _("No user with that email address.")
            raise serializers.ValidationError(msg, code="authorization")

        user = get_user_model().objects.get(email=email)
        if user.socialaccount_set.exists():
            raise serializers.ValidationError(
                {
                    "detail": _(
                        "No es posible restablecer la contraseña para una cuenta vinculada a Google. Por favor, inicia sesión utilizando tu cuenta de Google."  # noqa
                    )
                },
                code="social_account",
            )

        return attrs

    def send_password_reset_email(self, validated_data):
        """Send a password reset email."""
        email = validated_data.get("email")
        user = get_user_model().objects.get(email=email)

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)

        email_service = EmailService(EmailSender())

        if email_service.send_reset_password_email(user, token):
            return {"detail": _("Password reset email sent.")}
        else:
            raise serializers.ValidationError(
                _("An error occurred while sending the email."),
                code="authorization",
            )


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for the password reset confirm endpoint."""
    token = serializers.CharField()
    new_password = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
    )
    password_confirm = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
    )
    email = serializers.EmailField()

    def validate(self, attrs):
        """Validate the token and passwords."""
        new_password = attrs.get("new_password")
        password_confirm = attrs.get("password_confirm")

        if new_password != password_confirm:
            raise serializers.ValidationError(
                _("Passwords do not match."), code="authorization"
            )

        return attrs

    def confirm_password_reset(self, validated_data):
        """Confirm a password reset."""
        token = validated_data.get("token")
        new_password = validated_data.get("new_password")
        email = validated_data.get("email")

        user = get_user_model().objects.get(email=email)
        token_generator = PasswordResetTokenGenerator()

        if not token_generator.check_token(user, token):
            raise serializers.ValidationError(_("Invalid token."),
                                              code="authorization")

        user.set_password(new_password)
        user.save()

        return {"detail": _("Password reset successful.")}
