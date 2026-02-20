from django.urls import path
from pathology_app.api.views import DiseaseDetailView, DiseaseListView, GenerateDiseaseView

urlpatterns = [
    path('generate_disease/', GenerateDiseaseView.as_view(), name='disease-generate'),
    path('diseases/', DiseaseListView.as_view(), name='disease-list'),
    path('diseases/<int:pk>/', DiseaseDetailView.as_view(), name='disease-detail'),

]