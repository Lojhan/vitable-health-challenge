from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from chatbot.features.core.auth_context import get_authenticated_user
from chatbot.features.core.models import OutboxMessage


@pytest.mark.django_db
def test_custom_user_persists_insurance_tier_and_medical_history():
	user_model = get_user_model()

	user = user_model.objects.create_user(
		username='jane.doe',
		password='safe-password-123',
		first_name='Jane',
		insurance_tier='Gold',
		medical_history={
			'conditions': ['asthma'],
			'allergies': ['peanuts'],
		},
	)

	assert user.first_name == 'Jane'
	assert user.insurance_tier == 'Gold'
	assert user.medical_history['conditions'] == ['asthma']


def test_custom_user_has_expected_insurance_tier_choices():
	user_model = get_user_model()
	insurance_tier_field = user_model._meta.get_field('insurance_tier')
	choices = {value for value, _label in insurance_tier_field.choices}

	assert choices == {'Bronze', 'Silver', 'Gold'}


@pytest.mark.django_db
def test_post_auth_token_returns_access_and_refresh_tokens():
	user_model = get_user_model()
	user_model.objects.create_user(
		username='auth-user',
		password='my-secure-password',
		insurance_tier='Bronze',
		medical_history={},
	)

	client = Client()
	response = client.post(
		'/api/auth/token',
		data={
			'username': 'auth-user',
			'password': 'my-secure-password',
		},
		content_type='application/json',
	)

	assert response.status_code == 200
	payload = response.json()
	assert 'access' in payload
	assert 'refresh' in payload


@pytest.mark.django_db
def test_post_auth_token_returns_401_for_invalid_credentials():
	user_model = get_user_model()
	user_model.objects.create_user(
		username='auth-user-2',
		password='my-secure-password',
		insurance_tier='Silver',
		medical_history={},
	)

	client = Client()
	response = client.post(
		'/api/auth/token',
		data={
			'username': 'auth-user-2',
			'password': 'wrong-password',
		},
		content_type='application/json',
	)

	assert response.status_code == 401


@pytest.mark.django_db
def test_post_auth_refresh_returns_new_access_and_refresh_tokens():
	user_model = get_user_model()
	user_model.objects.create_user(
		username='refresh-user',
		password='my-secure-password',
		insurance_tier='Bronze',
		medical_history={},
	)

	client = Client()
	token_response = client.post(
		'/api/auth/token',
		data={
			'username': 'refresh-user',
			'password': 'my-secure-password',
		},
		content_type='application/json',
	)
	refresh_token = token_response.json()['refresh']

	refresh_response = client.post(
		'/api/auth/refresh',
		data={'refresh': refresh_token},
		content_type='application/json',
	)

	assert refresh_response.status_code == 200
	payload = refresh_response.json()
	assert 'access' in payload
	assert 'refresh' in payload
	assert payload['refresh'] != refresh_token


@pytest.mark.django_db
def test_post_auth_refresh_returns_401_for_invalid_refresh_token():
	client = Client()
	response = client.post(
		'/api/auth/refresh',
		data={'refresh': 'invalid-refresh-token'},
		content_type='application/json',
	)

	assert response.status_code == 401


@pytest.mark.django_db
def test_invalid_refresh_token_is_logged(caplog):
	client = Client()

	with caplog.at_level('WARNING'):
		response = client.post(
			'/api/auth/refresh',
			data={'refresh': 'invalid-refresh-token'},
			content_type='application/json',
		)

	assert response.status_code == 401
	assert 'auth.refresh.invalid_token' in caplog.text


@pytest.mark.django_db
def test_get_authenticated_user_prefers_authenticated_request_user():
	user_model = get_user_model()
	user = user_model.objects.create_user(
		username='auth-context-user',
		password='safe-password-123',
		insurance_tier='Gold',
		medical_history={},
	)

	request = SimpleNamespace(
		user=SimpleNamespace(is_authenticated=True, pk=user.pk),
		headers={},
	)

	resolved_user = get_authenticated_user(request)

	assert resolved_user.pk == user.pk


