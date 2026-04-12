<script setup>
import Button from 'primevue/button'

import ChatSidebarHistoryList from './ChatSidebarHistoryList.vue'

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
	historyHasMore: {
		type: Boolean,
		default: false,
	},
	isLoadingHistory: {
		type: Boolean,
		default: false,
	},
	isLoadingMoreHistory: {
		type: Boolean,
		default: false,
	},
	formatConversationDate: {
		type: Function,
		required: true,
	},
})

const emit = defineEmits(['close', 'new-conversation', 'request-more', 'select-conversation'])
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

		<ChatSidebarHistoryList
			:conversation-summaries="conversationSummaries"
			:active-conversation-id="activeConversationId"
			:history-has-more="historyHasMore"
			:is-loading-history="isLoadingHistory"
			:is-loading-more-history="isLoadingMoreHistory"
			:format-conversation-date="formatConversationDate"
			@request-more="emit('request-more')"
			@select-conversation="emit('select-conversation', $event)"
		/>
	</aside>
</template>