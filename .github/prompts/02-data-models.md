We are building the data foundations in PostgreSQL.

Tasks:

In chatbot/features/users/, write tests for a Custom User model containing: first_name, insurance_tier (Bronze, Silver, Gold), and a medical_history field utilizing Django's JSONField (to store flexible, semi-structured health data context). Make tests pass.

In chatbot/features/scheduling/, write tests for an Appointment model supporting standard calendar conventions by including an rrule string field. Make tests pass.

In chatbot/features/chat/: ChatSession (owned by user) and ChatMessage (session, role=user/assistant, content, timestamps), with tests. Make tests pass.

Create and apply migrations.

Save this prompt to .github/prompts/02-data-models.md and execute Memory Check.
