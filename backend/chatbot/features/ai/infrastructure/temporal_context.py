from datetime import datetime

from chatbot.features.scheduling.infrastructure.time_context import build_temporal_anchor_lines


def build_temporal_context_lines(reference: datetime) -> str:
    return build_temporal_anchor_lines(reference)
