import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

export function useChatScreenController({ authStore, chatStore }) {
	const inputMessage = ref('')
	const acknowledgeBtn = ref(null)
	const headerMenuRoot = ref(null)
	const sidebarOpen = ref(false)
	const headerMenuOpen = ref(false)
	const messageInputId = 'chat-message-input'

	const conversationDateFormatter = new Intl.DateTimeFormat(undefined, {
		month: 'short',
		day: 'numeric',
		hour: 'numeric',
		minute: '2-digit',
	})

	const conversationSummaries = computed(() => chatStore.conversationSummaries)
	const activeConversationId = computed(() => chatStore.activeConversationId)
	const historyHasMore = computed(() => chatStore.historyHasMore)
	const isLoadingHistory = computed(() => chatStore.isSyncingHistory)
	const isLoadingMoreHistory = computed(() => chatStore.isLoadingMoreHistory)

	watch(
		() => chatStore.emergencyOverride,
		(active) => {
			if (active) {
				nextTick(() => {
					acknowledgeBtn.value?.$el?.focus()
				})
			}
		},
	)

	async function submitMessage() {
		const message = inputMessage.value.trim()
		if (!message) {
			return
		}

		inputMessage.value = ''
		await chatStore.sendMessage(message)
	}

	async function handleStructuredQuickReply(prompt) {
		const message = String(prompt ?? '').trim()
		if (!message) {
			return
		}

		await chatStore.sendMessage(message)
	}

	function resetAlert() {
		chatStore.resetEmergencyState()
	}

	function toggleSidebar() {
		sidebarOpen.value = !sidebarOpen.value
		if (sidebarOpen.value) {
			headerMenuOpen.value = false
		}
	}

	function closeSidebar() {
		sidebarOpen.value = false
	}

	function toggleHeaderMenu() {
		headerMenuOpen.value = !headerMenuOpen.value
	}

	function handleNewConversation() {
		chatStore.startNewConversation()
		inputMessage.value = ''
		headerMenuOpen.value = false
		closeSidebar()
	}

	function handleClearChat() {
		chatStore.clearChat()
		inputMessage.value = ''
		headerMenuOpen.value = false
	}

	async function handleSelectConversation(conversationId) {
		await chatStore.selectConversation(conversationId)
		closeSidebar()
	}

	function handleLoadMoreHistory() {
		void chatStore.loadConversationHistoryPage()
	}

	function formatConversationDate(value) {
		if (!value) {
			return ''
		}

		const parsed = new Date(value)
		if (Number.isNaN(parsed.getTime())) {
			return ''
		}

		return conversationDateFormatter.format(parsed)
	}

	function onGlobalPointerDown(event) {
		if (!headerMenuOpen.value) {
			return
		}

		if (!headerMenuRoot.value?.contains(event.target)) {
			headerMenuOpen.value = false
		}
	}

	function onGlobalKeyDown(event) {
		if (event.key === 'Escape') {
			headerMenuOpen.value = false
			closeSidebar()
		}
	}

	onMounted(() => {
		window.addEventListener('pointerdown', onGlobalPointerDown)
		window.addEventListener('keydown', onGlobalKeyDown)

		if (authStore.isAuthenticated) {
			void chatStore.initializeChatScreen()
		}
	})

	onBeforeUnmount(() => {
		window.removeEventListener('pointerdown', onGlobalPointerDown)
		window.removeEventListener('keydown', onGlobalKeyDown)
	})

	return {
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
		handleStructuredQuickReply,
		resetAlert,
		toggleSidebar,
		closeSidebar,
		toggleHeaderMenu,
		handleNewConversation,
		handleClearChat,
		handleLoadMoreHistory,
		handleSelectConversation,
		formatConversationDate,
	}
}