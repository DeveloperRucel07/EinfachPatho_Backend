import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from django.shortcuts import get_object_or_404

from auth_app.api.authentication import CookieJWTAuthentication
from pathology_app.models import Disease, Quiz, QuizAttempt, Question, QuestionAnswer
from pathology_app.api.serializers import (
    DiseaseSerializer,
    DiseaseCreateSerializer,
    QuizAttemptSerializer,
    QuestionAnswerSerializer,
    AnswerSubmissionSerializer,
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


class QuizAttemptStartView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)

        if not (request.user.is_staff or request.user.is_superuser) and quiz.disease.owner_id != request.user.id:
            return Response({'detail': 'You do not have permission to access this quiz.'}, status=status.HTTP_403_FORBIDDEN)

        attempt = QuizAttempt.objects.create(quiz=quiz, user=request.user)
        return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class QuizAttemptAnswerView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, id=attempt_id)
        if attempt.user_id != request.user.id:
            return Response({'detail': 'You do not have permission to modify this attempt.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AnswerSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question_id = serializer.validated_data['question_id']
        selected_index = serializer.validated_data['selected_index']

        question = get_object_or_404(Question, id=question_id, quiz=attempt.quiz)
        if selected_index < 0 or selected_index >= len(question.options):
            return Response({'detail': 'selected_index is out of range for this question.'}, status=status.HTTP_400_BAD_REQUEST)

        answer, created = QuestionAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'selected_index': selected_index,
                'is_correct': selected_index == question.correct_index,
            },
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(QuestionAnswerSerializer(answer).data, status=code)


class QuizAttemptCompleteView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, id=attempt_id)
        if attempt.user_id != request.user.id:
            return Response({'detail': 'You do not have permission to modify this attempt.'}, status=status.HTTP_403_FORBIDDEN)

        attempt.complete()
        return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_200_OK)


class QuizAttemptListView(generics.ListAPIView):
    serializer_class = QuizAttemptSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get_queryset(self):
        queryset = QuizAttempt.objects.filter(user=self.request.user).select_related('quiz', 'quiz__disease').prefetch_related('answers')
        disease_id = self.request.query_params.get('disease')
        if disease_id:
            queryset = queryset.filter(quiz__disease__disease_id=disease_id)
        return queryset.order_by('-started_at')

