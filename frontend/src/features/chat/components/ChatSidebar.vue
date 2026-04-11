<script setup>
import Button from 'primevue/button'

defineProps({
	sidebarOpen: {
		type: Boolean,
		required: true,
	},
	conversationSummaries: {
		type: Array,
		required: true,
	},
	activeConversationId: {
		type: String,
		default: null,
	},
	formatConversationDate: {
		type: Function,
		required: true,
	},
})

const emit = defineEmits(['close', 'new-conversation', 'select-conversation'])
</script>

<template>
	<button
		v-if="sidebarOpen"
		class="fixed inset-0 z-30 bg-slate-900/40 md:hidden"
		type="button"
		aria-label="Close conversation history"
		@click="emit('close')"
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
				@click="emit('new-conversation')"
			/>
		</div>

		<nav class="flex-1 overflow-y-auto px-2 py-2" aria-label="Past conversations">
			<button
				v-for="conversation in conversationSummaries"
				:key="conversation.id"
				type="button"
				class="mb-1 w-full rounded-md border px-3 py-2 text-left transition"
				:class="[
					conversation.id === activeConversationId
						? 'border-indigo-300 bg-indigo-50 text-indigo-900'
						: 'border-transparent bg-transparent text-slate-700 hover:border-slate-200 hover:bg-slate-100',
				]"
				:aria-current="conversation.id === activeConversationId ? 'page' : undefined"
				:aria-label="`Open conversation: ${conversation.title}`"
				@click="emit('select-conversation', conversation.id)"
			>
				<p class="m-0 truncate text-sm font-medium">{{ conversation.title }}</p>
				<p class="m-0 mt-0.5 text-xs text-slate-500">{{ formatConversationDate(conversation.updatedAt) }}</p>
			</button>

			<p v-if="conversationSummaries.length === 0" class="m-0 px-2 pt-3 text-sm text-slate-500">
				Your past conversations will appear here.
			</p>
		</nav>
	</aside>
</template>