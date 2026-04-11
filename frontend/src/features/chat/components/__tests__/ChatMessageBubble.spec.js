import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChatMessageBubble from '../ChatMessageBubble.vue'

describe('ChatMessageBubble', () => {
	it('renders user message content', () => {
		const wrapper = mount(ChatMessageBubble, {
			props: {
				message: {
					id: 'u1',
					role: 'user',
					content: 'I have a headache.',
				},
			},
		})

		expect(wrapper.text()).toContain('I have a headache.')
	})

	it('renders assistant markdown text', () => {
		const wrapper = mount(ChatMessageBubble, {
			props: {
				message: {
					id: 'a2',
					role: 'assistant',
					content: '**Bring water** and rest today.',
				},
			},
		})

		expect(wrapper.html()).toContain('<strong>Bring water</strong>')
	})
})
