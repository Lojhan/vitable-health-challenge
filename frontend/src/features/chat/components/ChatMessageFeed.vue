<script setup>
import { computed } from 'vue'

import ChatMessageBubble from './ChatMessageBubble.vue'
import ChatStructuredSection from './ChatStructuredSection.vue'
import { buildStructuredLeadMessage, normalizeStructuredPayload } from '../lib/structuredPayload'

const props = defineProps({
	messages: {
		type: Array,
		required: true,
	},
	streamError: {
		type: String,
		default: '',
	},
})

const emit = defineEmits(['quick-reply'])

function resolveAssistantPayload(message) {
	const explicitKind = String(message.messageKind ?? message.message_kind ?? 'text').trim().toLowerCase()
	if (explicitKind === 'text') {
		return normalizeStructuredPayload(message.content)
	}

	if (typeof message.content === 'object' && message.content !== null) {
		return normalizeStructuredPayload({
			kind: explicitKind,
			type: explicitKind,
			...message.content,
		})
	}

	if (typeof message.content === 'string') {
		try {
			const parsed = JSON.parse(message.content)
			if (parsed && typeof parsed === 'object') {
				return normalizeStructuredPayload({
					kind: explicitKind,
					type: explicitKind,
					...parsed,
				})
			}
		} catch (_error) {
			return { kind: 'text', data: message.content }
		}
	}

	return normalizeStructuredPayload(message.content)
}

const feedEntries = computed(() => props.messages.map((message) => {
	if (message.role !== 'assistant') {
		return {
			id: message.id,
			bubbleMessage: message,
			structuredPayload: null,
		}
	}

	const payload = resolveAssistantPayload(message)
	if (payload.kind === 'text') {
		return {
			id: message.id,
			bubbleMessage: message,
			structuredPayload: null,
		}
	}

	const leadMessage = {
		...message,
		content: buildStructuredLeadMessage(payload.kind),
	}

	return {
		id: message.id,
		bubbleMessage: leadMessage,
		structuredPayload: payload,
	}
}))

function handleQuickReply(prompt) {
	emit('quick-reply', prompt)
}
</script>

<template>
	<main
		id="chat-feed"
		role="log"
		aria-live="polite"
		aria-atomic="false"
		aria-relevant="additions"
		aria-label="Chat messages"
		class="flex-1 overflow-y-auto px-3 py-4 sm:px-4 vertical-scroll-strip"
	>
		<div class="mx-auto grid w-full max-w-5xl content-start gap-2.5">
			<article
				v-for="entry in feedEntries"
				:key="entry.id"
				class="grid gap-2"
			>
				<ChatMessageBubble :message="entry.bubbleMessage" />
				<ChatStructuredSection
					v-if="entry.structuredPayload"
					:payload="entry.structuredPayload"
					@quick-reply="handleQuickReply"
				/>
			</article>

			<p
				v-if="streamError"
				class="m-0 rounded-[0.45rem] border border-red-200 bg-red-50 p-2.5 text-red-700"
				role="alert"
				aria-live="polite"
			>
				{{ streamError }}
			</p>
		</div>
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
</style>
