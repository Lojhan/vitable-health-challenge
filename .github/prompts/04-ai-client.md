We need an AI client with a generic interface, implemented for OpenRouter.
Constraint: Install the openai library via CLI. Mock external API calls in tests.

Tasks:

In chatbot/features/ai/, define a generic abstract class BaseAgentInterface requiring an async generate_response method.

Write tests for an OpenRouterAgent implementing this interface.
Require OPENROUTER_API_KEY from environment variables (or explicit constructor arg) and fail fast with a clear error when missing.

Implement the class.

Save this prompt to .github/prompts/04-ai-client.md and execute Memory Check.
