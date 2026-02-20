from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from unittest import mock


class GenerateDiseasePromptTests(TestCase):
    """Ensure that the generation endpoint works with a prompt string."""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='pass')
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
