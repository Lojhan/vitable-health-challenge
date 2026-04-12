import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import ChatStructuredSection from '../ChatStructuredSection.vue'

const _interactionStore = new Map()

vi.mock('../../../chat/structured/services/structuredInteractionApi', () => ({
	fetchStructuredInteractionState: vi.fn(async (id) => ({
		interaction_id: id ?? '',
		selection: _interactionStore.get(id) ?? null,
	})),
	saveStructuredInteractionState: vi.fn(async (params) => {
		const sel = params?.selection ? { kind: params.kind, ...params.selection, saved_at: new Date().toISOString() } : null
		if (sel) _interactionStore.set(params.interactionId, sel)
		return { interaction_id: params?.interactionId ?? '', selection: sel }
	}),
}))

describe('ChatStructuredSection', () => {
	it('renders provider explorer and emits quick reply after selecting provider in details view', async () => {
		vi.useFakeTimers()

		const wrapper = mount(ChatStructuredSection, {
			props: {
				payload: {
					kind: 'providers',
					interactionId: 'test-providers-selection',
					data: [
						{ provider_id: 1, name: 'Dr. Sarah Chen', specialty: 'General Practice' },
					],
				},
			},
		})

		await vi.runAllTimersAsync()
		await nextTick()

		expect(wrapper.text()).toContain('Available providers')
		expect(wrapper.text()).toContain('Dr. Sarah Chen')

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

		expect(wrapper.emitted('quick-reply')).toBeTruthy()
		expect(wrapper.emitted('quick-reply')[0]).toEqual([
			'Book an appointment with Dr. Sarah Chen (General Practice).',
		])

		wrapper.unmount()

		const remounted = mount(ChatStructuredSection, {
			props: {
				payload: {
					kind: 'providers',
					interactionId: 'test-providers-selection',
					data: [
						{ provider_id: 1, name: 'Dr. Sarah Chen', specialty: 'General Practice' },
					],
				},
			},
		})

		await vi.runAllTimersAsync()
		await nextTick()

		expect(remounted.text()).toContain('Selected provider')
		expect(remounted.text()).toContain('This step is completed for this message.')

		vi.useRealTimers()
	})
})
