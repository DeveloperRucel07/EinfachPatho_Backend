# serializers.py
from rest_framework import serializers
from pathology_app.models import Disease, Quiz, Question, Source, DurstData, RiskFactor, Symptom, ImmediateAction, UrsacheKeyword





class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id",
            "question_title",
            "question_options",
            "correct_index",
            "explanation",
            "quiz",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        options = data.get("question_options")

        if not isinstance(options, list):
            raise serializers.ValidationError(
                "question_options must be a list."
            )

        if len(options) < 2:
            raise serializers.ValidationError(
                "At least 2 options are required."
            )

        if data["correct_index"] >= len(options):
            raise serializers.ValidationError(
                "correct_index is out of range."
            )

        if data["correct_index"] < 0:
            raise serializers.ValidationError(
                "correct_index cannot be negative."
            )

        return data

class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "disease",
            "questions",
            "created_at",
            "updated_at",
        ]


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["id", "source_name", "link"]


class RiskFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskFactor
        fields = ["id", "text"]


class SymptomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Symptom
        fields = ["id", "text"]


class ImmediateActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImmediateAction
        fields = ["id", "text"]


class UrsacheKeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UrsacheKeyword
        fields = ["id", "keyword"]


class DurstDataSerializer(serializers.ModelSerializer):
    risk_factors = RiskFactorSerializer(many=True)
    symptoms = SymptomSerializer(many=True)
    immediate_actions = ImmediateActionSerializer(many=True)
    ursache_keywords = UrsacheKeywordSerializer(many=True)

    class Meta:
        model = DurstData
        fields = [
            "definition",
            "ursachen_text",
            "red_flags",
            "diagnostic_gold_standard",
            "guideline_link",
            "risk_factors",
            "symptoms",
            "immediate_actions",
            "ursache_keywords",
        ]

    def create(self, validated_data):
        risk_data = validated_data.pop("risk_factors")
        symptom_data = validated_data.pop("symptoms")
        action_data = validated_data.pop("immediate_actions")
        keyword_data = validated_data.pop("ursache_keywords")

        durst = DurstData.objects.create(**validated_data)

        for r in risk_data:
            RiskFactor.objects.create(durst_data=durst, **r)

        for s in symptom_data:
            Symptom.objects.create(durst_data=durst, **s)

        for a in action_data:
            ImmediateAction.objects.create(durst_data=durst, **a)

        for k in keyword_data:
            UrsacheKeyword.objects.create(durst_data=durst, **k)

        return durst


class DiseaseSerializer(serializers.ModelSerializer):
    durst_data = DurstDataSerializer()
    quiz = QuizSerializer(many=True)
    sources = SourceSerializer(many=True)

    class Meta:
        model = Disease
        fields = [
            "id",
            "disease_id",
            "name",
            "image",
            "category",
            "durst_data",
            "quiz_questions",
            "sources",
        ]

    def create(self, validated_data):
        durst_data = validated_data.pop("durst_data")
        quiz_data = validated_data.pop("quiz_questions")
        sources_data = validated_data.pop("sources")
        disease = Disease.objects.create(**validated_data)
        durst_serializer = DurstDataSerializer(data=durst_data)
        durst_serializer.is_valid(raise_exception=True)
        durst_serializer.save(disease=disease)
        for quiz in quiz_data:
            quiz_serializer = QuizSerializer(data=quiz)
            quiz_serializer.is_valid(raise_exception=True)
            quiz_serializer.save(disease=disease)
        for source in sources_data:
            source_serializer = SourceSerializer(data=source)
            source_serializer.is_valid(raise_exception=True)
            source_serializer.save(disease=disease)
        return disease
