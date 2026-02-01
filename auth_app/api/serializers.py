from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth  import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    User Serializer.
    Used to serialize user data.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email']
        

class RegistrationSerializer(serializers.ModelSerializer):
    """
    Registration Serializer.
    read all registration informations
    write the fullname by assigning it to the username
    validate if the both password are correct or not.
    
    """
    confirmed_password = serializers.CharField(write_only = True)
    class Meta:
        model = User
        fields = ['username', 'email','password', 'confirmed_password']
        extra_kwargs = {
            'password':{
                'write_only': True
            }
        }
        
    def save(self):
        """ if all required informations was correct, create a user.

        Raises:
            serializers.ValidationError: password don't match
            serializers.ValidationError: the email already exists

        Returns:
            user data: a user information
        """
        
        
        pw = self.validated_data['password']
        repeated_pw = self.validated_data['confirmed_password']
        
        if pw != repeated_pw:
            raise serializers.ValidationError({'error':'passwords dont match'})
        
        if User.objects.filter(email = self.validated_data['email']).exists():
            raise serializers.ValidationError({'error':'this Email already exists'})
        
        account = User(email = self.validated_data['email'], username = self.validated_data['username'])
        account.set_password(pw)
        account.save()
        return account
    
    
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom Token Obtain Pair Serializer.
    Used to customize the token claims if needed.
    Currently, it does not add any additional claims.
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    
    def validate(self, attrs):
        """Validate user credentials and return token pair.

        Args:
            attrs (dict): Dictionary containing 'username' and 'password'.
        Returns:
            dict: Validated data including token pair.
        Raises:
            serializers.ValidationError: If authentication fails.
        """
        username = attrs.get('username')
        password = attrs.get('password')
        
        user = authenticate(username=username, password=password)
        
        if not user:
            raise serializers.ValidationError({'error':'Invalid credentials'})
        
        return super().validate(attrs)
    
        
        
    
    
        