from typing import Literal

from django.contrib.auth import get_user_model
from ninja import Router, Schema
from ninja.responses import Status

router = Router()


class SignupRequestSchema(Schema):
    email: str
    password: str
    first_name: str
    insurance_tier: Literal['Bronze', 'Silver', 'Gold']


class SignupResponseSchema(Schema):
    email: str
    first_name: str
    insurance_tier: str


class SignupErrorSchema(Schema):
    detail: str


@router.post('/signup', response={201: SignupResponseSchema, 409: SignupErrorSchema})
def signup(request, payload: SignupRequestSchema):
    user_model = get_user_model()

    if user_model.objects.filter(email=payload.email).exists():
        return Status(409, {'detail': 'A user with that email already exists.'})

    user = user_model.objects.create_user(
        username=payload.email,
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        insurance_tier=payload.insurance_tier,
    )

    return Status(201, SignupResponseSchema(
        email=user.email,
        first_name=user.first_name,
        insurance_tier=user.insurance_tier,
    ))
