from rest_framework import serializers
from pathology_app.models import (
    Disease,
    DurstData,
    UrsacheKeyword,
    RiskFactor,
    Symptom,
    ImmediateAction,
    Quiz,
    Question,
    Source
)


class UrsacheKeywordSerializer(serializers.ModelSerializer):
    """
    Serializer for UrsacheKeyword model.
    Handles the keywords related to the causes (Ursachen) of a disease.
    """
    class Meta:
        model = UrsacheKeyword
        fields = ['id', 'keyword']
        read_only_fields = ['id']


class RiskFactorSerializer(serializers.ModelSerializer):
    """
    Serializer for RiskFactor model.
    Handles the risk factors of a disease.
    """
    class Meta:
        model = RiskFactor
        fields = ['id', 'text']
        read_only_fields = ['id']


class SymptomSerializer(serializers.ModelSerializer):
    """
    Serializer for Symptom model.
    Handles the symptoms of a disease.
    """
    class Meta:
        model = Symptom
        fields = ['id', 'text']
        read_only_fields = ['id']


class ImmediateActionSerializer(serializers.ModelSerializer):
    """
    Serializer for ImmediateAction model.
    Handles the immediate therapy actions for a disease.
    """
    class Meta:
        model = ImmediateAction
        fields = ['id', 'text']
        read_only_fields = ['id']


class QuestionSerializer(serializers.ModelSerializer):
    """
    Serializer for Question model.
    Handles quiz questions with options, correct answer index, and explanation.

    Includes validation to ensure the correct_index references an existing entry in
    the options list and that a question string is provided.
    """
    class Meta:
        model = Question
        fields = ['id', 'question', 'options', 'correct_index', 'explanation', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        options = attrs.get('options', [])
        correct = attrs.get('correct_index', 0)
        if not options or not isinstance(options, (list, tuple)):
            raise serializers.ValidationError("Options must be a non-empty list.")
        if correct < 0 or correct >= len(options):
            raise serializers.ValidationError("correct_index must be a valid index into options.")
        if not attrs.get('question'):
            raise serializers.ValidationError("Question text cannot be empty.")
        return attrs


class SourceSerializer(serializers.ModelSerializer):
    """
    Serializer for Source model.
    Handles the sources/references for a disease.
    """
    class Meta:
        model = Source
        fields = ['id', 'source_name', 'link']
        read_only_fields = ['id']


class QuizSerializer(serializers.ModelSerializer):
    """
    Serializer for Quiz model.
    Includes nested questions for the quiz.
    """
    questions = QuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Quiz
        fields = ['id', 'title', 'questions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class DurstDataSerializer(serializers.ModelSerializer):
    """
    Serializer for DurstData model.
    Includes nested related objects: ursache_keywords, risk_factors, symptoms, immediate_actions.
    """
    ursache_keywords = UrsacheKeywordSerializer(many=True, read_only=True)
    risk_factors = RiskFactorSerializer(many=True, read_only=True)
    symptoms = SymptomSerializer(many=True, read_only=True)
    immediate_actions = ImmediateActionSerializer(many=True, read_only=True)
    
    class Meta:
        model = DurstData
        fields = [
            'id',
            'definition',
            'ursachen',
            'ursache_keywords',
            'risk_factors',
            'symptoms',
            'red_flags',
            'immediate_actions',
            'diagnostic_gold_standard',
            'guideline_link'
        ]
        read_only_fields = ['id']


class DiseaseSerializer(serializers.ModelSerializer):
    """
    Serializer for Disease model.
    The main serializer that includes all related data:
    - durst_data (D-U-R-S-T data)
    - quizzes (with nested questions)
    - sources
    """
    durst_data = DurstDataSerializer(read_only=True)
    quizzes = QuizSerializer(many=True, read_only=True)
    sources = SourceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Disease
        fields = [
            'id',
            'disease_id',
            'name',
            'image',
            'category',
            'durst_data',
            'quizzes',
            'sources',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DiseaseCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a Disease with all related data.
    Used for the generate_disease endpoint to create disease from JSON.
    """
    durst_data = serializers.DictField(required=False)
    quiz = serializers.ListField(required=False, child=serializers.DictField())
    sources = serializers.ListField(required=False, child=serializers.DictField())
    
    class Meta:
        model = Disease
        fields = [
            'disease_id',
            'name',
            'image',
            'category',
            'durst_data',
            'quiz',
            'sources'
        ]
    
    def create(self, validated_data):
        """
        Create a Disease with all related objects from the JSON data.
        """
        # Extract related data
        durst_data = validated_data.pop('durst_data', {})
        quizzes_data = validated_data.pop('quiz', {})
        sources_data = validated_data.pop('sources', [])
        
        # Get the owner from the request context
        owner = self.context['request'].user
        
        # Create the Disease
        disease = Disease.objects.create(owner=owner, **validated_data)
        
        # Create DurstData
        if durst_data:
            ursachen_block = durst_data.get('ursachen', {})
            ursachen_keywords = ursachen_block.get('keywords', [])
            ursachen_text = ursachen_block.get('text', '')
            
            durst_data_obj = DurstData.objects.create(
                disease=disease,
                definition=durst_data.get('definition', ''),
                ursachen=ursachen_text,
                red_flags=durst_data.get('symptome', {}).get('red_flags', ''),
                diagnostic_gold_standard=durst_data.get('therapie_massnahmen', {}).get('diagnostic_gold_standard', ''),
                guideline_link=durst_data.get('therapie_massnahmen', {}).get('guideline_link', '')
            )
            
            # Create UrsacheKeywords
            for keyword in ursachen_keywords:
                UrsacheKeyword.objects.create(durst_data=durst_data_obj, keyword=keyword)
            
            # Create RiskFactors
            for risk_factor in durst_data.get('risikofaktoren', []):
                RiskFactor.objects.create(durst_data=durst_data_obj, text=risk_factor)
            
            # Create Symptoms
            # Corrected Symptoms loop
            symptom_list = durst_data.get('symptome', {}).get('list', [])
            for symptom in symptom_list:
                Symptom.objects.create(durst_data=durst_data_obj, text=symptom)
            
            # Create ImmediateActions
            for action in durst_data.get('therapie_massnahmen', {}).get('immediate_actions', []):
                ImmediateAction.objects.create(durst_data=durst_data_obj, text=action)
        
        # Create Quizzes and Questions
        if quizzes_data:
            quiz = Quiz.objects.create(disease=disease, title=f"Quiz für {disease.name}")

            questions_to_create = []
            for question_data in quizzes_data:
                if isinstance(question_data, dict):
                    questions_to_create.append(
                        Question(
                            quiz=quiz,
                            question=question_data.get('question', ''),
                            options=question_data.get('options', []),
                            correct_index=question_data.get('correct_index', 0),
                            explanation=question_data.get('explanation', '')
                        )
                    )
            if questions_to_create:
                Question.objects.bulk_create(questions_to_create)
                
        # Create Sources
        for source_data in sources_data:
            if isinstance(source_data, dict):
                Source.objects.create(
                    disease=disease,
                    source_name=source_data.get('source_name', ''),
                    link=source_data.get('link', '')
                )
        
        return disease

