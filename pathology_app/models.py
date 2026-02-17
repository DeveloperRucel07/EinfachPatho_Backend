from django.db import models

from auth_app.api.authentication import User


class Disease(models.Model):
    disease_id = models.CharField(max_length=50, unique=True)
    owner = models.ForeignKey(
        User,
        related_name='diseases',
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    image = models.URLField()
    category = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class DurstData(models.Model):
    disease = models.OneToOneField(
        Disease,
        related_name="durst_data",
        on_delete=models.CASCADE
    )
    definition = models.TextField()
    ursachen_text = models.TextField()
    red_flags = models.TextField()
    diagnostic_gold_standard = models.TextField()
    guideline_link = models.URLField()

    def __str__(self):
        return f"DurstData - {self.disease.name}"


class UrsacheKeyword(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="ursache_keywords",
        on_delete=models.CASCADE
    )
    keyword = models.CharField(max_length=255)

    def __str__(self):
        return self.keyword


class RiskFactor(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="risk_factors",
        on_delete=models.CASCADE
    )
    text = models.TextField()


class Symptom(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="symptoms",
        on_delete=models.CASCADE
    )
    text = models.TextField()


class ImmediateAction(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="immediate_actions",
        on_delete=models.CASCADE
    )
    text = models.TextField()



class Quiz(models.Model):
    disease = models.ForeignKey(
        Disease,
        related_name="quizzes",
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.title

class Question(models.Model):
    id = models.AutoField(primary_key=True)

    question_title = models.CharField(max_length=200)
    question_options = models.JSONField()
    quiz = models.ForeignKey(
        Quiz,
        related_name="questions",
        on_delete=models.CASCADE
    )
    correct_index = models.IntegerField()
    explanation = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.question_title


class Source(models.Model):
    disease = models.ForeignKey(
        Disease,
        related_name="sources",
        on_delete=models.CASCADE
    )
    source_name = models.CharField(max_length=255)
    link = models.URLField()

    def __str__(self):
        return self.source_name

