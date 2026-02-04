from django.urls import path
from .views import  MeView, RegistrationView, CookieTokenObtainPairView, CookieTokenRefreshView, LogoutView
urlpatterns = [

    path('register/',RegistrationView.as_view(), name='register'),
    path('login/', CookieTokenObtainPairView.as_view(), name='login'),
     path("auth/me/", MeView.as_view()),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
]