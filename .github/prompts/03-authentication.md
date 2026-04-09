We need to secure our API using JSON Web Tokens (JWT).

Tasks:

Install JWT support for Django Ninja via CLI (e.g., django-ninja-jwt).

In chatbot/features/users/, write tests for an authentication endpoints: 

(POST /api/auth/token) that accepts credentials and returns an access and refresh token.
(POST /api/auth/refresh) that accepts a refresh token and returns a new access token.

Use username+password for token login, and keep signup/login compatibility by setting username=email when creating users.

Implement the Django Ninja endpoint to make the tests pass.

Save this prompt to .github/prompts/03-authentication.md and execute Memory Check.
