<script setup>
import Button from "primevue/button";

import ThemePreferenceControl from "../../../components/ThemePreferenceControl.vue";
import { useAuthStore } from "../../auth/stores/auth";
import { useChatStore } from "../../../stores/chat";
import ChatComposer from "../components/ChatComposer.vue";
import ChatMessageFeed from "../components/ChatMessageFeed.vue";
import ChatSidebar from "../components/ChatSidebar.vue";
import { useChatScreenController } from "../composables/useChatScreenController";

const authStore = useAuthStore();
const chatStore = useChatStore();

const {
  inputMessage,
  acknowledgeBtn,
  headerMenuRoot,
  sidebarOpen,
  headerMenuOpen,
  messageInputId,
  conversationSummaries,
  activeConversationId,
  historyHasMore,
  isLoadingHistory,
  isLoadingMoreHistory,
  submitMessage,
  resetAlert,
  toggleSidebar,
  toggleHeaderMenu,
  handleNewConversation,
  handleClearChat,
  handleLoadMoreHistory,
  handleStructuredQuickReply,
  handleSelectConversation,
  formatConversationDate,
  closeSidebar,
} = useChatScreenController({ authStore, chatStore });
</script>

<template>
  <section
    :class="[
      'h-svh w-full overflow-hidden',
      chatStore.emergencyOverride ? 'emergency-bg' : 'bg-slate-50',
    ]"
    :aria-label="
      chatStore.emergencyOverride
        ? 'Emergency triage active'
        : 'AI Triage Console'
    "
  >
    <div class="relative flex h-full overflow-hidden">
      <ChatSidebar
        :sidebar-open="sidebarOpen"
        :conversation-summaries="conversationSummaries"
        :active-conversation-id="activeConversationId"
        :history-has-more="historyHasMore"
        :is-loading-history="isLoadingHistory"
        :is-loading-more-history="isLoadingMoreHistory"
        :format-conversation-date="formatConversationDate"
        @close="closeSidebar"
        @new-conversation="handleNewConversation"
        @request-more="handleLoadMoreHistory"
        @select-conversation="handleSelectConversation"
      />

      <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header
          class="chat-header sticky top-0 z-20 flex items-center justify-between gap-3 border-b px-4 py-3 backdrop-blur"
        >
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
              <p
                class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-500"
              >
                Vitable AI
              </p>
              <h2 class="m-0 text-lg font-semibold text-slate-900">
                AI Triage Console
              </h2>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <ThemePreferenceControl />

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
                class="chat-menu absolute right-0 top-[calc(100%+0.35rem)] z-30 w-52 rounded-md border p-1.5"
              >
                <button
                  type="button"
                  role="menuitem"
                  class="chat-menu__item block w-full rounded-md px-3 py-2 text-left text-sm"
                  @click="handleNewConversation"
                >
                  Start new conversation
                </button>
                <button
                  type="button"
                  role="menuitem"
                  class="chat-menu__item block w-full rounded-md px-3 py-2 text-left text-sm"
                  @click="handleClearChat"
                >
                  Clear current conversation
                </button>
                <button
                  type="button"
                  role="menuitem"
                  class="chat-menu__item chat-menu__item--danger mt-1 block w-full rounded-md px-3 py-2 text-left text-sm"
                  @click="authStore.logout"
                >
                  Logout
                </button>
              </div>
            </transition>
            </div>
          </div>
        </header>

        <div
          v-if="chatStore.emergencyOverride"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          class="alert-banner mx-4 my-3 rounded-lg border-2 p-4 shadow-md"
        >
          <strong class="block text-base">EMERGENCY OVERRIDE ACTIVE</strong>
          <p class="alert-banner__copy mt-1.5 mb-3.5">
            Potential life-threatening symptoms detected. Call emergency
            services immediately.
          </p>
          <Button
            ref="acknowledgeBtn"
            label="Acknowledge and dismiss alert"
            aria-label="Acknowledge this emergency alert and dismiss it"
            severity="danger"
            @click="resetAlert"
          />
        </div>

        <ChatMessageFeed
          :messages="chatStore.messages"
          :is-streaming="chatStore.isStreaming"
          :stream-error="chatStore.streamError"
          :stream-activities="chatStore.streamActivities"
          @quick-reply="handleStructuredQuickReply"
        />
        <ChatComposer
          :model-value="inputMessage"
          :message-input-id="messageInputId"
          @update:model-value="inputMessage = $event"
          @submit="submitMessage"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.emergency-bg {
  animation: pulse-alert 1.2s ease-in-out infinite;
  background-color: #fef2f2;
}

.chat-header {
  border-color: var(--app-border-subtle);
  background: var(--app-surface-0);
  box-shadow: var(--app-shadow-soft);
}

.chat-menu {
  border-color: var(--app-border-subtle);
  background: var(--app-surface-1);
  box-shadow: var(--app-shadow-soft);
}

.chat-menu__item {
  color: var(--app-text-secondary);
  transition: background-color 160ms ease, color 160ms ease;
}

.chat-menu__item:hover {
  background: var(--app-surface-2);
  color: var(--app-text-primary);
}

.chat-menu__item--danger {
  background: color-mix(in srgb, var(--app-danger-500) 12%, transparent);
  color: var(--app-danger-700);
}

.chat-menu__item--danger:hover {
  background: color-mix(in srgb, var(--app-danger-500) 18%, transparent);
  color: var(--app-danger-800);
}

.alert-banner {
  border-color: var(--app-alert-danger-border);
  background: var(--app-alert-danger-bg);
  color: var(--app-alert-danger-text);
}

.alert-banner__copy {
  color: color-mix(in srgb, var(--app-alert-danger-text) 88%, white 12%);
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
