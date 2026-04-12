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

	function loadStructuredDemoConversation() {
		const demoMessages = [
			{
				id: 'demo-user-1',
				role: 'user',
				content: 'I need to schedule a doctor visit next week. Can you show options?',
			},
			{
				id: 'demo-assistant-1',
				role: 'assistant',
				content: JSON.stringify({
					type: 'providers',
					providers: [
						{ provider_id: 1, name: 'Dr. Sarah Chen', specialty: 'General Practice' },
						{ provider_id: 2, name: 'Dr. Marcus Rivera', specialty: 'Internal Medicine' },
						{ provider_id: 3, name: 'Dr. Priya Nair', specialty: 'Pediatrics' },
					],
				}),
			},
			{
				id: 'demo-user-2',
				role: 'user',
				content: 'Show me Dr. Sarah Chen availability for Tuesday.',
			},
			{
				id: 'demo-assistant-2',
				role: 'assistant',
				content: JSON.stringify({
					type: 'availability',
					timezone: 'UTC',
					appointment_duration_minutes: 60,
					appointment_duration_note: '*Appointments last 1h.',
					availability_source: 'provider_rrule',
					requested_window_start_utc: '2026-04-14T09:00:00',
					requested_window_end_utc: '2026-04-14T16:00:00',
					provider: {
						provider_id: 1,
						name: 'Dr. Sarah Chen',
						specialty: 'General Practice',
					},
					availability_dtstart_utc: '2026-04-14T09:00:00',
					availability_rrule: 'FREQ=DAILY;BYHOUR=9,10,11,13,14,15;BYMINUTE=0;BYSECOND=0',
					blocked_slots_utc: [],
				}),
			},
			{
				id: 'demo-user-3',
				role: 'user',
				content: 'What are my next appointments?',
			},
			{
				id: 'demo-assistant-3',
				role: 'assistant',
				content: JSON.stringify({
					type: 'appointments',
					count: 2,
					summary: 'You have 2 upcoming appointment(s).',
					appointments: [
						{
							appointment_id: 42,
							title: 'Primary Care Follow-up',
							time_slot_human_utc: 'Tuesday, April 14, 2026 at 10:00 AM UTC',
							time_slot: '2026-04-14T10:00:00',
							appointment_reason: 'Persistent sore throat',
							symptoms_summary: 'Sore throat and mild fever for 5 days',
							provider_name: 'Dr. Sarah Chen',
						},
						{
							appointment_id: 57,
							title: 'Cardiology Check',
							time_slot_human_utc: 'Friday, April 18, 2026 at 01:00 PM UTC',
							time_slot: '2026-04-18T13:00:00',
							appointment_reason: 'Chest discomfort follow-up',
							symptoms_summary: 'Intermittent chest tightness after exercise',
							provider_name: 'Dr. James Okafor',
						},
					],
				}),
			},
		]

		chatStore.startNewConversation('Structured data preview')
		chatStore.messages = demoMessages
		chatStore.streamError = ''
		chatStore.emergencyOverride = false
		headerMenuOpen.value = false
		closeSidebar()
	}

	function handleSelectConversation(conversationId) {
		chatStore.selectConversation(conversationId)
		closeSidebar()
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
			void chatStore.synchronizeHistoryOnStartup({ force: true })
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
		submitMessage,
		handleStructuredQuickReply,
		resetAlert,
		toggleSidebar,
		closeSidebar,
		toggleHeaderMenu,
		handleNewConversation,
		handleClearChat,
		loadStructuredDemoConversation,
		handleSelectConversation,
		formatConversationDate,
	}
}