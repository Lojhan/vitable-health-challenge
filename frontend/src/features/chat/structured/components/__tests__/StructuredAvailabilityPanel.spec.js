import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import StructuredAvailabilityPanel from '../StructuredAvailabilityPanel.vue'

describe('StructuredAvailabilityPanel', () => {
	it('renders interactive calendar and emits quick reply on slot selection', async () => {
		vi.useFakeTimers({ now: new Date('2026-04-10T12:00:00.000Z') })

		const wrapper = mount(StructuredAvailabilityPanel, {
			props: {
				payload: {
					kind: 'availability',
					interactionId: 'test-availability-selection',
					data: {
						total_slots: 4,
						timezone: 'UTC',
						grouped_human_utc: [
							{
								day_iso_utc: '2026-04-14',
								day: 'Tuesday, April 14',
								period: 'morning',
								windows_utc: ['9:00 AM - 12:00 PM'],
								slot_count: 3,
							},
						],
					},
				},
			},
		})

		await vi.runAllTimersAsync()
		await nextTick()

		expect(wrapper.text()).toContain('Availability calendar')
		expect(wrapper.text()).toContain('April 2026')

		const dayButton = wrapper.findAll('button').find((candidate) => candidate.text().includes('14'))
		expect(dayButton).toBeTruthy()
		await dayButton.trigger('click')

		await vi.runAllTimersAsync()
		await nextTick()

		const slotButton = wrapper.findAll('button').find((candidate) => candidate.text().includes('09:00 UTC'))
		expect(slotButton).toBeTruthy()
		await slotButton.trigger('click')

		const continueButton = wrapper.findAll('button').find((candidate) => candidate.text() === 'Select slot')
		expect(continueButton).toBeTruthy()
		await continueButton.trigger('click')
		await vi.runAllTimersAsync()
		await nextTick()

		expect(wrapper.emitted('quick-reply')).toBeTruthy()
		expect(wrapper.emitted('quick-reply')[0]).toEqual([
			'Please book Tue, Apr 14 at 09:00 UTC (UTC).',
		])

		wrapper.unmount()

		const remounted = mount(StructuredAvailabilityPanel, {
			props: {
				payload: {
					kind: 'availability',
					interactionId: 'test-availability-selection',
					data: {
						total_slots: 4,
						timezone: 'UTC',
						grouped_human_utc: [
							{
								day_iso_utc: '2026-04-14',
								day: 'Tuesday, April 14',
								period: 'morning',
								windows_utc: ['9:00 AM - 12:00 PM'],
								slot_count: 3,
							},
						],
					},
				},
			},
		})

		await vi.runAllTimersAsync()
		await nextTick()

		expect(remounted.text()).toContain('Selected availability')
		expect(remounted.text()).toContain('This step is completed for this message.')
		expect(remounted.text()).toContain('Slot selected')

		vi.useRealTimers()
	})
})
