from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch

from pathology_app.models import (
    Disease,
    DurstData,
    Quiz,
    QuizQuestion,
    QuizOption,
    Source,
)
from .serializers import (
    DiseaseSerializer,
    DurstDataSerializer,
    QuizSerializer,
    QuizQuestionSerializer,
    QuizOptionSerializer,
    SourceSerializer,
)
