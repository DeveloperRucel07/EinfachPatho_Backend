from django.urls import path
from pathology_app.api.views import DiseaseDetailView, DiseaseListView

urlpatterns = [
    path('diseases/', DiseaseListView.as_view(), name='disease-list'),
    path('diseases/<int:pk>/', DiseaseDetailView.as_view(), name='disease-detail'),

]