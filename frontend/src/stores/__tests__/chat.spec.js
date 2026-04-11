import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { apiClient } from '../../lib/apiClient'
import { useAuthStore } from '../../features/auth/stores/auth'
import { useChatStore } from '../chat'

const FRONTEND_BURST_SEPARATOR_TOKEN = '<USER_MESSAGE_BURST_SEPARATOR>'

function buildStreamingBody(events) {
  const encoder = new TextEncoder()
  let index = 0

  return {
    getReader() {
      return {
        async read() {
          if (index >= events.length) {
            return { done: true, value: undefined }
          }

          const value = encoder.encode(events[index])
          index += 1
          return { done: false, value }
        },
      }
    },
  }
}

describe('chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sends only the current message and persists session id from backend', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'

    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        headers: {
          get(name) {
            if (name === 'X-Chat-Session-Id') {
              return '42'
            }
            return null
          },
        },
        body: buildStreamingBody(['data: hello\n\n']),
      })
      .mockResolvedValueOnce({
        ok: true,
        headers: {
          get() {
            return null
          },
        },
        body: buildStreamingBody(['data: second\n\n']),
      })

    const chatStore = useChatStore()
    await chatStore.sendMessage('first prompt')

    expect(chatStore.sessionId).toBe(42)
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('/api/chat'),
      expect.objectContaining({
        body: JSON.stringify({
          message: 'first prompt',
          session_id: null,
        }),
      }),
    )

    await chatStore.sendMessage('second prompt')

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/api/chat'),
      expect.objectContaining({
        body: JSON.stringify({
          message: 'second prompt',
          session_id: 42,
        }),
      }),
    )

    chatStore.clearChat()
    expect(chatStore.sessionId).toBe(null)
  })

  it('groups quick consecutive sends into one token-delimited request', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'

    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        headers: {
          get(name) {
            if (name === 'X-Chat-Session-Id') {
              return '77'
            }
            return null
          },
        },
        body: buildStreamingBody(['data: grouped\n\n']),
      })

    const chatStore = useChatStore()
    const firstSend = chatStore.sendMessage('i')
    const secondSend = chatStore.sendMessage('have fever')
    await Promise.all([firstSend, secondSend])

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/chat'),
      expect.objectContaining({
        body: JSON.stringify({
            message: `i${FRONTEND_BURST_SEPARATOR_TOKEN}have fever`,
          session_id: null,
        }),
      }),
    )

    const assistantMessages = chatStore.messages.filter((message) => message.role === 'assistant')
    expect(assistantMessages).toHaveLength(1)
    expect(assistantMessages[0].content).toBe('grouped')
  })

  it('streams chunks into a single assistant message without placeholder overload', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: {
        get() {
          return null
        },
      },
      body: buildStreamingBody([
        'data: First message.\n\n',
        'data: Second message.\n\n',
      ]),
    })

    const chatStore = useChatStore()
    const pending = chatStore.sendMessage('hello')

    await pending

    const assistantMessages = chatStore.messages.filter(
      (message) => message.role === 'assistant',
    )
    expect(assistantMessages).toHaveLength(1)
    expect(assistantMessages[0].content).toBe('First message.Second message.')
  })

  it('preserves multiline content within a single SSE event', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: {
        get() {
          return null
        },
      },
      body: buildStreamingBody([
        'data: I found several available appointment slots:\n'
          + 'data: - 9:00 AM\n'
          + 'data: - 10:00 AM\n\n',
      ]),
    })

    const chatStore = useChatStore()
    await chatStore.sendMessage('what availability do you have by next week?')

    const assistantMessages = chatStore.messages.filter(
      (message) => message.role === 'assistant',
    )
    expect(assistantMessages).toHaveLength(1)
    expect(assistantMessages[0].content).toBe(
      'I found several available appointment slots:\n- 9:00 AM\n- 10:00 AM',
    )
  })

  it('retries chat request after access token refresh on 401', async () => {
    const authStore = useAuthStore()
    authStore.token = 'expired-token'
    authStore.refreshToken = 'valid-refresh-token'

    const refreshSpy = vi
      .spyOn(authStore, 'refreshAccessToken')
      .mockImplementation(async () => {
        authStore.token = 'new-access-token'
        return true
      })

    const fetchMock = vi.spyOn(globalThis, 'fetch')
    fetchMock
      .mockResolvedValueOnce({
        status: 401,
        ok: false,
        headers: { get: () => null },
        body: null,
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        headers: { get: () => '99' },
        body: buildStreamingBody(['data: retried successfully\n\n']),
      })

    const chatStore = useChatStore()
    await chatStore.sendMessage('hello after expiry')

    expect(refreshSpy).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(chatStore.sessionId).toBe(99)
    const assistantMessages = chatStore.messages.filter(
      (message) => message.role === 'assistant',
    )
    expect(assistantMessages.at(-1)?.content).toBe('retried successfully')
  })

  it('logs out and clears chat when refresh fails', async () => {
    const authStore = useAuthStore()
    authStore.token = 'expired-token'
    authStore.refreshToken = 'expired-refresh-token'

    vi.spyOn(authStore, 'refreshAccessToken').mockResolvedValue(false)

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      status: 401,
      ok: false,
      headers: { get: () => null },
      body: null,
    })

    const chatStore = useChatStore()
    await chatStore.sendMessage('will fail refresh')

    expect(authStore.token).toBe('')
    expect(authStore.refreshToken).toBe('')
    expect(chatStore.messages).toEqual([])
    expect(chatStore.sessionId).toBe(null)
    expect(chatStore.streamError).toBe('')
  })

  it('syncs server history on startup when sync token changed', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'

    vi.spyOn(apiClient, 'get')
      .mockResolvedValueOnce({
        data: {
          latest_updated_at: '2026-04-09T12:00:00Z',
          session_count: 1,
          message_count: 2,
        },
      })
      .mockResolvedValueOnce({
        data: {
          sessions: [
            {
              id: 55,
              title: 'my knee hurts',
              created_at: '2026-04-09T11:00:00Z',
              updated_at: '2026-04-09T12:00:00Z',
              messages: [
                { role: 'user', content: 'my knee hurts', created_at: '2026-04-09T11:00:01Z' },
                { role: 'assistant', content: 'tell me more', created_at: '2026-04-09T11:00:02Z' },
              ],
            },
          ],
        },
      })

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      headers: { get: () => null },
      body: buildStreamingBody(['data: hello there\n\n']),
    })

    const chatStore = useChatStore()
    await chatStore.synchronizeHistoryOnStartup({ force: true })

    expect(chatStore.conversationSummaries).toHaveLength(1)
    expect(chatStore.activeConversationId).toBe('session-55')
    expect(chatStore.sessionId).toBe(55)
    expect(chatStore.messages.some((message) => message.content.includes('knee'))).toBe(true)
  })

  it('switches to a selected past conversation and restores its session id', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'

    const fetchMock = vi.spyOn(globalThis, 'fetch')
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        headers: { get: (name) => (name === 'X-Chat-Session-Id' ? '7' : null) },
        body: buildStreamingBody(['data: first reply\n\n']),
      })
      .mockResolvedValueOnce({
        ok: true,
        headers: { get: (name) => (name === 'X-Chat-Session-Id' ? '13' : null) },
        body: buildStreamingBody(['data: second reply\n\n']),
      })

    const chatStore = useChatStore()
    await chatStore.sendMessage('conversation one')
    const firstConversationId = chatStore.activeConversationId

    chatStore.startNewConversation('conversation two')
    await chatStore.sendMessage('conversation two')

    chatStore.selectConversation(firstConversationId)
    expect(chatStore.sessionId).toBe(7)
    expect(chatStore.messages.some((message) => message.content.includes('conversation one'))).toBe(true)
  })

  it('clears active server-backed conversation and calls delete endpoint', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'

    vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: { deleted: true } })

    const fetchMock = vi.spyOn(globalThis, 'fetch')
    fetchMock.mockResolvedValueOnce({
      ok: true,
      headers: { get: (name) => (name === 'X-Chat-Session-Id' ? '101' : null) },
      body: buildStreamingBody(['data: cleared\n\n']),
    })

    const chatStore = useChatStore()
    await chatStore.sendMessage('persist this')
    chatStore.clearChat()

    expect(apiClient.delete).toHaveBeenCalledWith('/api/chat/sessions/101')
    expect(chatStore.activeConversationId).toBe(null)
    expect(chatStore.sessionId).toBe(null)
    expect(chatStore.messages).toEqual([])
  })
})
