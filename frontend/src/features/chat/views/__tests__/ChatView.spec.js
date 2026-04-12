import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChatView from '../ChatView.vue'

const authStore = reactive({
	isAuthenticated: false,
	logout: vi.fn(),
})

const chatStore = reactive({
	emergencyOverride: false,
	messages: [],
	streamError: '',
	conversationSummaries: [],
	activeConversationId: null,
	historyHasMore: false,
	isSyncingHistory: false,
	isLoadingMoreHistory: false,
	initializeChatScreen: vi.fn(async () => {}),
	loadConversationHistoryPage: vi.fn(async () => {}),
	sendMessage: vi.fn(async () => {}),
	startNewConversation: vi.fn(),
	clearChat: vi.fn(),
	selectConversation: vi.fn(async () => {}),
	resetEmergencyState: vi.fn(),
})

vi.mock('../../../auth/stores/auth', () => ({
	useAuthStore: () => authStore,
}))

vi.mock('../../../../stores/chat', () => ({
	useChatStore: () => chatStore,
}))

vi.mock('../../structured/services/structuredInteractionApi', () => ({
	fetchStructuredInteractionState: vi.fn(async () => ({ interaction_id: '', selection: null })),
	saveStructuredInteractionState: vi.fn(async (params) => ({
		interaction_id: params?.interactionId ?? '',
		selection: params?.selection ? { kind: params.kind, ...params.selection } : null,
	})),
}))

vi.mock('primevue/button', async () => {
	const { defineComponent } = await import('vue')

	return {
		default: defineComponent({
			name: 'Button',
			inheritAttrs: false,
			props: ['label', 'icon', 'ariaLabel', 'type'],
			template: `<button v-bind="$attrs" :type="type || 'button'" @click="$emit('click')">{{ label || icon }}</button>`,
		}),
	}
})

vi.mock('primevue/inputtext', async () => {
	const { defineComponent } = await import('vue')

	return {
		default: defineComponent({
			name: 'InputText',
			props: ['modelValue', 'id', 'placeholder'],
			emits: ['input'],
			template: `
				<input
					:id="id"
					:value="modelValue"
					:placeholder="placeholder"
					@input="$emit('input', $event)"
				>
			`,
		}),
	}
})

describe('ChatView', () => {
	beforeEach(() => {
		authStore.isAuthenticated = false
		authStore.logout.mockClear()

		chatStore.emergencyOverride = false
		chatStore.messages = [
			{ id: '1', role: 'user', content: 'hello' },
		]
		chatStore.streamError = ''
		chatStore.conversationSummaries = []
		chatStore.activeConversationId = null
		chatStore.historyHasMore = false
		chatStore.isSyncingHistory = false
		chatStore.isLoadingMoreHistory = false
		chatStore.initializeChatScreen.mockClear()
		chatStore.loadConversationHistoryPage.mockClear()
		chatStore.sendMessage.mockClear()
		chatStore.startNewConversation.mockClear()
		chatStore.clearChat.mockClear()
		chatStore.selectConversation.mockClear()
		chatStore.resetEmergencyState.mockClear()
	})

	it('initializes a fresh chat screen on mount when authenticated', async () => {
		authStore.isAuthenticated = true
		mount(ChatView)
		await nextTick()

		expect(chatStore.initializeChatScreen).toHaveBeenCalledTimes(1)
	})

	it('renders existing messages', () => {
		const wrapper = mount(ChatView)
		expect(wrapper.text()).toContain('hello')
	})

	it('submits new message through chat store', async () => {
		const wrapper = mount(ChatView)
		const input = wrapper.find('input[placeholder="Type your symptoms..."]')

		await input.setValue('i need help')
		await wrapper.find('form[aria-label="Send a message"]').trigger('submit')

		expect(chatStore.sendMessage).toHaveBeenCalledWith('i need help')
	})

	it('sends quick reply when structured action is clicked', async () => {
		vi.useFakeTimers()

		chatStore.messages = [
			{
				id: 'a1',
				role: 'assistant',
				content: JSON.stringify({
					type: 'providers',
					providers: [
						{ provider_id: 1, name: 'Dr. Sarah Chen', specialty: 'General Practice' },
					],
				}),
			},
		]

		const wrapper = mount(ChatView)

		await vi.runAllTimersAsync()
		await nextTick()

		const viewProfileButton = wrapper.findAll('button').find((candidate) => candidate.text() === 'View profile')
		expect(viewProfileButton).toBeTruthy()
		await viewProfileButton.trigger('click')

		await vi.runAllTimersAsync()
		await nextTick()

		const selectProviderButton = wrapper.findAll('button').find((candidate) => candidate.text().includes('Select Dr. Sarah Chen'))
		expect(selectProviderButton).toBeTruthy()
		await selectProviderButton.trigger('click')
		await vi.runAllTimersAsync()
		await nextTick()

		expect(chatStore.sendMessage).toHaveBeenCalledWith(
			'Book an appointment with Dr. Sarah Chen (General Practice).',
		)

		vi.useRealTimers()
	})

})
