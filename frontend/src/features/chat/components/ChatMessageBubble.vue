<script setup>
import { computed } from 'vue'

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
		<p v-if="isUserMessage || isPlainText" class="m-0 whitespace-pre-wrap">
			{{ message.content }}
		</p>
	</article>
</template>

<style scoped>
</style>