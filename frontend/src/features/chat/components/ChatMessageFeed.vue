<script setup>
import { computed, ref } from "vue";

import { useChatFeedAutoFollow } from "../composables/useChatFeedAutoFollow";
import {
  buildStructuredLeadMessage,
  normalizeStructuredPayload,
} from "../lib/structuredPayload";
import ChatMessageBubble from "./ChatMessageBubble.vue";
import ChatStreamActivityList from "./ChatStreamActivityList.vue";
import ChatStructuredSection from "./ChatStructuredSection.vue";

const props = defineProps({
  messages: {
    type: Array,
    required: true,
  },
  streamError: {
    type: String,
    default: "",
  },
  isStreaming: {
    type: Boolean,
    default: false,
  },
  streamActivities: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["quick-reply"]);
const feedRoot = ref(null);

const STRUCTURED_MESSAGE_KINDS = new Set([
  "providers",
  "availability",
  "availability_day",
  "availability_slots",
  "appointments",
  "json",
]);

const TOOL_ACTIVITY_KIND_MAP = {
  show_providers_for_selection: "providers",
  check_availability: "availability",
  list_my_appointments: "appointments",
};

function normalizeMessageKind(message) {
  return String(message?.messageKind ?? message?.message_kind ?? "text")
    .trim()
    .toLowerCase();
}

function resolveStreamingSkeletonKind(kind) {
  if (kind === "availability_day" || kind === "availability_slots") {
    return "availability";
  }

  return STRUCTURED_MESSAGE_KINDS.has(kind) && kind !== "text" ? kind : null;
}

function resolveStreamingSkeletonPayload(kind, progressLabel = "") {
  const normalizedKind = resolveStreamingSkeletonKind(kind);

  if (!normalizedKind) {
    return null;
  }

  if (normalizedKind === "providers") {
    return {
      kind: normalizedKind,
      state: "skeleton",
      progressLabel,
      interactionId: `streaming-skeleton-${normalizedKind}`,
      data: [],
    };
  }

  if (normalizedKind === "appointments") {
    return {
      kind: normalizedKind,
      state: "skeleton",
      progressLabel,
      interactionId: `streaming-skeleton-${normalizedKind}`,
      data: {
        appointments: [],
        count: 0,
      },
    };
  }

  return {
    kind: normalizedKind,
    state: "skeleton",
    progressLabel,
    interactionId: `streaming-skeleton-${normalizedKind}`,
    data: {},
  };
}

function isAssistantMessageRenderable(message) {
  if (message?.role !== "assistant") {
    return false;
  }

  const payload = resolveAssistantPayload(message);
  if (payload.kind !== "text") {
    return true;
  }

  if (typeof message.content === "string") {
    return message.content.trim().length > 0;
  }

  return message.content != null;
}

function resolveSkeletonKindFromActivity(activity) {
  const toolName = String(activity?.toolName ?? activity?.tool_name ?? "")
    .trim()
    .toLowerCase();
  return resolveStreamingSkeletonKind(TOOL_ACTIVITY_KIND_MAP[toolName] ?? null);
}

function resolveAssistantPayload(message) {
  const explicitKind = normalizeMessageKind(message);
  if (explicitKind === "text") {
    return normalizeStructuredPayload(message.content);
  }

  if (typeof message.content === "object" && message.content !== null) {
    return normalizeStructuredPayload({
      kind: explicitKind,
      type: explicitKind,
      ...message.content,
    });
  }

  if (typeof message.content === "string") {
    try {
      const parsed = JSON.parse(message.content);
      if (Array.isArray(parsed)) {
        return normalizeStructuredPayload(parsed);
      }
      if (parsed && typeof parsed === "object") {
        return normalizeStructuredPayload({
          kind: explicitKind,
          type: explicitKind,
          ...parsed,
        });
      }
    } catch (_error) {
      return { kind: "text", data: message.content };
    }
  }

  return normalizeStructuredPayload(message.content);
}

const feedEntries = computed(() =>
  props.messages.map((message) => {
    if (message.role !== "assistant") {
      return {
        id: message.id,
        bubbleMessage: message,
        structuredPayload: null,
      };
    }

    const payload = resolveAssistantPayload(message);

    if (payload.kind === "text") {
      return {
        id: message.id,
        bubbleMessage: message,
        structuredPayload: null,
      };
    }

    const leadMessage = {
      ...message,
      messageKind: "text",
      content: buildStructuredLeadMessage(
        payload.kind,
        payload.state,
        payload.progressLabel,
      ),
    };

    return {
      id: message.id,
      bubbleMessage: leadMessage,
      structuredPayload: payload,
    };
  }),
);

const activeStructuredStreamActivity = computed(() =>
  [...props.streamActivities]
    .reverse()
    .find(
      (activity) =>
        activity?.state !== "completed"
        && resolveSkeletonKindFromActivity(activity),
    ) ?? null,
);

const latestAssistantMessage = computed(
  () => [...props.messages].reverse().find((message) => message.role === "assistant") ?? null,
);

const pendingStructuredSkeletonPayload = computed(() => {
  if (!props.isStreaming) {
    return null;
  }

  const activeActivity = activeStructuredStreamActivity.value;
  if (activeActivity) {
    const matchingAssistantMessage = [...props.messages]
      .reverse()
      .find(
        (message) =>
          message.role === "assistant"
          && String(message.streamKey ?? "").trim() !== ""
          && String(message.streamKey).trim()
            === String(activeActivity.toolCallId ?? activeActivity.tool_call_id ?? "").trim(),
      );

    if (matchingAssistantMessage && isAssistantMessageRenderable(matchingAssistantMessage)) {
      return null;
    }

    return resolveStreamingSkeletonPayload(
      resolveSkeletonKindFromActivity(activeActivity),
      String(activeActivity.label ?? "").trim(),
    );
  }

  if (!latestAssistantMessage.value || isAssistantMessageRenderable(latestAssistantMessage.value)) {
    return null;
  }

  return resolveStreamingSkeletonPayload(normalizeMessageKind(latestAssistantMessage.value));
});

const feedVersion = computed(() => {
  const messageVersion = props.messages
    .map((message) => {
      const kind = normalizeMessageKind(message);
      const content =
        typeof message.content === "string"
          ? `${message.content.length}:${message.content.slice(-24)}`
          : JSON.stringify(message.content ?? "");
      return `${message.id}:${message.role}:${kind}:${content}`;
    })
    .join("|");

  const activityVersion = props.streamActivities
    .map(
      (activity) =>
        `${activity.id}:${activity.label}:${activity.phase}:${activity.state}`,
    )
    .join("|");

  return [
    messageVersion,
    activityVersion,
    props.streamError,
    props.isStreaming ? "1" : "0",
  ].join("::");
});

const { handleFeedScroll } = useChatFeedAutoFollow({
  feedRoot,
  feedVersion,
});

function handleQuickReply(prompt) {
  emit("quick-reply", prompt);
}
</script>

<template>
  <main
    ref="feedRoot"
    id="chat-feed"
    role="log"
    aria-live="polite"
    aria-atomic="false"
    aria-relevant="additions"
    aria-label="Chat messages"
    class="flex-1 overflow-y-auto px-3 py-4 sm:px-4 vertical-scroll-strip"
    @scroll="handleFeedScroll"
  >
    <TransitionGroup
      tag="div"
      name="feed-entry"
      class="mx-auto grid w-full max-w-5xl content-start gap-2.5"
    >
      <article v-for="entry in feedEntries" :key="entry.id" class="grid gap-2">
        <ChatMessageBubble
          v-if="!entry.structuredPayload"
          :message="entry.bubbleMessage"
        />
        <ChatStructuredSection
          v-if="entry.structuredPayload"
          :payload="entry.structuredPayload"
          @quick-reply="handleQuickReply"
        />
      </article>

      <ChatStreamActivityList
        v-if="streamActivities.length > 0"
        :key="'stream-activity-list'"
        :activities="streamActivities"
      />

      <article
        v-if="pendingStructuredSkeletonPayload"
        :key="'streaming-skeleton'"
        class="grid gap-2"
        aria-label="Assistant is preparing a structured response"
      >
        <ChatStructuredSection
          :payload="pendingStructuredSkeletonPayload"
          @quick-reply="handleQuickReply"
        />
      </article>

      <p
        v-if="streamError"
        key="stream-error"
        class="m-0 rounded-[0.45rem] border border-red-200 bg-red-50 p-2.5 text-red-700"
        role="alert"
        aria-live="polite"
      >
        {{ streamError }}
      </p>
    </TransitionGroup>
  </main>
</template>

<style scoped>
.vertical-scroll-strip {
  -ms-overflow-style: none;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.vertical-scroll-strip::-webkit-scrollbar {
  display: none;
}

.feed-entry-enter-active,
.feed-entry-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.feed-entry-enter-from,
.feed-entry-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
