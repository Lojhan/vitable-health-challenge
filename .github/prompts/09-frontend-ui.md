Build the polished UI and Auth integration. Use CLI to install primevue and axios.

Tasks:

Create a Pinia AuthStore to handle login, store the JWT token, and attach it to API requests. Create a simple Login.vue view.

Create a Pinia ChatStore. Build ChatInterface.vue with conversation history support.

Consume the POST /api/chat SSE stream, passing the JWT in the headers. Map the stream to a reactive typewriter effect.

On startup, sync server-backed history using GET /api/chat/history-sync and GET /api/chat/history. Support creating/selecting conversations and clearing the active conversation (including DELETE /api/chat/sessions/{session_id} when applicable).

In App.vue, use auth-state conditional rendering between Login/Signup/Chat (no router required).

Add UX polish: AI branding and a dramatic visual red state when the <EMERGENCY_OVERRIDE> event occurs.

Save this prompt to .github/prompts/09-frontend-ui.md and execute Final Memory Check.
