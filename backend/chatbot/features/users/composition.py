from django.contrib.auth import get_user_model

from chatbot.features.users.application.use_cases.refresh_token import RefreshTokenUseCase
from chatbot.features.users.application.use_cases.sign_up_user import SignUpUserUseCase
from chatbot.features.users.infrastructure.unit_of_work.django_signup import (
    DjangoSignUpUnitOfWork,
)
from chatbot.features.users.infrastructure.unit_of_work.django_token import (
    DjangoTokenUnitOfWork,
)


def build_signup_use_case() -> SignUpUserUseCase:
    user_model = get_user_model()
    return SignUpUserUseCase(DjangoSignUpUnitOfWork(user_model))


def build_refresh_token_use_case() -> RefreshTokenUseCase:
    return RefreshTokenUseCase(DjangoTokenUnitOfWork())
