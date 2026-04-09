Expose the agent via an async API stream protected by JWT.

Tasks:

Create chatbot/api.py.

Write tests for a POST /api/chat endpoint. It MUST enforce JWT authentication. If unauthenticated, return 401. If authenticated, return a StreamingHttpResponse.

Implement the endpoint. Extract the User ID from the JWT, fetch the User from the DB, and inject it into the OpenRouterAgent. Map OpenRouter chunks to SSE format.

Persist each conversation in ChatSession/ChatMessage and return session id in the response headers. Accept optional session_id in request payload to continue a previous conversation.

Add authenticated history endpoints used by the UI:
- GET /api/chat/history
- GET /api/chat/history-sync
- DELETE /api/chat/sessions/{session_id}

Save this prompt to .github/prompts/08-api-sse.md and execute Memory Check.
