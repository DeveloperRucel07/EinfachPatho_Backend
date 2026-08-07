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
    QuizAttemptSerializer,
    QuestionAnswerSerializer,
    AnswerSubmissionSerializer,
)
from pathology_app.api.utils import (
    DiseaseGenerationError,
    DiseaseGenerationService,
    GeneratedPayloadValidationError,
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

    def get_object(self):
        disease_id = self.kwargs[self.lookup_field]
        queryset = Disease.objects.filter(disease_id=disease_id).order_by('-created_at', '-id')

        user = self.request.user
        if user.is_authenticated and not (user.is_staff or user.is_superuser):
            owned = queryset.filter(owner=user).first()
            if owned is not None:
                self.check_object_permissions(self.request, owned)
                return owned

        obj = queryset.first()
        if obj is None:
            raise get_object_or_404(Disease, disease_id=disease_id)

        self.check_object_permissions(self.request, obj)
        return obj


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
        service = DiseaseGenerationService()
        data = request.data.copy()

        if 'prompt' in data:
            prompt_text = data.get('prompt', '')
            if not prompt_text:
                return Response(
                    {'detail': 'Prompt may not be empty.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                disease = service.get_or_generate(prompt_text, request.user, prompt_text=prompt_text)
            except GeneratedPayloadValidationError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except DiseaseGenerationError as exc:
                logger.error("AI generation failed", extra={"user_id": request.user.id, "error": str(exc)})
                return Response(
                    {'detail': 'AI generation failed. Please try again later.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            except Exception as exc:
                logger.error("Unexpected AI generation failure", extra={"user_id": request.user.id, "error": str(exc)})
                return Response(
                    {'detail': 'AI generation failed. Please try again later.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            return Response(
                DiseaseSerializer(disease).data,
                status=status.HTTP_201_CREATED
            )

        try:
            disease = service.persist_ai_payload(data, request.user)
        except GeneratedPayloadValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DiseaseGenerationError as exc:
            logger.error("Disease persistence failed", extra={"user_id": request.user.id, "error": str(exc)})
            return Response(
                {'detail': 'AI generation failed. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            logger.error("Unexpected disease generation failure", extra={"user_id": request.user.id, "error": str(exc)})
            return Response(
                {'detail': 'AI generation failed. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            DiseaseSerializer(disease).data,
            status=status.HTTP_201_CREATED
        )


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

