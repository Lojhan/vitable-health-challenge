<script setup>
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed, ref, watch } from 'vue'

const props = defineProps({
	message: {
		type: Object,
		required: true,
	},
})

const isUserMessage = computed(() => props.message.role === 'user')
const isPlainText = computed(() => {
	const kind = String(props.message.messageKind ?? 'text').trim().toLowerCase()
	return kind === 'text'
})

const assistantRenderSeed = ref(0)

const assistantHtml = computed(() => {
	if (isUserMessage.value || !isPlainText.value) {
		return ''
	}

	const rendered = marked.parse(String(props.message.content ?? ''))
	return DOMPurify.sanitize(rendered)
})

const bubbleClasses = computed(() => {
	if (isUserMessage.value) {
		return 'ml-auto bg-indigo-600 text-white rounded-[0.85rem] rounded-br-sm user-bubble'
	}

	return 'bg-white text-slate-800 border border-slate-200 rounded-[0.85rem] rounded-bl-sm assistant-bubble'
})

watch(
	() => props.message.content,
	() => {
		if (isUserMessage.value || !isPlainText.value) {
			return
		}

		assistantRenderSeed.value += 1
	},
)
</script>

<template>
	<article
		:class="[
			'relative w-fit max-w-[86%] px-3.5 py-2.5 text-[0.95rem] leading-relaxed shadow-sm sm:max-w-[80%]',
			bubbleClasses,
		]"
		:aria-label="`${message.role === 'user' ? 'You' : 'AI Nurse'}: ${typeof message.content === 'string' ? message.content : 'Response'}`"
	>
		<p v-if="isUserMessage" class="m-0 whitespace-pre-wrap">
			{{ message.content }}
		</p>
		<div
			v-else-if="isPlainText"
			:key="`assistant-${message.id}-${assistantRenderSeed}`"
			class="message-rich-text assistant-stream-fragment"
			v-html="assistantHtml"
		/>
	</article>
</template>

<style scoped>
.assistant-stream-fragment {
	animation: assistant-token-fade 180ms ease-out;
}

.message-rich-text :deep(p:first-child:last-child) {
	margin: 0;
}

.message-rich-text :deep(p) {
	margin: 0 0 0.55rem;
}

.message-rich-text :deep(p:last-child) {
	margin-bottom: 0;
}

.message-rich-text :deep(strong) {
	font-weight: 700;
}

.message-rich-text :deep(ul),
.message-rich-text :deep(ol) {
	margin: 0.45rem 0 0 1rem;
	padding: 0;
}

.message-rich-text :deep(li + li) {
	margin-top: 0.18rem;
}

@keyframes assistant-token-fade {
	0% {
		opacity: 0.36;
		transform: translateY(2px);
	}
	100% {
		opacity: 1;
		transform: translateY(0);
	}
}
</style>