from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


class RegistrationTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.register_url = '/api/register/'
		self.User = get_user_model()

	def test_register_rejects_weak_password(self):
		response = self.client.post(
			self.register_url,
			{
				'username': 'weak_user',
				'email': 'weak@example.com',
				'password': '12345',
				'confirmed_password': '12345',
			},
			format='json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn('password', response.data)

	def test_register_accepts_strong_password(self):
		response = self.client.post(
			self.register_url,
			{
				'username': 'strong_user',
				'email': 'strong@example.com',
				'password': 'StrongPassword#2026',
				'confirmed_password': 'StrongPassword#2026',
			},
			format='json',
		)

		self.assertEqual(response.status_code, 201)
		self.assertTrue(self.User.objects.filter(username='strong_user').exists())

	def test_duplicate_email_returns_generic_error(self):
		self.User.objects.create_user(username='existing', email='dup@example.com', password='StrongPass#2026')

		response = self.client.post(
			self.register_url,
			{
				'username': 'another',
				'email': 'dup@example.com',
				'password': 'StrongPassword#2026',
				'confirmed_password': 'StrongPassword#2026',
			},
			format='json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			str(response.data.get('detail')),
			'Unable to process registration with the provided credentials.',
		)


class LogoutAndRefreshTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.user = get_user_model().objects.create_user(
			username='logout_user',
			email='logout@example.com',
			password='StrongPassword#2026',
		)

	def test_logout_blacklists_refresh_token(self):
		refresh = str(RefreshToken.for_user(self.user))
		self.client.cookies['refresh_token'] = refresh
		self.client.force_authenticate(user=self.user)

		logout_response = self.client.post('/api/logout/', format='json')
		self.assertEqual(logout_response.status_code, 200)

		self.client.force_authenticate(user=None)
		self.client.cookies['refresh_token'] = refresh
		refresh_response = self.client.post('/api/token/refresh/', format='json')
		self.assertEqual(refresh_response.status_code, 401)


class LoginThrottleTests(TestCase):
	def setUp(self):
		cache.clear()
		self.client = APIClient()
		get_user_model().objects.create_user(
			username='throttle_user',
			email='throttle@example.com',
			password='StrongPassword#2026',
		)

	def test_login_rate_limit_returns_429(self):
		payload = {'username': 'throttle_user', 'password': 'wrong-password'}
		last_response = None
		for _ in range(11):
			last_response = self.client.post('/api/login/', payload, format='json')

		self.assertIsNotNone(last_response)
		self.assertEqual(last_response.status_code, 429)
