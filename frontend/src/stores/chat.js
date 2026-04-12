import { fetchEventSource } from '@microsoft/fetch-event-source'
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { apiClient, getApiBaseUrl } from '../lib/apiClient'
import { useAuthStore } from '../features/auth/stores/auth'

const FRONTEND_BURST_WINDOW_MS = 1000
const HISTORY_PAGE_SIZE = 20
const FRONTEND_BURST_SEPARATOR_TOKEN = '<USER_MESSAGE_BURST_SEPARATOR>'
const AUTH_REFRESH_FAILED_ERROR = 'AUTH_REFRESH_FAILED'
const MERGED_IN_PREVIOUS_RESPONSE_TOKEN = '<MERGED_IN_PREVIOUS_RESPONSE>'
let messageCounter = 0
let conversationCounter = 0
let streamActivityCounter = 0

const TOOL_ACTIVITY_LABELS = {
  show_providers_for_selection: 'Reviewing provider options',
  check_availability: 'Checking appointment availability',
  list_my_appointments: 'Loading your upcoming appointments',
  book_appointment: 'Preparing your booking',
  update_my_appointment: 'Updating your appointment',
  cancel_my_appointment: 'Cancelling your appointment',
  list_providers: 'Searching provider availability',
  resolve_datetime_reference: 'Normalizing the requested time window',
  calculate_visit_cost: 'Estimating visit coverage and cost',
}

function buildMessageId() {
  messageCounter += 1
  return `msg-${messageCounter}`
}

function buildConversationId() {
  conversationCounter += 1
  return `conv-${Date.now()}-${conversationCounter}`
}

