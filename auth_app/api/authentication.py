from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model

User = get_user_model()
class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication class that retrieves the token from cookies.
    """
    def authenticate(self, request):
        """
        Overrides the default authenticate method to extract the token from cookies.

        Args:
            request: The HTTP request object.

        Returns:
            A tuple of (user, token) if authentication is successful, else None.
        """
        raw_token = request.COOKIES.get('access_token')
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token