from dataclasses import asdict

import pytest

from chatbot.features.users.application.signup import (
    DuplicateEmailError,
    SignUpUserCommand,
    UserSignedUpEvent,
)
from chatbot.features.users.application.use_cases.sign_up_user import SignUpUserUseCase


class FakeCreatedUser:
    def __init__(self, *, user_id: int, email: str, first_name: str, insurance_tier: str):
        self.id = user_id
        self.email = email
        self.first_name = first_name
        self.insurance_tier = insurance_tier


class FakeSignUpUnitOfWork:
    def __init__(self, *, existing_emails: set[str] | None = None):
        self.existing_emails = existing_emails or set()
        self.created_users: list[FakeCreatedUser] = []
        self.recorded_events: list[UserSignedUpEvent] = []
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    def email_exists(self, email: str) -> bool:
        return email in self.existing_emails

    def create_user(self, *, email: str, password: str, first_name: str, insurance_tier: str):
        _ = password
        user = FakeCreatedUser(
            user_id=1,
            email=email,
            first_name=first_name,
            insurance_tier=insurance_tier,
        )
        self.created_users.append(user)
        return user

    def record_event(self, event: UserSignedUpEvent) -> None:
        self.recorded_events.append(event)


def test_signup_use_case_creates_user_and_records_domain_event():
    uow = FakeSignUpUnitOfWork()
    use_case = SignUpUserUseCase(uow)

    result = use_case.execute(
        SignUpUserCommand(
            email='new.user@example.com',
            password='secure-pass',
            first_name='Alice',
            insurance_tier='Silver',
        )
    )

    assert uow.entered is True
    assert uow.exited is True
    assert result.email == 'new.user@example.com'
    assert result.first_name == 'Alice'
    assert result.insurance_tier == 'Silver'
    assert len(uow.recorded_events) == 1
    assert asdict(uow.recorded_events[0]) == {
        'user_id': 1,
        'email': 'new.user@example.com',
        'first_name': 'Alice',
        'insurance_tier': 'Silver',
    }


def test_signup_use_case_rejects_duplicate_email_without_recording_event():
    uow = FakeSignUpUnitOfWork(existing_emails={'existing@example.com'})
    use_case = SignUpUserUseCase(uow)

    with pytest.raises(DuplicateEmailError):
        use_case.execute(
            SignUpUserCommand(
                email='existing@example.com',
                password='secure-pass',
                first_name='Alice',
                insurance_tier='Silver',
            )
        )

    assert uow.created_users == []
    assert uow.recorded_events == []
