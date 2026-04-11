<script setup>
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed } from 'vue'
import { normalizeStructuredPayload } from '../lib/structuredPayload'

const props = defineProps({
	message: {
		type: Object,
		required: true,
	},
})

const isUserMessage = computed(() => props.message.role === 'user')
const structuredPayload = computed(() => normalizeStructuredPayload(props.message.content))
const markdownHtml = computed(() => {
	if (structuredPayload.value.kind !== 'text') {
		return ''
	}

	return DOMPurify.sanitize(marked.parse(String(structuredPayload.value.data ?? '')))
})

const bubbleClasses = computed(() => {
	if (isUserMessage.value) {
		return 'ml-auto bg-indigo-600 text-white rounded-[0.85rem] rounded-br-sm user-bubble'
	}

	return 'bg-white text-slate-800 border border-slate-200 rounded-[0.85rem] rounded-bl-sm assistant-bubble'
})
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

		<div v-else class="m-0 markdown-body" v-html="markdownHtml" />
	</article>
</template>

<style scoped>
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

</style>