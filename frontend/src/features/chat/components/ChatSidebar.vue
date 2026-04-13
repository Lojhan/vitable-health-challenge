<script setup>
import Button from 'primevue/button'

import ChatSidebarProfileMenu from './ChatSidebarProfileMenu.vue'
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
	profileLabel: {
		type: String,
		default: 'Profile',
	},
	profileCaption: {
		type: String,
		default: 'Theme and session settings',
	},
})

const emit = defineEmits(['close', 'new-conversation', 'request-more', 'select-conversation', 'logout'])
</script>

<template>
	<button
		v-if="sidebarOpen"
		class="sidebar-backdrop fixed inset-0 z-30 md:hidden"
		type="button"
		aria-label="Close conversation history"
		@click="emit('close')"
	/>

	<aside
		:class="[
			'chat-sidebar fixed inset-y-0 left-0 z-40 flex w-[82vw] max-w-[320px] flex-col border-r transition-transform duration-300 md:static md:z-10 md:w-75 md:max-w-none md:shadow-none',
			sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
		]"
		aria-label="Conversation history"
	>
		<div class="chat-sidebar__header flex items-center justify-between border-b px-4 py-3">
			<div>
				<p class="chat-sidebar__eyebrow m-0 text-xs font-semibold uppercase tracking-[0.14em]">History</p>
				<h2 class="chat-sidebar__title m-0 text-lg font-semibold">Conversations</h2>
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

		<ChatSidebarProfileMenu
			:profile-label="profileLabel"
			:profile-caption="profileCaption"
			@logout="emit('logout')"
		/>
	</aside>
</template>

<style scoped>
.sidebar-backdrop {
	background: var(--app-overlay);
}

.chat-sidebar {
	border-color: var(--app-border-subtle);
	background: var(--app-surface-1);
	box-shadow: var(--app-shadow-soft);
}

.chat-sidebar__header {
	border-color: var(--app-border-subtle);
}

.chat-sidebar__eyebrow {
	color: var(--app-text-secondary);
}

.chat-sidebar__title {
	color: var(--app-text-primary);
}
</style>