<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const authStore = useAuthStore()
const chatStore = useChatStore()
const inputMessage = ref('')
const acknowledgeBtn = ref(null)
const headerMenuRoot = ref(null)
const sidebarOpen = ref(false)
const headerMenuOpen = ref(false)
const messageInputId = 'chat-message-input'
const conversationDateFormatter = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

const conversationSummaries = computed(() => chatStore.conversationSummaries)
const activeConversationId = computed(() => chatStore.activeConversationId)

// Shift focus to Acknowledge button immediately when emergency activates
watch(
  () => chatStore.emergencyOverride,
  (active) => {
    if (active) {
      nextTick(() => {
        acknowledgeBtn.value?.$el?.focus()
      })
    }
  },
)

async function submitMessage() {
  const message = inputMessage.value.trim()
  if (!message) {
    return
  }

  inputMessage.value = ''
  await chatStore.sendMessage(message)
}

function resetAlert() {
  chatStore.resetEmergencyState()
}

function renderAssistantMessage(content) {
  return DOMPurify.sanitize(marked.parse(content ?? ''))
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
  if (sidebarOpen.value) {
    headerMenuOpen.value = false
  }
}

function closeSidebar() {
  sidebarOpen.value = false
}

function toggleHeaderMenu() {
  headerMenuOpen.value = !headerMenuOpen.value
}

function handleNewConversation() {
  chatStore.startNewConversation()
  inputMessage.value = ''
  headerMenuOpen.value = false
  closeSidebar()
}

function handleClearChat() {
  chatStore.clearChat()
  inputMessage.value = ''
  headerMenuOpen.value = false
}

function handleSelectConversation(conversationId) {
  chatStore.selectConversation(conversationId)
  closeSidebar()
}

function formatConversationDate(value) {
  if (!value) {
    return ''
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return ''
  }

  return conversationDateFormatter.format(parsed)
}

function onGlobalPointerDown(event) {
  if (!headerMenuOpen.value) {
    return
  }

  if (!headerMenuRoot.value?.contains(event.target)) {
    headerMenuOpen.value = false
  }
}

function onGlobalKeyDown(event) {
  if (event.key === 'Escape') {
    headerMenuOpen.value = false
    closeSidebar()
  }
}

