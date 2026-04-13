import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ChatComposer from '../ChatComposer.vue'
import ChatEmptyState from '../ChatEmptyState.vue'
import ChatSidebarHistoryList from '../ChatSidebarHistoryList.vue'
import ChatStreamActivityList from '../ChatStreamActivityList.vue'

vi.mock('@tanstack/vue-virtual', () => ({
	useVirtualizer() {
		return {
			value: {
				getVirtualItems: () => [],
				getTotalSize: () => 0,
			},
		}
	},
}))

vi.mock('primevue/inputtext', async () => {
	const { defineComponent } = await import('vue')

	return {
		default: defineComponent({
			name: 'InputText',
			props: ['modelValue', 'id', 'placeholder'],
			emits: ['input'],
			template: '<input :id="id" :value="modelValue" :placeholder="placeholder" @input="$emit(\'input\', $event)">',
		}),
	}
})

vi.mock('primevue/button', async () => {
	const { defineComponent } = await import('vue')

	return {
		default: defineComponent({
			name: 'Button',
			props: ['label', 'type', 'icon'],
			template: `<button :type="type || 'button'">{{ label || icon }}</button>`,
		}),
	}
})

describe('chat dark mode accessibility', () => {
	it('keeps the composer input on the shared themed surface instead of forcing white styles', () => {
		const wrapper = mount(ChatComposer, {
			props: {
				modelValue: '',
				messageInputId: 'composer-input',
			},
		})

		const composer = wrapper.get('form')
		expect(composer.classes()).toContain('chat-composer')

		const input = wrapper.get('input#composer-input')
		expect(input.classes()).toContain('app-themed-input')
		expect(input.classes()).toContain('chat-composer__input')
		expect(input.attributes('class')).not.toContain('bg-white!')
	})

	it('uses semantic text classes for the empty state copy and labels', () => {
		const wrapper = mount(ChatEmptyState)

		expect(wrapper.get('.empty-state__eyebrow').text()).toContain('New conversation')
		expect(wrapper.get('.empty-state__title').text()).toContain('Start with your symptoms')
		expect(wrapper.get('.empty-state__copy').classes()).toContain('empty-state__copy')
		expect(wrapper.get('.empty-state__label').classes()).toContain('empty-state__label')
		expect(wrapper.get('.empty-state-prompt').classes()).toContain('empty-state-prompt')
	})

	it('renders stream activity rows with theme-aware contrast classes', () => {
		const wrapper = mount(ChatStreamActivityList, {
			props: {
				activities: [
					{ id: 'a1', label: 'Loading options', phase: 'running', state: 'active' },
					{ id: 'a2', label: 'Finished loading', phase: 'completed', state: 'completed' },
				],
			},
		})

		expect(wrapper.get('.stream-activity-panel__heading').text()).toContain('Assistant activity')
		const rows = wrapper.findAll('.stream-activity-row')
		expect(rows).toHaveLength(2)
		expect(rows[0].classes()).toContain('stream-activity-row--active')
		expect(rows[1].classes()).toContain('stream-activity-row--completed')
		expect(wrapper.findAll('.stream-activity-row__phase')).toHaveLength(2)
	})

	it('renders conversation history states with semantic contrast classes', () => {
		const wrapper = mount(ChatSidebarHistoryList, {
			props: {
				conversationSummaries: [
					{
						id: 'session-1',
						title: 'Follow up on chest pain',
						updatedAt: '2026-04-12T09:00:00Z',
						isDraft: false,
					},
					{
						id: 'draft-1',
						title: 'New conversation',
						updatedAt: '2026-04-12T09:05:00Z',
						isDraft: true,
					},
				],
				activeConversationId: 'session-1',
				historyHasMore: false,
				isLoadingHistory: false,
				isLoadingMoreHistory: false,
				formatConversationDate: () => 'Apr 12, 9:00 AM',
			},
		})

		const buttons = wrapper.findAll('button.history-list__button')
		expect(buttons).toHaveLength(2)
		expect(buttons[0].classes()).toContain('history-list__button--active')
		expect(buttons[1].classes()).toContain('history-list__button--inactive')
		expect(wrapper.get('.history-list__draft-badge').text()).toContain('New')
		expect(wrapper.findAll('.history-list__meta')).toHaveLength(2)
	})
})