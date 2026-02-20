from django.db import models

from auth_app.api.authentication import User


class Disease(models.Model):
    disease_id = models.CharField(max_length=50, unique=True, db_index=True)
    owner = models.ForeignKey(
        User,
        related_name='diseases',
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255, db_index=True)
    image = models.URLField(null=True, blank=True, max_length=1000)
    category = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.name


class DurstData(models.Model):
    """Extended descriptive data ("DURST") tied to a disease.

    This model contains the long-form explanation (definition), the plain text
    description of the causes ("Ursachen"), and pointers to related lists such
    as keywords, risk factors, symptoms, and immediate actions.  We keep a
    one-to-one relationship to the parent `Disease` to make it easy to pull all
    the extended information in a single `select_related` call.
    """

    disease = models.OneToOneField(
        Disease,
        related_name="durst_data",
        on_delete=models.CASCADE
    )
    definition = models.TextField()
    ursachen = models.TextField(verbose_name="Ursachen")
    red_flags = models.TextField(blank=True, help_text="Warnsignale, die eine Lungenembolie nahelegen können")
    diagnostic_gold_standard = models.TextField(blank=True)
    guideline_link = models.URLField(blank=True)

    class Meta:
        ordering = ["disease"]
        verbose_name = "Durst Data"
        verbose_name_plural = "Durst Data"

    def __str__(self):
        return f"DurstData – {self.disease.name}"


class UrsacheKeyword(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="ursache_keywords",
        on_delete=models.CASCADE
    )
    keyword = models.CharField(max_length=255, db_index=True)

    class Meta:
        unique_together = ("durst_data", "keyword")
        ordering = ["keyword"]

    def __str__(self):
        return self.keyword


class RiskFactor(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="risk_factors",
        on_delete=models.CASCADE
    )
    text = models.TextField()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        # keep a short preview of the text to avoid huge strings
        return (self.text[:50] + "…") if len(self.text) > 50 else self.text


class Symptom(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="symptoms",
        on_delete=models.CASCADE
    )
    text = models.TextField()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.text


class ImmediateAction(models.Model):
    durst_data = models.ForeignKey(
        DurstData,
        related_name="immediate_actions",
        on_delete=models.CASCADE
    )
    text = models.TextField()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.text



class Quiz(models.Model):
    disease = models.ForeignKey(
        Disease,
        related_name="quizzes",
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

class Question(models.Model):
    id = models.AutoField(primary_key=True)

    question = models.CharField(max_length=300)
    options = models.JSONField()
    quiz = models.ForeignKey(
        Quiz,
        related_name="questions",
        on_delete=models.CASCADE
    )
    correct_index = models.IntegerField()
    explanation = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.question

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

    class Meta:
        unique_together = ("disease", "link")
        ordering = ["source_name"]

    def __str__(self):
        return self.source_name