function buildStreamActivityId() {
	streamActivityCounter += 1
	return `activity-${streamActivityCounter}`
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

function compareConversationsByUpdatedAt(left, right) {
  return new Date(right.updatedAt) - new Date(left.updatedAt)
}

function buildMockIsoTimestamp(offsetMs = 0) {
	return new Date(Date.now() + offsetMs).toISOString()
}

function parseProtocolLine(raw) {
  if (!raw || raw.length < 2 || raw[1] !== ':') {
    return null
  }
  const prefix = raw[0]
  const payload = raw.slice(2)
  try {
    return { prefix, payload: JSON.parse(payload) }
  } catch (_error) {
    return { prefix, payload }
  }
}

function normalizeAssistantMessageKind(rawKind) {
  const allowedKinds = new Set(['text', 'providers', 'availability', 'appointments', 'json'])
  const normalized = String(rawKind ?? 'text').trim().toLowerCase()
  return allowedKinds.has(normalized) ? normalized : 'text'
}

function stringifyStructuredContent(content) {
  if (typeof content === 'string') {
    return content
  }

  try {
    return JSON.stringify(content)
  } catch (_error) {
    return ''
  }
}

function humanizeToolActivity(toolName) {
  const normalized = String(toolName ?? '').trim()
  if (!normalized) {
    return 'Working on your request'
  }

  return TOOL_ACTIVITY_LABELS[normalized] ?? normalized.replaceAll('_', ' ')
}

function normalizeStreamActivityPayload(rawPayload, defaultPhase = 'running') {
  if (typeof rawPayload === 'string') {
    const trimmed = rawPayload.trim()
    return {
      toolCallId: '',
      toolName: '',
      label: trimmed || 'Working on your request',
      phase: defaultPhase,
      state: defaultPhase === 'completed' ? 'completed' : 'active',
    }
  }

  if (!rawPayload || typeof rawPayload !== 'object') {
    return {
      toolCallId: '',
      toolName: '',
      label: 'Working on your request',
      phase: defaultPhase,
      state: defaultPhase === 'completed' ? 'completed' : 'active',
    }
  }

  const toolName = String(rawPayload.tool_name ?? rawPayload.toolName ?? '').trim()
  const label = String(
    rawPayload.label
    ?? rawPayload.message
    ?? humanizeToolActivity(toolName),
  ).trim()

  return {
    toolCallId: String(rawPayload.tool_call_id ?? rawPayload.toolCallId ?? '').trim(),
    toolName,
    label: label || humanizeToolActivity(toolName),
    phase: String(rawPayload.phase ?? defaultPhase).trim() || defaultPhase,
    state: String(rawPayload.state ?? (defaultPhase === 'completed' ? 'completed' : 'active')).trim()
      || (defaultPhase === 'completed' ? 'completed' : 'active'),
  }
}

/**
 * Processes a single parsed data chunk from the SSE stream.
 * Returns a signal object: { earlyReturn: true } when the caller must stop
 * processing and return immediately (emergency or burst-merged).
 */
function resolveStructuredMessageState(rawResult) {
  if (!rawResult || typeof rawResult !== 'object') {
    return 'final'
  }

  const normalized = String(rawResult.ui_state ?? 'final').trim().toLowerCase()
  if (['skeleton', 'partial', 'final', 'error'].includes(normalized)) {
    return normalized
  }

  return 'final'
}

function processStreamChunk(
  chunk,
  {
    ensureAssistantMessage,
    updateMeta,
    onEarlyReturn,
    emergencyRef,
    recordStreamActivity,
    completeStreamActivity,
    clearStreamActivities,
  },
) {
  if (chunk === MERGED_IN_PREVIOUS_RESPONSE_TOKEN) {
    clearStreamActivities()
    onEarlyReturn()
    return { earlyReturn: true }
  }

  const proto = parseProtocolLine(chunk)

  if (!proto) {
    // Drop SSE comment lines (heartbeat etc.) that leaked into the data stream
    if (chunk.startsWith(':')) {
      return {}
    }
    if (chunk === '<EMERGENCY_OVERRIDE>') {
      clearStreamActivities()
      emergencyRef.value = true
      ensureAssistantMessage('text').content = 'Emergency signal received. Please call emergency services now.'
      updateMeta()
      onEarlyReturn()
      return { earlyReturn: true }
    }
    ensureAssistantMessage('text').content += chunk
    updateMeta()
    return {}
  }

  // 0: text_delta
  if (proto.prefix === '0') {
    const delta = String(proto.payload ?? '')
    if (delta === '<EMERGENCY_OVERRIDE>') {
      clearStreamActivities()
      emergencyRef.value = true
      ensureAssistantMessage('text').content = 'Emergency signal received. Please call emergency services now.'
      updateMeta()
      onEarlyReturn()
      return { earlyReturn: true }
    }
    
    let currentMessage = ensureAssistantMessage('text')
    const combined = currentMessage.content + delta
    const parts = combined.split('\n\n')
    
    if (parts.length > 1) {
      currentMessage.content = parts[0]
      for (let i = 1; i < parts.length; i++) {
        currentMessage = ensureAssistantMessage('text', true)
        currentMessage.content = parts[i]
      }
    } else {
      currentMessage.content = combined
    }

    updateMeta()
    return {}
  }

  // 9: tool_result (structured UI component)
  if (proto.prefix === '9') {
    const data = proto.payload
    const resultState = resolveStructuredMessageState(data?.result)
    if (resultState === 'final' || resultState === 'error') {
      completeStreamActivity(data)
    } else {
      recordStreamActivity(data, resultState)
    }
    const kind = normalizeAssistantMessageKind(data?.ui_kind)
    const assistantTarget = ensureAssistantMessage(kind, false, {
      streamKey: String(data?.tool_call_id ?? ''),
    })
    assistantTarget.messageKind = kind
    assistantTarget.content = stringifyStructuredContent(data?.result)
    updateMeta()
    return {}
  }

  if (proto.prefix === '8') {
    recordStreamActivity(proto.payload, 'started')
    return {}
  }

  if (proto.prefix === 's') {
    recordStreamActivity(proto.payload, 'running')
    return {}
  }

  if (proto.prefix === '2') {
    clearStreamActivities()
    ensureAssistantMessage('text').content = String(proto.payload ?? 'An error occurred.')
    updateMeta()
    return {}
  }

  // d: finish
  return {}
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const conversations = ref([])
  const activeConversationId = ref(null)
  const activeStreamCount = ref(0)
  const isStreaming = computed(() => activeStreamCount.value > 0)
  const isSyncingHistory = ref(false)
  const isLoadingMoreHistory = ref(false)
  const emergencyOverride = ref(false)
  const streamError = ref('')
  const sessionId = ref(null)
  const streamActivities = ref([])
  const historySummaries = ref([])
  const historyNextCursor = ref(null)
  const historyHasMore = ref(true)
  const authStore = useAuthStore()

  const pendingPromptBurst = ref([])
  let promptBurstTimerId = null
  let isSendingPromptBurst = false

  function buildConversationSummary(conversation) {
    return {
      id: conversation.id,
      title: conversation.title,
      createdAt: conversation.createdAt,
      updatedAt: conversation.updatedAt,
      sessionId: conversation.sessionId ?? null,
      isDraft: conversation.sessionId == null,
    }
  }

  function normalizeServerSummary(session) {
    return {
      id: buildSessionConversationId(session.id),
      title: session.title,
      createdAt: session.created_at,
      updatedAt: session.updated_at,
      sessionId: session.id,
      isDraft: false,
    }
  }

  function normalizeConversationMessages(serverMessages) {
    return serverMessages.flatMap((message) => {
      const messageKind = message.message_kind ?? 'text'
      if (
        message.role === 'assistant'
        && messageKind === 'text'
        && typeof message.content === 'string'
        && message.content.includes('\n\n')
      ) {
        return message.content.split('\n\n').map((part) => ({
          id: buildMessageId(),
          role: message.role,
          messageKind,
          content: part,
        }))
      }

      return [{
        id: buildMessageId(),
        role: message.role,
        messageKind,
        content: message.content,
      }]
    })
  }

  function normalizeServerConversation(session) {
    return {
      id: buildSessionConversationId(session.id),
      title: session.title,
      createdAt: session.created_at,
      updatedAt: session.updated_at,
      sessionId: session.id,
      messages: normalizeConversationMessages(session.messages ?? []),
    }
  }

  const conversationSummaries = computed(() => (
    (() => {
      const loadedSessionIds = new Set()
      const combined = conversations.value.map((conversation) => {
        if (conversation.sessionId != null) {
          loadedSessionIds.add(conversation.sessionId)
        }
        return buildConversationSummary(conversation)
      })

      historySummaries.value.forEach((summary) => {
        if (summary.sessionId != null && loadedSessionIds.has(summary.sessionId)) {
          return
        }
        combined.push(summary)
      })

      return combined.sort(compareConversationsByUpdatedAt)
    })()
  ))

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

  function clearActiveConversationSelection() {
    activeConversationId.value = null
    messages.value = []
    sessionId.value = null
  }

  function setNewestLoadedConversationAsActive() {
    if (conversations.value.length === 0) {
      clearActiveConversationSelection()
      return
    }

    const latestConversation = [...conversations.value].sort(compareConversationsByUpdatedAt)[0]
    setCurrentConversationById(latestConversation.id)
  }

  function findReusableDraftConversation() {
    return conversations.value.find(
      (conversation) => conversation.sessionId == null && conversation.messages.length === 0,
    ) ?? null
  }

  function ensureDraftConversationActive() {
    const reusableDraftConversation = findReusableDraftConversation()
    if (reusableDraftConversation) {
      setCurrentConversationById(reusableDraftConversation.id)
      return reusableDraftConversation
    }

    return startNewConversation()
  }

  function upsertHistorySummary(summary) {
    if (summary.sessionId == null) {
      return
    }

    const existingIndex = historySummaries.value.findIndex(
      (candidate) => candidate.sessionId === summary.sessionId,
    )

    if (existingIndex >= 0) {
      historySummaries.value[existingIndex] = {
        ...historySummaries.value[existingIndex],
        ...summary,
      }
      return
    }

    historySummaries.value.unshift(summary)
  }

  function removeHistorySummary(sessionIdentifier) {
    historySummaries.value = historySummaries.value.filter(
      (summary) => summary.sessionId !== sessionIdentifier,
    )
  }

  function mergeHistorySummaries(nextSummaries, { reset = false } = {}) {
    const merged = reset ? [] : [...historySummaries.value]

    nextSummaries.forEach((summary) => {
      const existingIndex = merged.findIndex(
        (candidate) => candidate.sessionId === summary.sessionId,
      )
      if (existingIndex >= 0) {
        merged[existingIndex] = {
          ...merged[existingIndex],
          ...summary,
        }
        return
      }
      merged.push(summary)
    })

    historySummaries.value = merged
  }

  function syncConversationSummary(conversation) {
    upsertHistorySummary(buildConversationSummary(conversation))
  }

  function hydrateConversationFromServer(session) {
    const normalizedConversation = normalizeServerConversation(session)
    const existingConversation = conversations.value.find(
      (conversation) => conversation.sessionId === normalizedConversation.sessionId,
    )

    if (existingConversation) {
      existingConversation.title = normalizedConversation.title
      existingConversation.createdAt = normalizedConversation.createdAt
      existingConversation.updatedAt = normalizedConversation.updatedAt
      existingConversation.messages = normalizedConversation.messages
      if (existingConversation.id === activeConversationId.value) {
        messages.value = existingConversation.messages
        sessionId.value = existingConversation.sessionId
      }
      syncConversationSummary(existingConversation)
      return existingConversation
    }

    conversations.value.unshift(normalizedConversation)
    syncConversationSummary(normalizedConversation)
    return normalizedConversation
  }

  function resetHistoryState() {
    historySummaries.value = []
    historyNextCursor.value = null
    historyHasMore.value = true
  }

  async function loadConversationHistoryPage({ reset = false } = {}) {
    if (!authStore.token) {
      return
    }

    if (reset) {
      isSyncingHistory.value = true
      resetHistoryState()
    } else {
      if (isLoadingMoreHistory.value || !historyHasMore.value) {
        return
      }
      isLoadingMoreHistory.value = true
    }

    try {
      const response = await fetchWithAuthRecovery(() => apiClient.get('/api/chat/history', {
        params: {
          page_size: HISTORY_PAGE_SIZE,
          ...(reset ? {} : { cursor: historyNextCursor.value }),
        },
      }))

      const serverSessions = Array.isArray(response.data?.sessions)
        ? response.data.sessions.map(normalizeServerSummary)
        : []

      mergeHistorySummaries(serverSessions, { reset })
      historyNextCursor.value = response.data?.next_cursor ?? null
      historyHasMore.value = Boolean(response.data?.has_more)
    } catch (_error) {
      streamError.value = 'Unable to load conversation history from the server.'
    } finally {
      if (reset) {
        isSyncingHistory.value = false
      } else {
        isLoadingMoreHistory.value = false
      }
    }
  }

  async function initializeChatScreen() {
    if (!authStore.token) {
      return
    }

    streamError.value = ''
    emergencyOverride.value = false
    ensureDraftConversationActive()
    await loadConversationHistoryPage({ reset: true })
  }

  async function openPersistedConversation(nextSessionId) {
    const loadedConversation = conversations.value.find(
      (conversation) => conversation.sessionId === nextSessionId,
    )
    if (loadedConversation) {
      setCurrentConversationById(loadedConversation.id)
      streamError.value = ''
      emergencyOverride.value = false
      clearStreamActivities()
      return loadedConversation
    }

    const response = await fetchWithAuthRecovery(
      () => apiClient.get(`/api/chat/sessions/${nextSessionId}`),
    )
    const serverSession = response.data
    if (!serverSession || typeof serverSession !== 'object') {
      throw new Error('Conversation detail payload missing.')
    }

    const hydratedConversation = hydrateConversationFromServer(serverSession)
    setCurrentConversationById(hydratedConversation.id)
    streamError.value = ''
    emergencyOverride.value = false
    clearStreamActivities()
    return hydratedConversation
  }

  function setLatestConversationAsActive() {
    if (conversations.value.length === 0) {
      activeConversationId.value = null
      messages.value = []
      sessionId.value = null
      return
    }

    setNewestLoadedConversationAsActive()
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
    if (activeConversation.sessionId != null) {
      syncConversationSummary(activeConversation)
    }
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
    syncConversationSummary(activeConversation)
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
	clearStreamActivities()
    return conversation
  }

  async function selectConversation(conversationId) {
    const selectedConversation = conversations.value.find(
      (conversation) => conversation.id === conversationId,
    )

    if (selectedConversation) {
      activeConversationId.value = selectedConversation.id
      messages.value = selectedConversation.messages
      sessionId.value = selectedConversation.sessionId ?? null
      streamError.value = ''
      emergencyOverride.value = false
	clearStreamActivities()
      return
    }

    const selectedSummary = historySummaries.value.find(
      (summary) => summary.id === conversationId,
    )
    if (!selectedSummary?.sessionId) {
      return
    }

    try {
      await openPersistedConversation(selectedSummary.sessionId)
    } catch (_error) {
      streamError.value = 'Unable to load this conversation.'
    }
  }

  function resetEmergencyState() {
    emergencyOverride.value = false
  }

  function appendMessage(role, content) {
    messages.value.push({
      id: buildMessageId(),
      role,
      messageKind: 'text',
      content,
    })

    if (activeConversationId.value) {
      updateActiveConversationMeta()
    }
  }

  function resolveBurstItems(items) {
    items.forEach((item) => item.resolve())
  }

  function recordStreamActivity(rawPayload, defaultPhase = 'running') {
    const normalized = normalizeStreamActivityPayload(rawPayload, defaultPhase)
    const existingActivity = [...streamActivities.value].reverse().find((activity) => {
      if (normalized.toolCallId) {
        return activity.toolCallId === normalized.toolCallId
      }

      if (normalized.toolName) {
        return activity.toolName === normalized.toolName && activity.state !== 'completed'
      }

      return activity.label === normalized.label && activity.state !== 'completed'
    })

    if (existingActivity) {
      existingActivity.label = normalized.label
      existingActivity.phase = normalized.phase
      existingActivity.state = normalized.state
      return existingActivity
    }

    const nextActivity = {
      id: buildStreamActivityId(),
      ...normalized,
    }

    streamActivities.value.push(nextActivity)
    return nextActivity
  }

  function completeStreamActivity(rawPayload) {
    const normalized = normalizeStreamActivityPayload(rawPayload, 'completed')
    const existingActivity = [...streamActivities.value].reverse().find((activity) => {
      if (normalized.toolCallId) {
        return activity.toolCallId === normalized.toolCallId
      }

      if (normalized.toolName) {
        return activity.toolName === normalized.toolName
      }

      return false
    })

    if (!existingActivity) {
      return
    }

    existingActivity.label = normalized.label
    existingActivity.phase = normalized.phase
    existingActivity.state = 'completed'
  }

  function clearStreamActivities() {
    streamActivities.value = []
  }

  function clearPromptBurstState() {
    if (promptBurstTimerId !== null) {
      clearTimeout(promptBurstTimerId)
      promptBurstTimerId = null
    }

    resolveBurstItems(pendingPromptBurst.value)
    pendingPromptBurst.value = []
    isSendingPromptBurst = false
    clearStreamActivities()
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
    let activeAssistantMessage = null

    function ensureAssistantMessage(kind, forceNew = false, options = {}) {
      const streamKey = String(options.streamKey ?? '').trim()

      if (streamKey) {
        const matchedMessage = messages.value.find((message) => (
          message.role === 'assistant' && message.streamKey === streamKey
        ))
        if (matchedMessage) {
          activeAssistantMessage = matchedMessage
          return activeAssistantMessage
        }
      }

      if (
        !forceNew
        && activeAssistantMessage?.messageKind === kind
        && (!streamKey || activeAssistantMessage?.streamKey === streamKey)
      ) {
        return activeAssistantMessage
      }

      const nextAssistantMessage = {
        id: buildMessageId(),
        role: 'assistant',
        messageKind: kind,
        streamKey: streamKey || null,
        content: '',
      }
      messages.value.push(nextAssistantMessage)
      activeAssistantMessage = messages.value[messages.value.length - 1]
      return activeAssistantMessage
    }

    updateActiveConversationMeta()

    activeStreamCount.value += 1
    isSendingPromptBurst = true

    try {
      let activeController = new AbortController()

      const buildRequestOptions = () => ({
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: prompt,
          session_id: sessionId.value,
        }),
        signal: activeController.signal,
      })

      const chunkCtx = {
        ensureAssistantMessage,
        updateMeta: updateActiveConversationMeta,
        onEarlyReturn: () => {
          activeController.abort()
          resolveBurstItems(burstItems)
        },
        emergencyRef: emergencyOverride,
        recordStreamActivity,
        completeStreamActivity,
        clearStreamActivities,
      }

      let receivedAtLeastOneChunk = false
      let authRefreshFailed = false
      clearStreamActivities()

      await fetchEventSource(`${getApiBaseUrl()}/api/chat`, {
        ...buildRequestOptions(),
        fetch: async (input, init) => {
          let response = await fetch(input, init)
          if (response.status === 401) {
            const refreshed = await authStore.refreshAccessToken()
            if (!refreshed) {
              authRefreshFailed = true
              clearChat()
              authStore.logout()
              streamError.value = 'Your session expired. Please login again.'
              activeController.abort()
              throw new Error(AUTH_REFRESH_FAILED_ERROR)
            }
            // Update token and retry
            const headers = new Headers(init.headers)
            headers.set('Authorization', `Bearer ${authStore.token}`)
            init.headers = headers
            response = await fetch(input, init)
          }
          return response
        },
        async onopen(response) {
          const responseSessionId = response.headers.get('X-Chat-Session-Id')
          if (responseSessionId) {
            syncSessionIdToActiveConversation(Number.parseInt(responseSessionId, 10))
            updateActiveConversationMeta()
          }

          if (!response.ok) {
            throw new Error(`Stream failed: ${response.status}`)
          }
        },
        onmessage(msg) {
          if (!msg.data) return
          const result = processStreamChunk(msg.data, chunkCtx)
          receivedAtLeastOneChunk = true
          if (result.earlyReturn) {
            activeController.abort()
          }
        },
        onerror(err) {
          throw err // Stop retrying on other errors
        }
      })

      if (authRefreshFailed) {
        clearStreamActivities()
        resolveBurstItems(burstItems)
        return
      }

      if (!receivedAtLeastOneChunk && !messages.value.some((message) => message.role === 'assistant' && message.content)) {
        const textMessage = ensureAssistantMessage('text')
        textMessage.content =
          'I could not generate a response. Please try again.'
        updateActiveConversationMeta()
      }

      resolveBurstItems(burstItems)
    } catch (error) {
      if (authRefreshFailed || (error instanceof Error && error.message === AUTH_REFRESH_FAILED_ERROR)) {
        clearStreamActivities()
        resolveBurstItems(burstItems)
        return
      }

      if (!messages.value.some((message) => message.role === 'assistant' && message.content)) {
        const textMessage = ensureAssistantMessage('text')
        textMessage.content = 'I could not generate a response. Please try again.'
        updateActiveConversationMeta()
      }
      streamError.value = 'Chat stream interrupted. Please try again.'
      resolveBurstItems(burstItems)
    } finally {
      activeStreamCount.value = Math.max(0, activeStreamCount.value - 1)
      isSendingPromptBurst = false
      clearStreamActivities()
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
        historySummaries.value = []
        messages.value = []
        activeConversationId.value = null
        sessionId.value = null
        streamError.value = ''
        emergencyOverride.value = false
        historyNextCursor.value = null
        historyHasMore.value = true
        isLoadingMoreHistory.value = false
        clearPromptBurstState()
        clearStreamActivities()
      }
    },
  )

  async function sendMessage(prompt) {
    if (!authStore.token) {
      streamError.value = 'You need to login before chatting.'
      return
    }

    if (!activeConversationId.value) {
      ensureDraftConversationActive()
    }

    streamError.value = ''
    appendMessage('user', prompt)
    updateActiveConversationMeta(buildConversationTitle(prompt))

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
    clearStreamActivities()

    if (selectedSessionId != null) {
      removeHistorySummary(selectedSessionId)
    }

    startNewConversation()

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
    streamActivities,
    isSyncingHistory,
    isLoadingMoreHistory,
    historyHasMore,
    emergencyOverride,
    streamError,
    sessionId,
    sendMessage,
    initializeChatScreen,
    loadConversationHistoryPage,
    startNewConversation,
    selectConversation,
    clearChat,
    resetEmergencyState,
  }
})
