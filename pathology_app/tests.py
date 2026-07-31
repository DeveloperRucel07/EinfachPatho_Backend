import os
import tempfile
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient
from unittest import mock

from pathology_app.api.utils import create_disease_image_with_nanobanana
from pathology_app.models import Disease, Quiz, Question, QuizAttempt


class GenerateDiseasePromptTests(TestCase):
    """Ensure that the generation endpoint works with a prompt string."""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass')
        self.client.force_authenticate(self.user)

    @mock.patch('pathology_app.api.utils.create_disease_json_for_durst')
    @mock.patch('pathology_app.api.utils.find_disease_by_prompt')
    def test_prompt_generates_disease(self, mock_find, mock_create_json):
        # arrange: make the helper return a fixed disease name and JSON
        mock_find.return_value = 'Test Disease'
        mock_create_json.return_value = {
            'disease_id': 'TEST-001',
            'name': 'Test Disease',
            'image': 'https://example.com/img.png',
            'category': 'Testcat',
            'durst_data': {
                'definition': 'Definition here',
                'ursachen': {'text': 'cause', 'keywords': []},
                'risikofaktoren': [],
                'symptoms': {'list': [], 'red_flags': ''},
                'therapie_massnahmen': {
                    'immediate_actions': [],
                    'diagnostic_gold_standard': '',
                    'guideline_link': ''
                }
            },
            'quiz': [],
            'sources': []
        }

        # act
        response = self.client.post('/api/generate_disease/', {'prompt': 'anything'}, format='json')

        # assert
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['disease_id'], 'TEST-001')
        self.assertEqual(response.data['name'], 'Test Disease')
        mock_find.assert_called_once()
        mock_create_json.assert_called_once_with('Test Disease')


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

    @mock.patch('pathology_app.api.utils.find_disease_by_prompt')
    def test_generation_error_is_redacted(self, mock_find):
        mock_find.side_effect = Exception('internal-sdk-error-with-sensitive-data')

        response = self.client.post('/api/generate_disease/', {'prompt': 'something'}, format='json')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['detail'], 'AI generation failed. Please try again later.')
        self.assertNotIn('internal-sdk-error-with-sensitive-data', response.data['detail'])


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
