Make the chat feel more natural when users send several short messages in a row.

Goal:
Users should be able to type quickly (for example: "i", "have", "fever") and still get one good response based on the full idea, not awkward partial replies.

What to implement:

On the backend, add a short debounce in /api/chat per session. Store each user message right away, then briefly wait and group pending user messages that arrived in the same burst.

Before calling the AI, split data into:
- confirmed history (up to the last assistant message)
- pending user messages (after the last assistant message)

If a request is already covered by a newer request in the same burst, do not generate another assistant answer. Return a no-op SSE token like <MERGED_IN_PREVIOUS_RESPONSE>.

When multiple pending user messages exist, merge them into one natural prompt. Do not send numbered meta text. "i" + "have" + "fever" should become "i have fever".

If pending input is still only incomplete connective fragments, defer the AI call and return the no-op token until enough context arrives.

On the frontend, handle the no-op token by removing any temporary assistant placeholder created for superseded requests.

Also add a similar short burst grouping on the frontend before sending requests. If the user sends messages quickly, group them in one outbound request and join each message with a separator token (for example "i<USER_MESSAGE_BURST_SEPARATOR>have<USER_MESSAGE_BURST_SEPARATOR>fever") so backend can restore the original message boundaries.

Also keep sending enabled while streaming. Do not block the user from sending follow-up messages.

Save this prompt to .github/prompts/12-message-coalescing-debounce.md and execute Memory Check.