@pytest.mark.django_db
def test_post_auth_signup_creates_user_and_returns_201():
	client = Client()
	response = client.post(
		'/api/auth/signup',
		data={
			'email': 'new.user@example.com',
			'password': 'secure-pass-456',
			'first_name': 'Alice',
			'insurance_tier': 'Silver',
		},
		content_type='application/json',
	)

	assert response.status_code == 201
	payload = response.json()
	assert payload['email'] == 'new.user@example.com'
	assert payload['first_name'] == 'Alice'
	assert payload['insurance_tier'] == 'Silver'
	assert 'password' not in payload


@pytest.mark.django_db
def test_post_auth_signup_persists_user_to_database():
	user_model = get_user_model()
	client = Client()
	client.post(
		'/api/auth/signup',
		data={
			'email': 'persisted@example.com',
			'password': 'secure-pass-789',
			'first_name': 'Bob',
			'insurance_tier': 'Gold',
		},
		content_type='application/json',
	)

	user = user_model.objects.get(email='persisted@example.com')
	assert user.first_name == 'Bob'
	assert user.insurance_tier == 'Gold'
	assert user.check_password('secure-pass-789')


@pytest.mark.django_db
def test_post_auth_signup_records_outbox_event():
	client = Client()
	response = client.post(
		'/api/auth/signup',
		data={
			'email': 'outbox.user@example.com',
			'password': 'secure-pass-789',
			'first_name': 'Olivia',
			'insurance_tier': 'Gold',
		},
		content_type='application/json',
	)

	assert response.status_code == 201
	outbox_message = OutboxMessage.objects.get(event_type='users.user_signed_up')
	assert outbox_message.aggregate_type == 'users.user'
	assert outbox_message.payload['email'] == 'outbox.user@example.com'
	assert outbox_message.payload['first_name'] == 'Olivia'


@pytest.mark.django_db
def test_duplicate_signup_does_not_record_outbox_event():
	user_model = get_user_model()
	user_model.objects.create_user(
		username='duplicate-outbox@example.com',
		email='duplicate-outbox@example.com',
		password='existing-pass',
		insurance_tier='Bronze',
	)

	client = Client()
	response = client.post(
		'/api/auth/signup',
		data={
			'email': 'duplicate-outbox@example.com',
			'password': 'new-pass',
			'first_name': 'Carol',
			'insurance_tier': 'Bronze',
		},
		content_type='application/json',
	)

	assert response.status_code == 409
	assert OutboxMessage.objects.count() == 0


@pytest.mark.django_db
def test_post_auth_signup_returns_409_for_duplicate_email():
	user_model = get_user_model()
	user_model.objects.create_user(
		username='duplicate@example.com',
		email='duplicate@example.com',
		password='existing-pass',
		insurance_tier='Bronze',
	)

	client = Client()
	response = client.post(
		'/api/auth/signup',
		data={
			'email': 'duplicate@example.com',
			'password': 'new-pass',
			'first_name': 'Carol',
			'insurance_tier': 'Bronze',
		},
		content_type='application/json',
	)

	assert response.status_code == 409


@pytest.mark.django_db
def test_post_auth_signup_returns_422_for_invalid_tier():
	client = Client()
	response = client.post(
		'/api/auth/signup',
		data={
			'email': 'invalid.tier@example.com',
			'password': 'secure-pass',
			'first_name': 'Dave',
			'insurance_tier': 'Platinum',
		},
		content_type='application/json',
	)

	assert response.status_code == 422


@pytest.mark.django_db
def test_post_auth_signup_returns_422_for_blank_first_name():
	client = Client()
	response = client.post(
		'/api/auth/signup',
		data={
			'email': 'blank.name@example.com',
			'password': 'secure-pass',
			'first_name': '   ',
			'insurance_tier': 'Gold',
		},
		content_type='application/json',
	)

	assert response.status_code == 422
