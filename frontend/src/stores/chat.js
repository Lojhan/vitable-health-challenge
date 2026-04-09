import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { apiClient, getApiBaseUrl } from '../lib/apiClient'
import { useAuthStore } from './auth'

const TYPEWRITER_DELAY_MS = 16
const FRONTEND_BURST_WINDOW_MS = 1000
const FRONTEND_BURST_SEPARATOR_TOKEN = '<USER_MESSAGE_BURST_SEPARATOR>'
const MERGED_IN_PREVIOUS_RESPONSE_TOKEN = '<MERGED_IN_PREVIOUS_RESPONSE>'
let messageCounter = 0
let conversationCounter = 0

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function buildMessageId() {
  messageCounter += 1
  return `msg-${messageCounter}`
}

function buildConversationId() {
  conversationCounter += 1
  return `conv-${Date.now()}-${conversationCounter}`
}

function buildSessionConversationId(nextSessionId) {
  return `session-${nextSessionId}`
}

function buildConversationTitle(prompt) {
  const normalized = (prompt ?? '').trim().replace(/\s+/g, ' ')
  if (!normalized) {
    return 'New conversation'
  }
  return normalized.slice(0, 42)
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const conversations = ref([])
  const activeConversationId = ref(null)
  const activeStreamCount = ref(0)
  const isStreaming = computed(() => activeStreamCount.value > 0)
  const isSyncingHistory = ref(false)
  const emergencyOverride = ref(false)
  const streamError = ref('')
  const sessionId = ref(null)
  const authStore = useAuthStore()

  const pendingPromptBurst = ref([])
  let promptBurstTimerId = null
  let isSendingPromptBurst = false
  let promptBurstAssistantMessage = null

  const conversationSummaries = computed(() => (
    conversations.value
      .map((conversation) => ({
        id: conversation.id,
        title: conversation.title,
        createdAt: conversation.createdAt,
        updatedAt: conversation.updatedAt,
      }))
      .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
  ))

  function computeLocalSyncToken() {
    const latestUpdatedAt = conversations.value.reduce((latest, conversation) => {
      if (!latest) {
        return conversation.updatedAt
      }
      return new Date(conversation.updatedAt) > new Date(latest)
        ? conversation.updatedAt
        : latest
    }, null)

    const messageCount = conversations.value.reduce(
      (total, conversation) => total + (conversation.messages?.length ?? 0),
      0,
    )

    return [
      latestUpdatedAt ?? 'none',
      String(conversations.value.length),
      String(messageCount),
    ].join(':')
  }

  function buildServerSyncToken(payload) {
    return [
      payload.latest_updated_at ?? 'none',
      String(payload.session_count ?? 0),
      String(payload.message_count ?? 0),
    ].join(':')
  }

  function setCurrentConversationById(nextConversationId) {
    const selectedConversation = conversations.value.find(
      (conversation) => conversation.id === nextConversationId,
    )

    if (!selectedConversation) {
      return
    }

    activeConversationId.value = selectedConversation.id
    messages.value = selectedConversation.messages
    sessionId.value = selectedConversation.sessionId ?? null
  }

  function setLatestConversationAsActive() {
    if (conversations.value.length === 0) {
      activeConversationId.value = null
      messages.value = []
      sessionId.value = null
      return
    }

    const latestConversation = [...conversations.value].sort(
      (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt),
    )[0]

    setCurrentConversationById(latestConversation.id)
  }

  function applyServerHistory(serverSessions) {
    const previousActiveConversationId = activeConversationId.value

    conversations.value = serverSessions.map((session) => ({
      id: buildSessionConversationId(session.id),
      title: session.title,
      createdAt: session.created_at,
      updatedAt: session.updated_at,
      sessionId: session.id,
      messages: session.messages.map((message) => ({
        id: buildMessageId(),
        role: message.role,
        content: message.content,
      })),
    }))

    if (
      previousActiveConversationId
      && conversations.value.some((conversation) => conversation.id === previousActiveConversationId)
    ) {
      setCurrentConversationById(previousActiveConversationId)
      return
    }

    setLatestConversationAsActive()
  }

  function updateActiveConversationMeta(nextTitle) {
    const activeConversation = conversations.value.find(
      (conversation) => conversation.id === activeConversationId.value,
    )

    if (!activeConversation) {
      return
    }

    activeConversation.title = nextTitle || activeConversation.title
    activeConversation.updatedAt = new Date().toISOString()
    activeConversation.messages = messages.value
    activeConversation.sessionId = sessionId.value
  }

  function syncSessionIdToActiveConversation(nextSessionId) {
    const activeConversation = conversations.value.find(
      (conversation) => conversation.id === activeConversationId.value,
    )

    sessionId.value = nextSessionId

    if (!activeConversation) {
      return
    }

    const permanentId = buildSessionConversationId(nextSessionId)
    const duplicateConversation = conversations.value.find(
      (conversation) => conversation.id === permanentId,
    )

    if (duplicateConversation && duplicateConversation !== activeConversation) {
      conversations.value = conversations.value.filter(
        (conversation) => conversation.id !== duplicateConversation.id,
      )
    }

    activeConversation.id = permanentId
    activeConversation.sessionId = nextSessionId
    activeConversation.updatedAt = new Date().toISOString()
    activeConversationId.value = permanentId
  }

  async function fetchWithAuthRecovery(requestFn) {
    try {
      return await requestFn()
    } catch (error) {
      if (error.response?.status !== 401) {
        throw error
      }

      const refreshed = await authStore.refreshAccessToken()
      if (!refreshed) {
        throw error
      }

      return requestFn()
    }
  }

  async function synchronizeHistoryOnStartup({ force = false } = {}) {
    if (!authStore.token) {
      return
    }

    isSyncingHistory.value = true

    try {
      const syncResponse = await fetchWithAuthRecovery(() => apiClient.get('/api/chat/history-sync'))
      const serverToken = buildServerSyncToken(syncResponse.data)
      const localToken = computeLocalSyncToken()

      if (force || serverToken !== localToken) {
        const historyResponse = await fetchWithAuthRecovery(() => apiClient.get('/api/chat/history'))
        const serverSessions = historyResponse.data?.sessions

        if (Array.isArray(serverSessions)) {
          applyServerHistory(serverSessions)
        }
      }
    } catch (_error) {
      streamError.value = 'Unable to sync chat history from the server.'
    } finally {
      isSyncingHistory.value = false
    }
  }

  function startNewConversation(initialPrompt = '') {
    const now = new Date().toISOString()
    const conversation = {
      id: buildConversationId(),
      title: buildConversationTitle(initialPrompt),
      createdAt: now,
      updatedAt: now,
      sessionId: null,
      messages: [],
    }

    conversations.value.unshift(conversation)
    activeConversationId.value = conversation.id
    messages.value = conversation.messages
    sessionId.value = null
    streamError.value = ''
    emergencyOverride.value = false
  }

  function selectConversation(conversationId) {
    const selectedConversation = conversations.value.find(
      (conversation) => conversation.id === conversationId,
    )

    if (!selectedConversation) {
      return
    }

    activeConversationId.value = selectedConversation.id
    messages.value = selectedConversation.messages
    sessionId.value = selectedConversation.sessionId ?? null
    streamError.value = ''
    emergencyOverride.value = false
  }

  function resetEmergencyState() {
    emergencyOverride.value = false
  }

  function appendMessage(role, content) {
    messages.value.push({
      id: buildMessageId(),
      role,
      content,
    })

    if (activeConversationId.value) {
      updateActiveConversationMeta()
    }
  }

  async function streamWithTypewriter(assistantMessage, chunk) {
    for (const char of chunk) {
      assistantMessage.content += char
      await delay(TYPEWRITER_DELAY_MS)
    }
  }

  function resolveBurstItems(items) {
    items.forEach((item) => item.resolve())
  }

  function clearPromptBurstState() {
    if (promptBurstTimerId !== null) {
      clearTimeout(promptBurstTimerId)
      promptBurstTimerId = null
    }

    resolveBurstItems(pendingPromptBurst.value)
    pendingPromptBurst.value = []
    isSendingPromptBurst = false
    promptBurstAssistantMessage = null
  }

  function ensurePromptBurstAssistantMessage() {
    if (promptBurstAssistantMessage) {
      return promptBurstAssistantMessage
    }

    promptBurstAssistantMessage = {
      id: buildMessageId(),
      role: 'assistant',
      content: '...',
    }
    messages.value.push(promptBurstAssistantMessage)
    updateActiveConversationMeta()
    return promptBurstAssistantMessage
  }

  function schedulePromptBurstSend() {
    if (promptBurstTimerId !== null) {
      clearTimeout(promptBurstTimerId)
    }

    promptBurstTimerId = setTimeout(() => {
      promptBurstTimerId = null
      void flushPromptBurst()
    }, FRONTEND_BURST_WINDOW_MS)
  }

  async function flushPromptBurst() {
    if (isSendingPromptBurst) {
      if (pendingPromptBurst.value.length > 0) {
        schedulePromptBurstSend()
      }
      return
    }

    const burstItems = [...pendingPromptBurst.value]
    if (burstItems.length === 0) {
      return
    }

    pendingPromptBurst.value = []
    const prompt = burstItems.map((item) => item.prompt).join(FRONTEND_BURST_SEPARATOR_TOKEN)
    let assistantMessage = ensurePromptBurstAssistantMessage()

    activeStreamCount.value += 1
    isSendingPromptBurst = true

    try {
      const buildRequest = () => fetch(`${getApiBaseUrl()}/api/chat`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: prompt,
          session_id: sessionId.value,
        }),
      })

      let response = await buildRequest()

      if (response.status === 401) {
        const refreshed = await authStore.refreshAccessToken()
        if (!refreshed) {
          clearChat()
          authStore.logout()
          streamError.value = 'Your session expired. Please login again.'
          resolveBurstItems(burstItems)
          return
        }
        response = await buildRequest()
      }

      const responseSessionId = response.headers.get('X-Chat-Session-Id')
      if (responseSessionId) {
        syncSessionIdToActiveConversation(Number.parseInt(responseSessionId, 10))
        updateActiveConversationMeta()
      }

      if (!response.ok || !response.body) {
        throw new Error('Unable to stream chat response.')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      let receivedAtLeastOneChunk = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''

        for (const event of events) {
          const lines = event
            .split('\n')
            .filter((candidateLine) => candidateLine.startsWith('data: '))

          if (lines.length === 0) {
            continue
          }

          receivedAtLeastOneChunk = true
          const chunk = lines.map((line) => line.slice(6)).join('\n')

          if (chunk === '<EMERGENCY_OVERRIDE>') {
            emergencyOverride.value = true
            assistantMessage.content =
              'Emergency signal received. Please call emergency services now.'
            updateActiveConversationMeta()
            resolveBurstItems(burstItems)
            return
          }

          if (chunk === MERGED_IN_PREVIOUS_RESPONSE_TOKEN) {
            if (assistantMessage.content === '...') {
              messages.value = messages.value.filter((message) => message.id !== assistantMessage.id)
              updateActiveConversationMeta()
            }
            resolveBurstItems(burstItems)
            return
          }

          if (assistantMessage.content === '...') {
            assistantMessage.content = ''
          } else if (assistantMessage.content.trim().length > 0) {
            assistantMessage = {
              id: buildMessageId(),
              role: 'assistant',
              content: '',
            }
            messages.value.push(assistantMessage)
            promptBurstAssistantMessage = assistantMessage
            updateActiveConversationMeta()
          }

          await streamWithTypewriter(assistantMessage, chunk)
          updateActiveConversationMeta()
        }
      }

      if (!receivedAtLeastOneChunk && assistantMessage.content === '...') {
        assistantMessage.content =
          'I could not generate a response. Please try again.'
        updateActiveConversationMeta()
      }

      resolveBurstItems(burstItems)
    } catch (_error) {
      if (assistantMessage.content === '...') {
        assistantMessage.content = 'I could not generate a response. Please try again.'
        updateActiveConversationMeta()
      }
      streamError.value = 'Chat stream interrupted. Please try again.'
      resolveBurstItems(burstItems)
    } finally {
      activeStreamCount.value = Math.max(0, activeStreamCount.value - 1)
      isSendingPromptBurst = false
      promptBurstAssistantMessage = null
      updateActiveConversationMeta()

      if (pendingPromptBurst.value.length > 0) {
        schedulePromptBurstSend()
      }
    }
  }

  watch(
    () => authStore.token,
    (nextToken) => {
      if (!nextToken) {
        conversations.value = []
        messages.value = []
        activeConversationId.value = null
        sessionId.value = null
        streamError.value = ''
        emergencyOverride.value = false
        clearPromptBurstState()
      }
    },
  )

  async function sendMessage(prompt) {
    if (!authStore.token) {
      streamError.value = 'You need to login before chatting.'
      return
    }

    if (!activeConversationId.value) {
      startNewConversation(prompt)
    }

    streamError.value = ''
    appendMessage('user', prompt)
    updateActiveConversationMeta(buildConversationTitle(prompt))
    ensurePromptBurstAssistantMessage()

    await new Promise((resolve) => {
      pendingPromptBurst.value.push({ prompt, resolve })
      schedulePromptBurstSend()
    })
  }

  function clearChat() {
    const selectedConversation = conversations.value.find(
      (conversation) => conversation.id === activeConversationId.value,
    )
    const selectedSessionId = selectedConversation?.sessionId ?? null

    if (activeConversationId.value) {
      conversations.value = conversations.value.filter(
        (conversation) => conversation.id !== activeConversationId.value,
      )
    }

    messages.value = []
    streamError.value = ''
    sessionId.value = null
    emergencyOverride.value = false
    clearPromptBurstState()

    setLatestConversationAsActive()

    if (selectedSessionId) {
      fetchWithAuthRecovery(
        () => apiClient.delete(`/api/chat/sessions/${selectedSessionId}`),
      ).catch(() => {
        streamError.value = 'Unable to clear this conversation on the server.'
      })
    }
  }

  return {
    messages,
    conversations,
    activeConversationId,
    conversationSummaries,
    isStreaming,
    isSyncingHistory,
    emergencyOverride,
    streamError,
    sessionId,
    sendMessage,
    synchronizeHistoryOnStartup,
    startNewConversation,
    selectConversation,
    clearChat,
    resetEmergencyState,
  }
})
