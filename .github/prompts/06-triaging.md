We are adding clinical boundaries to the agent.

Tasks:

Update the OpenRouterAgent system prompt to enforce Manchester Triage System logic (empathy, no diagnosing).

Instruct the agent to output the exact string <EMERGENCY_OVERRIDE> if life-threatening symptoms are detected.

Add a strict out-of-scope boundary so non-healthcare/programming requests are refused with a fixed safe response.

Write an evaluation test using a mocked user prompt ("I have severe chest pain") asserting the backend catches the <EMERGENCY_OVERRIDE> tag.

Save this prompt to .github/prompts/06-triaging.md and execute Memory Check.