onMounted(() => {
  window.addEventListener('pointerdown', onGlobalPointerDown)
  window.addEventListener('keydown', onGlobalKeyDown)

  if (authStore.isAuthenticated) {
    void chatStore.synchronizeHistoryOnStartup({ force: true })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', onGlobalPointerDown)
  window.removeEventListener('keydown', onGlobalKeyDown)
})
</script>

<template>
  <section
    :class="[
      'mx-auto h-svh w-full max-w-295 overflow-hidden',
      chatStore.emergencyOverride ? 'emergency-bg' : 'bg-slate-50',
    ]"
    :aria-label="chatStore.emergencyOverride ? 'Emergency triage active' : 'AI Triage Console'"
  >
    <div class="relative flex h-full overflow-hidden">
      <button
        v-if="sidebarOpen"
        class="fixed inset-0 z-30 bg-slate-900/40 md:hidden"
        type="button"
        aria-label="Close conversation history"
        @click="closeSidebar"
      />

      <aside
        :class="[
          'fixed inset-y-0 left-0 z-40 flex w-[82vw] max-w-[320px] flex-col border-r border-slate-200 bg-white shadow-xl transition-transform duration-300 md:static md:z-10 md:w-75 md:max-w-none md:shadow-none',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        ]"
        aria-label="Conversation history"
      >
        <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">History</p>
            <h2 class="m-0 text-lg font-semibold text-slate-900">Conversations</h2>
          </div>
          <Button
            icon="pi pi-plus"
            severity="secondary"
            outlined
            rounded
            size="small"
            class="text-slate-700!"
            aria-label="Start a new conversation"
            @click="handleNewConversation"
          />
        </div>

        <nav class="flex-1 overflow-y-auto px-2 py-2" aria-label="Past conversations">
          <button
            v-for="conversation in conversationSummaries"
            :key="conversation.id"
            type="button"
            class="mb-1 w-full rounded-xl border px-3 py-2 text-left transition"
            :class="[
              conversation.id === activeConversationId
                ? 'border-indigo-300 bg-indigo-50 text-indigo-900'
                : 'border-transparent bg-transparent text-slate-700 hover:border-slate-200 hover:bg-slate-100',
            ]"
            :aria-current="conversation.id === activeConversationId ? 'page' : undefined"
            :aria-label="`Open conversation: ${conversation.title}`"
            @click="handleSelectConversation(conversation.id)"
          >
            <p class="m-0 truncate text-sm font-medium">{{ conversation.title }}</p>
            <p class="m-0 mt-0.5 text-xs text-slate-500">{{ formatConversationDate(conversation.updatedAt) }}</p>
          </button>

          <p v-if="conversationSummaries.length === 0" class="m-0 px-2 pt-3 text-sm text-slate-500">
            Your past conversations will appear here.
          </p>
        </nav>
      </aside>

      <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header class="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 shadow-sm backdrop-blur">
          <div class="flex items-center gap-2.5">
            <div class="md:hidden">
              <Button
                icon="pi pi-bars"
                text
                rounded
                size="small"
                aria-label="Toggle conversation history"
                class="text-slate-700! bg-transparent! border-transparent! shadow-none!"
                @click="toggleSidebar"
              />
            </div>
            <div>
              <p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-500">Vitable AI</p>
              <h2 class="m-0 text-lg font-semibold text-slate-900">AI Triage Console</h2>
            </div>
          </div>

          <div ref="headerMenuRoot" class="relative">
            <Button
              icon="pi pi-ellipsis-v"
              severity="secondary"
              rounded
              size="small"
              class="text-slate-700!"
              aria-label="Open chat actions"
              :aria-expanded="headerMenuOpen"
              aria-haspopup="menu"
              @click="toggleHeaderMenu"
            />

            <transition name="menu-pop">
              <div
                v-if="headerMenuOpen"
                role="menu"
                aria-label="Chat actions"
                class="absolute right-0 top-[calc(100%+0.35rem)] z-30 w-52 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg"
              >
                <button
                  type="button"
                  role="menuitem"
                  class="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  @click="handleNewConversation"
                >
                  Start new conversation
                </button>
                <button
                  type="button"
                  role="menuitem"
                  class="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  @click="handleClearChat"
                >
                  Clear current conversation
                </button>
                <button
                  type="button"
                  role="menuitem"
                  class="mt-1 block w-full rounded-lg bg-rose-50 px-3 py-2 text-left text-sm text-rose-700 hover:bg-rose-100"
                  @click="authStore.logout"
                >
                  Logout
                </button>
              </div>
            </transition>
          </div>
        </header>

        <!-- Emergency alert — aria-live="assertive" so screen readers interrupt immediately -->
        <div
          v-if="chatStore.emergencyOverride"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          class="mx-4 my-3 rounded-2xl border-2 border-red-400 bg-red-50 p-4 text-red-900 shadow-md"
        >
          <strong class="block text-base">EMERGENCY OVERRIDE ACTIVE</strong>
          <p class="mt-1.5 mb-3.5 text-red-800">
            Potential life-threatening symptoms detected. Call emergency services immediately.
          </p>
          <Button
            ref="acknowledgeBtn"
            label="Acknowledge and dismiss alert"
            aria-label="Acknowledge this emergency alert and dismiss it"
            severity="danger"
            @click="resetAlert"
          />
        </div>

        <!-- Chat message feed — aria-live="polite" so new AI messages are announced -->
        <main
          id="chat-feed"
          role="log"
          aria-live="polite"
          aria-atomic="false"
          aria-relevant="additions"
          aria-label="Chat messages"
          class="flex-1 overflow-y-auto px-3 py-4 sm:px-4 grid content-start gap-2.5"
        >
          <article
            v-for="message in chatStore.messages"
            :key="message.id"
            :class="[
              'relative w-fit max-w-[86%] px-3.5 py-2.5 text-[0.95rem] leading-relaxed shadow-sm sm:max-w-[80%]',
              message.role === 'user'
                ? 'ml-auto bg-indigo-600 text-white rounded-[1.25rem] rounded-br-md user-bubble'
                : 'bg-white text-slate-800 border border-slate-200 rounded-[1.25rem] rounded-bl-md assistant-bubble',
              message.role === 'assistant' && message.content === '...'
                ? 'placeholder-bubble'
                : '',
            ]"
            :aria-label="`${message.role === 'user' ? 'You' : 'AI Nurse'}: ${message.content}`"
          >
            <p
              v-if="message.role === 'user' || message.content === '...'"
              class="m-0 whitespace-pre-wrap"
            >
              {{ message.content }}
            </p>
            <div
              v-else
              class="m-0 markdown-body"
              v-html="renderAssistantMessage(message.content)"
            />
          </article>

          <p
            v-if="chatStore.streamError"
            class="m-0 rounded-[0.6rem] border border-red-200 bg-red-50 p-2.5 text-red-700"
            role="alert"
            aria-live="polite"
          >
            {{ chatStore.streamError }}
          </p>
        </main>

        <form
          class="sticky bottom-0 z-20 border-t border-slate-200 bg-white/95 px-3 py-3 backdrop-blur sm:px-4"
          aria-label="Send a message"
          @submit.prevent="submitMessage"
        >
          <label :for="messageInputId" class="sr-only">
            Describe your symptoms
          </label>
          <div class="flex items-center gap-2">
            <InputText
              :id="messageInputId"
              v-model="inputMessage"
              placeholder="Type your symptoms..."
              aria-label="Describe your symptoms and current condition"
              class="w-full"
            />
            <Button
              type="submit"
              icon="pi pi-send"
              label="Send"
              aria-label="Send your message to the AI nurse"
              class="shrink-0"
            />
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<style scoped>
.emergency-bg {
  animation: pulse-alert 1.2s ease-in-out infinite;
  background-color: #fef2f2;
}

.placeholder-bubble {
  min-width: 3.2rem;
  text-align: center;
}

.markdown-body :deep(p) {
  margin: 0.25rem 0;
}

.markdown-body :deep(p:first-child) {
  margin-top: 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.35rem 0 0.35rem 1.1rem;
  padding: 0;
}

.markdown-body :deep(li) {
  margin: 0.15rem 0;
}

@keyframes pulse-alert {
  0%,
  100% {
    box-shadow: inset 0 0 0 0 rgba(239, 68, 68, 0.15);
  }
  50% {
    box-shadow: inset 0 0 0 8px rgba(239, 68, 68, 0.08);
  }
}

.menu-pop-enter-active,
.menu-pop-leave-active {
  transition: all 0.16s ease;
}

.menu-pop-enter-from,
.menu-pop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
