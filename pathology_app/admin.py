from django.contrib import admin
from django.db.models import Count

from pathology_app.models import Disease, DurstData, ImmediateAction, Question, RiskFactor, Source, Symptom, UrsacheKeyword


class UrsacheKeywordInline(admin.TabularInline):
    model = UrsacheKeyword
    extra = 1
    search_fields = ("keyword",)


class RiskFactorInline(admin.TabularInline):
    model = RiskFactor
    extra = 1


class SymptomInline(admin.TabularInline):
    model = Symptom
    extra = 1


class ImmediateActionInline(admin.TabularInline):
    model = ImmediateAction
    extra = 1

class DurstDataInline(admin.StackedInline):
    model = DurstData
    extra = 0
    show_change_link = True

class SourceInline(admin.TabularInline):
    model = Source
    extra = 1


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question", "quiz", "correct_index")
    list_filter = ("quiz",)
    search_fields = ("question",)
    readonly_fields = ("created_at", "updated_at")

@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "disease_id",
        "name",
        "category",
        "owner",
        "created_at",
        "quiz_count",
    )

    list_filter = ("category", "created_at")
    search_fields = ("name", "category", "disease_id")
    readonly_fields = ("created_at", "updated_at")

    inlines = [
        DurstDataInline,
        SourceInline,
    ]

    autocomplete_fields = ("owner",)

    fieldsets = (
        ("Basic Information", {
            "fields": (
                "disease_id",
                "name",
                "category",
                "owner",
                "image",
            )
        }),
        ("Metadata", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at"),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _quiz_count=Count("quizzes")
        )

    def quiz_count(self, obj):
        return obj.quizzes.count()

    quiz_count.short_description = "Quizzes"


