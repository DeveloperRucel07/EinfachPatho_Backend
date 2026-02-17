from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch

from auth_app.api.authentication import CookieJWTAuthentication
from pathology_app.models import Disease
from .serializers import DiseaseSerializer
from .permissions import IsAdminOrOwner


class DiseaseListView(ListAPIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrOwner]
    serializer_class = DiseaseSerializer
    queryset = Disease.objects.all()


class DiseaseDetailView(GenericAPIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrOwner]
    serializer_class = DiseaseSerializer
    queryset = Disease.objects.all()

    def get(self, request, pk):
        disease = get_object_or_404(
            Disease.objects.prefetch_related(
                Prefetch('durst_data'),
                Prefetch('quizzes__questions__options'),
                Prefetch('sources')
            ),
            pk=pk
        )
        serializer = self.get_serializer(disease)
        return Response(serializer.data)
    


