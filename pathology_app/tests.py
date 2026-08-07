import os
import tempfile
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db import ProgrammingError
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient
from unittest import mock

from pathology_app.api.utils import create_disease_image_with_nanobanana
from pathology_app.api.utils import DiseaseGenerationService
from pathology_app.api.utils import GeneratedPayloadValidationError
from pathology_app.models import Disease, Quiz, Question, QuizAttempt


class GenerateDiseasePromptTests(TestCase):
    """Ensure that the generation endpoint works with a prompt string."""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass')
        self.client.force_authenticate(self.user)

    @mock.patch('pathology_app.api.views.DiseaseGenerationService.get_or_generate')
    def test_prompt_generates_disease(self, mock_get_or_generate):
        disease = Disease.objects.create(
            disease_id='TEST-001',
            owner=self.user,
            name='Test Disease',
            category='Testcat',
        )
        mock_get_or_generate.return_value = disease

        # act
        response = self.client.post('/api/generate_disease/', {'prompt': 'anything'}, format='json')

        # assert
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['disease_id'], 'TEST-001')
        self.assertEqual(response.data['name'], 'Test Disease')
        mock_get_or_generate.assert_called_once_with('anything', self.user, prompt_text='anything')


class DiseaseListAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user_one = User.objects.create_user(username='user_one', email='user_one@example.com', password='StrongPassword#2026')
        self.user_two = User.objects.create_user(username='user_two', email='user_two@example.com', password='StrongPassword#2026')

        Disease.objects.create(
            disease_id='D-ONE-001',
            owner=self.user_one,
            name='Disease One',
            category='Cardiology',
        )
        Disease.objects.create(
            disease_id='D-TWO-001',
            owner=self.user_two,
            name='Disease Two',
            category='Neurology',
        )

    def test_anonymous_list_is_unauthorized(self):
        response = self.client.get('/api/diseases/')
        self.assertEqual(response.status_code, 401)

    def test_each_user_only_sees_own_diseases(self):
        self.client.force_authenticate(user=self.user_one)
        response = self.client.get('/api/diseases/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['disease_id'], 'D-ONE-001')


class GenerateDiseaseFailureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='generator_user',
            email='generator_user@example.com',
            password='StrongPassword#2026',
        )
        self.client.force_authenticate(user=self.user)

    @mock.patch('pathology_app.api.views.logger.error')
    @mock.patch('pathology_app.api.views.DiseaseGenerationService.get_or_generate')
    def test_generation_error_is_redacted(self, mock_get_or_generate, mock_logger_error):
        mock_get_or_generate.side_effect = Exception('internal-sdk-error-with-sensitive-data')

        response = self.client.post('/api/generate_disease/', {'prompt': 'something'}, format='json')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['detail'], 'AI generation failed. Please try again later.')
        self.assertNotIn('internal-sdk-error-with-sensitive-data', response.data['detail'])
        mock_logger_error.assert_called_once()

    @mock.patch('pathology_app.api.views.DiseaseGenerationService.get_or_generate')
    def test_generation_validation_error_returns_400(self, mock_get_or_generate):
        mock_get_or_generate.side_effect = GeneratedPayloadValidationError('Gemini output was not valid JSON.')

        response = self.client.post('/api/generate_disease/', {'prompt': 'something'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Gemini output was not valid JSON.')


class DiseaseDetailAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = get_user_model().objects.create_user(
            username='detail_owner',
            email='detail_owner@example.com',
            password='StrongPassword#2026',
        )
        self.disease = Disease.objects.create(
            disease_id='DETAIL-001',
            owner=self.owner,
            name='Detail Disease',
            category='Neurology',
        )

    def test_anonymous_detail_is_read_only_accessible(self):
        response = self.client.get(f'/api/diseases/{self.disease.disease_id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['disease_id'], 'DETAIL-001')

    def test_authenticated_user_gets_own_duplicate_disease_detail(self):
        other_user = get_user_model().objects.create_user(
            username='detail_other',
            email='detail_other@example.com',
            password='StrongPassword#2026',
        )
        other_disease = Disease.objects.create(
            disease_id='DETAIL-001',
            owner=other_user,
            name='Other Detail Disease',
            category='Cardiology',
        )

        self.client.force_authenticate(user=other_user)
        response = self.client.get(f'/api/diseases/{self.disease.disease_id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], other_disease.id)
        self.assertEqual(response.data['name'], 'Other Detail Disease')


class DiseaseGenerationReuseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username='reuse_user', email='reuse_user@example.com', password='StrongPassword#2026')
        self.other_user = User.objects.create_user(username='reuse_other_user', email='reuse_other_user@example.com', password='StrongPassword#2026')

    def test_existing_disease_short_circuits_before_provider(self):
        disease = Disease.objects.create(
            disease_id='REUSE-001',
            owner=self.user,
            name='  ReUsE Disease  ',
            category='Category',
        )

        mock_provider = mock.Mock()
        mock_provider.resolve_disease_name.side_effect = AssertionError('resolve_disease_name should not run')
        mock_provider.generate_disease_payload.side_effect = AssertionError('generate_disease_payload should not run')

        service = DiseaseGenerationService(provider=mock_provider)
        result = service.get_or_generate('reuse disease', self.user, prompt_text='reuse disease')

        self.assertEqual(result.id, disease.id)
        mock_provider.resolve_disease_name.assert_not_called()
        mock_provider.generate_disease_payload.assert_not_called()

    def test_invalid_provider_json_becomes_validation_error(self):
        mock_provider = mock.Mock()
        mock_provider.model_name = 'mock-gemini'
        mock_provider.resolve_disease_name.return_value = 'Fresh Disease'
        mock_provider.generate_disease_payload.side_effect = GeneratedPayloadValidationError('Gemini output was not valid JSON.')

        service = DiseaseGenerationService(provider=mock_provider)

        with self.assertRaises(GeneratedPayloadValidationError):
            service.get_or_generate('prompt text', self.user, prompt_text='prompt text')

    def test_existing_disease_is_cloned_for_other_owner_without_provider_call(self):
        disease = Disease.objects.create(
            disease_id='REUSE-CLONE-001',
            owner=self.user,
            name='Clone Disease',
            category='Category',
            image='https://example.com/clone.png',
        )
        durst_data = disease.durst_data = disease._meta.get_field('id') and None
        from pathology_app.models import DurstData, ImmediateAction, RiskFactor, Source, Symptom, UrsacheKeyword
        durst_data = DurstData.objects.create(
            disease=disease,
            definition='Definition',
            ursachen='Cause text',
            red_flags='Red flag',
            diagnostic_gold_standard='CT',
            guideline_link='https://example.com/guideline',
        )
        UrsacheKeyword.objects.create(durst_data=durst_data, keyword='Keyword A')
        RiskFactor.objects.create(durst_data=durst_data, text='Risk A')
        Symptom.objects.create(durst_data=durst_data, text='Symptom A')
        ImmediateAction.objects.create(durst_data=durst_data, text='Action A')
        Source.objects.create(disease=disease, source_name='Source A', link='https://example.com/source-a')
        quiz = Quiz.objects.create(disease=disease, title='Quiz for Clone Disease')
        Question.objects.create(
            quiz=quiz,
            question='Question 1',
            options=['A', 'B', 'C', 'D'],
            correct_index=1,
            explanation='Because B',
        )

        mock_provider = mock.Mock()
        mock_provider.resolve_disease_name.side_effect = AssertionError('resolve_disease_name should not run')
        mock_provider.generate_disease_payload.side_effect = AssertionError('generate_disease_payload should not run')

        service = DiseaseGenerationService(provider=mock_provider)
        result = service.get_or_generate('Clone Disease', self.other_user, prompt_text='Clone Disease')

        self.assertNotEqual(result.id, disease.id)
        self.assertEqual(result.owner_id, self.other_user.id)
        self.assertEqual(result.disease_id, disease.disease_id)
        self.assertEqual(result.durst_data.definition, 'Definition')
        self.assertEqual(result.durst_data.ursache_keywords.count(), 1)
        self.assertEqual(result.sources.count(), 1)
        self.assertEqual(result.quizzes.count(), 1)
        self.assertEqual(result.quizzes.first().questions.count(), 1)
        mock_provider.resolve_disease_name.assert_not_called()
        mock_provider.generate_disease_payload.assert_not_called()

    def test_cached_reuse_is_isolated_per_owner(self):
        disease = Disease.objects.create(
            disease_id='REUSE-CACHE-001',
            owner=self.user,
            name='Cache Disease',
            category='Category',
        )

        service = DiseaseGenerationService(provider=mock.Mock())
        service._cache_disease(disease)

        self.assertIsNone(service._get_cached_disease('Cache Disease', self.other_user))


class DiseaseGenerationStateFallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='state_fallback_user',
            email='state_fallback_user@example.com',
            password='StrongPassword#2026',
        )

    def _valid_payload(self, disease_id='FALLBACK-001', name='Fallback Disease'):
        return {
            'disease_id': disease_id,
            'name': name,
            'image': 'https://example.com/fallback.png',
            'category': 'Emergency Medicine',
            'durst_data': {
                'definition': 'Definition',
                'ursachen': {'text': 'Cause text', 'keywords': ['Keyword A', 'Keyword B']},
                'risikofaktoren': ['Risk A'],
                'symptome': {'list': ['Symptom A'], 'red_flags': 'Red flag'},
                'therapie_massnahmen': {
                    'immediate_actions': ['Action A'],
                    'diagnostic_gold_standard': 'CT',
                    'guideline_link': 'https://example.com/guideline',
                },
            },
            'quiz': [
                {
                    'question': f'Question {index}',
                    'options': ['A', 'B', 'C', 'D'],
                    'correct_index': 0,
                    'explanation': 'Explanation',
                }
                for index in range(1, 6)
            ],
            'sources': [
                {'source_name': 'Source A', 'link': 'https://example.com/source-a'},
                {'source_name': 'Source B', 'link': 'https://example.com/source-b'},
            ],
        }

    def test_get_or_generate_falls_back_when_generation_state_table_is_missing(self):
        provider = mock.Mock()
        provider.model_name = 'mock-gemini'
        provider.resolve_disease_name.return_value = 'Fallback Disease'
        provider.generate_disease_payload.return_value = self._valid_payload()

        service = DiseaseGenerationService(provider=provider)

        with mock.patch.object(
            service,
            '_lock_generation_state',
            side_effect=ProgrammingError('relation "pathology_app_diseasegenerationstate" does not exist'),
        ):
            disease = service.get_or_generate('prompt text', self.user, prompt_text='prompt text')

        self.assertEqual(disease.name, 'Fallback Disease')
        self.assertEqual(disease.owner_id, self.user.id)
        provider.generate_disease_payload.assert_called_once_with('Fallback Disease')

    def test_persist_ai_payload_falls_back_when_generation_state_table_is_missing(self):
        service = DiseaseGenerationService(provider=mock.Mock(model_name='mock-gemini'))
        payload = self._valid_payload(disease_id='FALLBACK-002', name='Fallback Persist Disease')

        with mock.patch.object(
            service,
            '_lock_generation_state',
            side_effect=ProgrammingError('relation "pathology_app_diseasegenerationstate" does not exist'),
        ):
            disease = service.persist_ai_payload(payload, self.user)

        self.assertEqual(disease.name, 'Fallback Persist Disease')
        self.assertEqual(disease.owner_id, self.user.id)


class DiseaseIdUniquenessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_one = User.objects.create_user(username='owner_one', email='owner_one@example.com', password='StrongPassword#2026')
        self.user_two = User.objects.create_user(username='owner_two', email='owner_two@example.com', password='StrongPassword#2026')

    def test_same_disease_id_across_two_owners_is_allowed(self):
        Disease.objects.create(
            disease_id='DUPL-001',
            owner=self.user_one,
            name='Disease A',
            category='Category A',
        )
        Disease.objects.create(
            disease_id='DUPL-001',
            owner=self.user_two,
            name='Disease B',
            category='Category B',
        )

        self.assertEqual(Disease.objects.filter(disease_id='DUPL-001').count(), 2)

    def test_same_owner_duplicate_disease_id_fails(self):
        Disease.objects.create(
            disease_id='OWNER-001',
            owner=self.user_one,
            name='Disease A',
            category='Category A',
        )

        with self.assertRaises(IntegrityError):
            Disease.objects.create(
                disease_id='OWNER-001',
                owner=self.user_one,
                name='Disease B',
                category='Category B',
            )


class ImagePathSafetyTests(TestCase):
    @override_settings(MEDIA_ROOT='')
    @mock.patch('pathology_app.api.utils.gemini_client.models.generate_content')
    def test_generated_image_path_stays_within_media_root(self, mock_generate):
        class DummyImage:
            def save(self, path):
                self.saved_path = path

        class DummyPart:
            inline_data = True

            def __init__(self, image):
                self._image = image

            def as_image(self):
                return self._image

        class DummyContent:
            def __init__(self, image):
                self.parts = [DummyPart(image)]

        class DummyCandidate:
            def __init__(self, image):
                self.content = DummyContent(image)

        class DummyResponse:
            def __init__(self, image):
                self.candidates = [DummyCandidate(image)]

        image = DummyImage()
        mock_generate.return_value = DummyResponse(image)

        with tempfile.TemporaryDirectory() as temp_media:
            with override_settings(MEDIA_ROOT=temp_media):
                path = create_disease_image_with_nanobanana('../../etc/passwd\\..\\evil')

        generated_root = os.path.join(temp_media, 'generated')
        self.assertTrue(path.startswith(generated_root))
        self.assertEqual(os.path.commonpath([path, generated_root]), generated_root)


class QuizAttemptApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user_one = User.objects.create_user(username='quiz_owner', email='quiz_owner@example.com', password='StrongPassword#2026')
        self.user_two = User.objects.create_user(username='quiz_other', email='quiz_other@example.com', password='StrongPassword#2026')

        self.disease = Disease.objects.create(
            disease_id='QUIZ-D-1',
            owner=self.user_one,
            name='Quiz Disease',
            category='Notfallmedizin',
        )
        self.quiz = Quiz.objects.create(disease=self.disease, title='Quiz 1')
        self.question_one = Question.objects.create(
            quiz=self.quiz,
            question='Question one',
            options=['A', 'B', 'C', 'D'],
            correct_index=1,
            explanation='Because B',
        )
        self.question_two = Question.objects.create(
            quiz=self.quiz,
            question='Question two',
            options=['A', 'B', 'C', 'D'],
            correct_index=0,
            explanation='Because A',
        )

    def test_complete_attempt_persists_score_and_total(self):
        self.client.force_authenticate(user=self.user_one)

        start = self.client.post(f'/api/quizzes/{self.quiz.id}/attempts/', format='json')
        self.assertEqual(start.status_code, 201)
        attempt_id = start.data['id']

        answer_one = self.client.post(
            f'/api/attempts/{attempt_id}/answer/',
            {'question_id': self.question_one.id, 'selected_index': 1},
            format='json',
        )
        self.assertEqual(answer_one.status_code, 201)
        self.assertTrue(answer_one.data['is_correct'])

        answer_two = self.client.post(
            f'/api/attempts/{attempt_id}/answer/',
            {'question_id': self.question_two.id, 'selected_index': 3},
            format='json',
        )
        self.assertEqual(answer_two.status_code, 201)
        self.assertFalse(answer_two.data['is_correct'])

        completed = self.client.post(f'/api/attempts/{attempt_id}/complete/', format='json')
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data['score'], 1)
        self.assertEqual(completed.data['total'], 2)
        self.assertIsNotNone(completed.data['completed_at'])

    def test_attempt_history_is_owner_scoped(self):
        user_one_attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.user_one)
        user_two_attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.user_two)

        self.client.force_authenticate(user=self.user_one)
        response = self.client.get(f'/api/attempts/?disease={self.disease.disease_id}')

        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.data}
        self.assertIn(user_one_attempt.id, ids)
        self.assertNotIn(user_two_attempt.id, ids)

    def test_cross_user_answer_submission_is_forbidden(self):
        attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.user_one)

        self.client.force_authenticate(user=self.user_two)
        response = self.client.post(
            f'/api/attempts/{attempt.id}/answer/',
            {'question_id': self.question_one.id, 'selected_index': 1},
            format='json',
        )
        self.assertEqual(response.status_code, 403)
