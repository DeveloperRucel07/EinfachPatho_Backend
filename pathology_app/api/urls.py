from django.urls import path
from pathology_app.api.views import (
    DiseaseDetailView,
    DiseaseListView,
    GenerateDiseaseView,
    QuizAttemptStartView,
    QuizAttemptAnswerView,
    QuizAttemptCompleteView,
    QuizAttemptListView,
)

urlpatterns = [
    path('generate_disease/', GenerateDiseaseView.as_view(), name='disease-generate'),
    path('diseases/', DiseaseListView.as_view(), name='disease-list'),
    path('diseases/<str:disease_id>/', DiseaseDetailView.as_view(), name='disease-detail'),
    path('quizzes/<int:quiz_id>/attempts/', QuizAttemptStartView.as_view(), name='quiz-attempt-start'),
    path('attempts/<int:attempt_id>/answer/', QuizAttemptAnswerView.as_view(), name='quiz-attempt-answer'),
    path('attempts/<int:attempt_id>/complete/', QuizAttemptCompleteView.as_view(), name='quiz-attempt-complete'),
    path('attempts/', QuizAttemptListView.as_view(), name='quiz-attempt-list'),

]