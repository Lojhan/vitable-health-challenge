from chatbot.features.ai.base import UserProfileSchema
from chatbot.features.ai.openrouter_agent import OpenRouterAgent
from chatbot.features.core.constants import InsuranceTier


def build_user_profile(*, first_name: str, insurance_tier: InsuranceTier) -> UserProfileSchema:
    return UserProfileSchema(
        first_name=first_name,
        insurance_tier=insurance_tier,
    )


def build_openrouter_agent(
    *,
    user_profile: UserProfileSchema | None = None,
    first_name: str | None = None,
    insurance_tier: InsuranceTier | None = None,
    user_id: int | None = None,
) -> OpenRouterAgent:
    resolved_user_profile = user_profile
    if resolved_user_profile is None and first_name is not None and insurance_tier is not None:
        resolved_user_profile = UserProfileSchema(
            first_name=first_name,
            insurance_tier=insurance_tier,
        )

    return OpenRouterAgent(user_profile=resolved_user_profile, user_id=user_id)
