import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import ChatMessageFeed from '../ChatMessageFeed.vue'

function bindScrollableMetrics(element, metrics) {
	Object.defineProperty(element, 'scrollHeight', {
		configurable: true,
		get: () => metrics.scrollHeight,
	})

	Object.defineProperty(element, 'clientHeight', {
		configurable: true,
		get: () => metrics.clientHeight,
	})

	Object.defineProperty(element, 'scrollTop', {
		configurable: true,
		get: () => metrics.scrollTop,
		set: (value) => {
			metrics.scrollTop = value
		},
	})
}

function mountFeed(props = {}) {
	return mount(ChatMessageFeed, {
		props: {
			messages: [],
			streamError: '',
			isStreaming: false,
			streamActivities: [],
			...props,
		},
		global: {
			stubs: {
				ChatStructuredSection: {
					props: ['payload'],
					template: '<div class="structured-section-stub">{{ payload.kind }}|{{ payload.state }}|{{ payload.progressLabel }}</div>',
				},
				TransitionGroup: false,
			},
		},
	})
}

describe('ChatMessageFeed', () => {
	it('auto-scrolls when new messages arrive and the user is near the bottom', async () => {
		const wrapper = mountFeed({
			messages: [
				{ id: 'u1', role: 'user', content: 'hello' },
			],
		})

		const feed = wrapper.get('#chat-feed').element
		const metrics = {
			scrollHeight: 1000,
			clientHeight: 240,
			scrollTop: 760,
		}
		bindScrollableMetrics(feed, metrics)
		feed.scrollTo = vi.fn()

		await nextTick()
		feed.scrollTo.mockClear()

		await wrapper.setProps({
			messages: [
				{ id: 'u1', role: 'user', content: 'hello' },
				{ id: 'a1', role: 'assistant', content: 'Hi there' },
			],
		})
		await nextTick()

		expect(feed.scrollTo).toHaveBeenCalledWith({
			behavior: 'auto',
			top: 1000,
		})
	})

	it('stops auto-follow while the user scrolls away and resumes near the bottom', async () => {
		const wrapper = mountFeed({
			messages: [
				{ id: 'u1', role: 'user', content: 'hello' },
			],
		})

		const feed = wrapper.get('#chat-feed').element
		const metrics = {
			scrollHeight: 1200,
			clientHeight: 240,
			scrollTop: 960,
		}
		bindScrollableMetrics(feed, metrics)
		feed.scrollTo = vi.fn()

		await nextTick()
		feed.scrollTo.mockClear()

		metrics.scrollTop = 180
		await wrapper.get('#chat-feed').trigger('scroll')

		await wrapper.setProps({
			messages: [
				{ id: 'u1', role: 'user', content: 'hello' },
				{ id: 'a1', role: 'assistant', content: 'First response' },
			],
		})
		await nextTick()

		expect(feed.scrollTo).not.toHaveBeenCalled()

		metrics.scrollTop = 968
		await wrapper.get('#chat-feed').trigger('scroll')
		await wrapper.setProps({
			messages: [
				{ id: 'u1', role: 'user', content: 'hello' },
				{ id: 'a1', role: 'assistant', content: 'First response' },
				{ id: 'a2', role: 'assistant', content: 'Second response' },
			],
		})
		await nextTick()

		expect(feed.scrollTo).toHaveBeenCalledWith({
			behavior: 'auto',
			top: 1200,
		})
	})

	it('renders inline activity and a providers skeleton before structured assistant output exists', () => {
		const wrapper = mountFeed({
			messages: [
				{ id: 'u1', role: 'user', content: 'Find a doctor for me' },
			],
			isStreaming: true,
			streamActivities: [
				{
					id: 'activity-1',
					label: 'Reviewing provider options',
					phase: 'running',
					state: 'active',
					toolName: 'show_providers_for_selection',
				},
			],
		})

		expect(wrapper.text()).toContain('Assistant activity')
		expect(wrapper.text()).toContain('Reviewing provider options')
		expect(wrapper.find('[aria-label="Assistant is preparing a structured response"]').exists()).toBe(true)
		expect(wrapper.get('.structured-section-stub').text()).toContain('providers|skeleton|Reviewing provider options')
	})

	it('renders the new conversation empty state and emits prompt quick replies', async () => {
		const wrapper = mountFeed()

		expect(wrapper.text()).toContain('New conversation')
		expect(wrapper.text()).toContain('Suggested prompts')

		const firstPromptButton = wrapper.findAll('button').find((candidate) => (
			candidate.text().includes('sore throat and fever')
		))
		expect(firstPromptButton).toBeTruthy()
		await firstPromptButton.trigger('click')

		expect(wrapper.emitted('quick-reply')).toEqual([
			['I have a sore throat and fever. What should I do?'],
		])
	})

	it('does not render a pending skeleton for plain text streaming', () => {
		const wrapper = mountFeed({
			messages: [
				{ id: 'u1', role: 'user', content: 'Say hello' },
			],
			isStreaming: true,
		})

		expect(wrapper.find('[aria-label="Assistant is preparing a structured response"]').exists()).toBe(false)
		expect(wrapper.find('.structured-section-stub').exists()).toBe(false)
	})

	it('does not render a pending skeleton for unsupported tool activity kinds', () => {
		const wrapper = mountFeed({
			messages: [
				{ id: 'u1', role: 'user', content: 'Book this slot' },
			],
			isStreaming: true,
			streamActivities: [
				{
					id: 'activity-1',
					label: 'Preparing your booking',
					phase: 'running',
					state: 'active',
					toolName: 'book_appointment',
				},
			],
		})

		expect(wrapper.find('[aria-label="Assistant is preparing a structured response"]').exists()).toBe(false)
		expect(wrapper.find('.structured-section-stub').exists()).toBe(false)
	})

	it('uses the pending assistant message kind when activity metadata is missing', () => {
		const wrapper = mountFeed({
			messages: [
				{ id: 'u1', role: 'user', content: 'Show my appointments' },
				{ id: 'a1', role: 'assistant', messageKind: 'appointments', content: '' },
			],
			isStreaming: true,
		})

		expect(wrapper.find('[aria-label="Assistant is preparing a structured response"]').exists()).toBe(true)
		expect(wrapper.get('.structured-section-stub').text()).toContain('appointments|skeleton|')
	})

	it('suppresses the pending skeleton once the structured assistant payload is renderable', () => {
		const wrapper = mountFeed({
			messages: [
				{ id: 'u1', role: 'user', content: 'Find a doctor for me' },
				{
					id: 'a1',
					role: 'assistant',
					messageKind: 'providers',
					streamKey: 'tool-1',
					content: JSON.stringify({
						type: 'providers',
						ui_state: 'skeleton',
						progress_message: 'Reviewing provider options',
						providers: [],
					}),
				},
			],
			isStreaming: true,
			streamActivities: [
				{
					id: 'activity-1',
					label: 'Reviewing provider options',
					phase: 'running',
					state: 'active',
					toolName: 'show_providers_for_selection',
					toolCallId: 'tool-1',
				},
			],
		})

		expect(wrapper.find('[aria-label="Assistant is preparing a structured response"]').exists()).toBe(false)
		expect(wrapper.findAll('.structured-section-stub')).toHaveLength(1)
		expect(wrapper.get('.structured-section-stub').text()).toContain('providers|skeleton|Reviewing provider options')
	})
})