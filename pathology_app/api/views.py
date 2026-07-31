import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from django.shortcuts import get_object_or_404

from auth_app.api.authentication import CookieJWTAuthentication
from pathology_app.models import Disease
from pathology_app.api.serializers import (
    DiseaseSerializer,
    DiseaseCreateSerializer
)
from pathology_app.api.permissions import IsAdminOrOwner


logger = logging.getLogger(__name__)


class DiseaseListView(generics.ListAPIView):
    """
    API endpoint to list all diseases.
    Accessible by any user (read-only).
    """
    serializer_class = DiseaseSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {'created_at': ['exact', 'gte', 'lte']}

    def get_queryset(self):
        user = self.request.user
        qs = Disease.objects.all() if (user.is_staff or user.is_superuser) else Disease.objects.filter(owner=user)
        return qs.order_by('-created_at')


class DiseaseDetailView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve a single disease by ID.
    Accessible by any user (read-only).
    """
    queryset = Disease.objects.all()
    serializer_class = DiseaseSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAdminOrOwner]
    authentication_classes = [CookieJWTAuthentication]
    lookup_field = "disease_id"


class GenerateDiseaseView(APIView):
    """
    API endpoint to generate/create a disease either from a full JSON payload
    or from a short textual prompt.  The latter hooks into the Gemini AI helpers
    in `pathology_app.api.utils`.

    Requires authentication.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'generate_disease'
    
    def post(self, request):
        """
        Create a new disease from the supplied data.

        Two modes are supported:

        * **JSON mode** – client sends the full disease document (same format as
          the `DiseaseCreateSerializer` expects).  This is unchanged from
          previous behaviour.
        * **Prompt mode** – client sends a payload containing only the key
          ``prompt`` with a free‑text description.  The backend will use the
          Gemini AI helpers to resolve a disease name, generate a DURST JSON
          blob and then persist it.

        Example prompt request body::

            {"prompt": "tiefe venenthrombose"}
        """

        data = request.data.copy()

        # handle prompt generation first
        if 'prompt' in data:
            # avoid circular import at module load time
            from pathology_app.api import utils

            prompt_text = data.get('prompt', '')
            if not prompt_text:
                return Response(
                    {'detail': 'Prompt may not be empty.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                disease_name = utils.find_disease_by_prompt(prompt_text)
                # this will raise if JSON is malformed
                data = utils.create_disease_json_for_durst(disease_name)
            except Exception:
                logger.exception("AI generation failed", extra={"user_id": request.user.id})
                return Response(
                    {'detail': 'AI generation failed. Please try again later.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        serializer = DiseaseCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            disease = serializer.save()
            return Response(
                DiseaseSerializer(disease).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

