We are implementing context injection and financial logic.

Tasks:

In chatbot/features/billing/, write a TDD-backed function calculate_visit_cost(insurance_tier, visit_type) -> float. (Bronze=$150, Silver=$75, Gold=$20).
In chatbot/features/ai/:

Update OpenRouterAgent to accept a User profile during instantiation and inject first_name and insurance_tier into the system prompt. Test this injection.
Register calculate_visit_cost as a tool using a Pydantic schema in the agent interface.

Save this prompt to .github/prompts/05-context-and-tiers.md and execute Memory Check.
