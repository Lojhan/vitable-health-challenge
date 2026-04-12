<script setup>
import Button from "primevue/button";

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
  submitMessage,
  resetAlert,
  toggleSidebar,
  toggleHeaderMenu,
  handleNewConversation,
  handleClearChat,
  handleLoadActivityPreview,
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
        :format-conversation-date="formatConversationDate"
        @close="closeSidebar"
        @new-conversation="handleNewConversation"
        @select-conversation="handleSelectConversation"
      />

      <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header
          class="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 shadow-sm backdrop-blur"
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
                class="absolute right-0 top-[calc(100%+0.35rem)] z-30 w-52 rounded-md border border-slate-200 bg-white p-1.5 shadow-lg"
              >
                <button
                  type="button"
                  role="menuitem"
                  class="block w-full rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  @click="handleNewConversation"
                >
                  Start new conversation
                </button>
                <button
                  type="button"
                  role="menuitem"
                  class="block w-full rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  @click="handleLoadActivityPreview"
                >
                  Load agent activity preview
                </button>
                <button
                  type="button"
                  role="menuitem"
                  class="block w-full rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  @click="handleClearChat"
                >
                  Clear current conversation
                </button>
                <button
                  type="button"
                  role="menuitem"
                  class="mt-1 block w-full rounded-md bg-rose-50 px-3 py-2 text-left text-sm text-rose-700 hover:bg-rose-100"
                  @click="authStore.logout"
                >
                  Logout
                </button>
              </div>
            </transition>
          </div>
        </header>

        <div
          v-if="chatStore.emergencyOverride"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          class="mx-4 my-3 rounded-lg border-2 border-red-400 bg-red-50 p-4 text-red-900 shadow-md"
        >
          <strong class="block text-base">EMERGENCY OVERRIDE ACTIVE</strong>
          <p class="mt-1.5 mb-3.5 text-red-800">
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
