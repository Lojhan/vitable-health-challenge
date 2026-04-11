from chatbot.features.core.application.contracts import BaseUseCase
from chatbot.features.core.domain.validation import require_non_blank_text
from chatbot.features.scheduling.application.common import resolve_datetime_reference_value


class ResolveDatetimeReferenceUseCase(BaseUseCase):
    def execute(self, *, datetime_reference: str) -> dict:
        normalized_reference = require_non_blank_text(
            datetime_reference,
            field='datetime_reference',
        )
        return resolve_datetime_reference_value(normalized_reference)
