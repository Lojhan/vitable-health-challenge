We are linking the AI to the scheduling models using standard RRULE calendar conventions.

Tasks:

In chatbot/features/scheduling/, write tests for tools:

check_availability(date_range_str) -> returns available slots, parsing existing RRULEs to avoid conflicts.

book_appointment(user_id, time_slot, rrule_str=None, symptoms_summary, appointment_reason) -> creates an Appointment.

Add owner-scoped tools list_my_appointments(user_id), cancel_user_appointment(user_id, appointment_id), and update_user_appointment(user_id, appointment_id, ...).

Add resolve_datetime_reference(datetime_reference) so the agent can convert inputs like "tomorrow" or "next monday" to UTC before checking availability/booking.

Use python-dateutil (install via CLI) to handle RRULE parsing.

Register these tools with the OpenRouterAgent. Write an integration test where the mocked LLM calls both.

Save this prompt to .github/prompts/07-scheduling.md and execute Memory Check.
