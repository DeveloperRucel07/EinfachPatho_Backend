from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from auth_app.api.authentication import CookieJWTAuthentication
from auth_app.api.serializers import  RegistrationSerializer, CustomTokenObtainPairSerializer, UserSerializer

class RegistrationView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        '''User registration View

        Args:
            request (request): user request

        Returns:
            data, status: return the user data with the status 200, if the infornmations was correct and 
            400 if noting was probided or if informatons provided as incorrect.
        '''
        
        serializer = RegistrationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            data = {
                'detail': 'User created successfully!'
            }
            return Response(data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    

class CookieTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    def post(self, request, *args, **kwargs):
        '''Override the post method to set the JWT token in an HttpOnly cookie.
        Args:
            request (request): user request
        Returns:
            response: response with the JWT token set in an HttpOnly cookie.
        '''
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh = serializer.validated_data['refresh']
        access = serializer.validated_data['access']
        
        response = Response({'message':'Login successfully'}, status=status.HTTP_200_OK)
        response.set_cookie(
            key='access_token',
            value=str(access),
            httponly=True,
            secure=True,
            samesite='Lax',
        )
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure=True,
            samesite='Lax',
        )
        data = {
            'detail': 'Login successfully!',
            'user': UserSerializer(serializer.user).data
        }
        response.data = data
        return response


class CookieTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        '''Override the post method to refresh the JWT token from HttpOnly cookie.

        Args:
            request (request): user request
        Returns:
            response: response with the refreshed JWT token set in an HttpOnly cookie.
        '''
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({'detail': 'Refresh token not provided'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data={'refresh': refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except:
            return Response({'detail': 'Invalid refresh token'}, status=status.HTTP_400_BAD_REQUEST)
        
        data = {
            'detail': 'Token refreshed',
            'access': serializer.validated_data.get('access')
        }
        access = serializer.validated_data.get('access')
        response = Response(data, status=status.HTTP_200_OK)
        response.set_cookie(
            key='access_token',
            value=access,
            httponly=True,
            secure=True,
            samesite='Lax',
        )
        return response
            
class LogoutView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        '''User logout View

        Args:
            request (request): user request

        Returns:
            data, status: return a success message with status 200.
        '''
        response = Response()
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        response.data = {'detail': 'Log-Out successfully! All Tokens will be deleted. Refresh token is now invalid.'}
        response.status_code = status.HTTP_200_OK
        return response           