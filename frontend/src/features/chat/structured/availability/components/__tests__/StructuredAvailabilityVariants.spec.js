import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import StructuredAvailabilityDayPanel from '../StructuredAvailabilityDayPanel.vue'
import StructuredAvailabilityPanel from '../StructuredAvailabilityPanel.vue'
import StructuredAvailabilitySlotsPanel from '../StructuredAvailabilitySlotsPanel.vue'

const interactionStore = new Map()

vi.mock('../../../../../../stores/chat', () => ({
	useChatStore: () => ({ isStreaming: false }),
}))

vi.mock('../../../services/structuredInteractionApi', () => ({
	fetchStructuredInteractionState: vi.fn(async (id) => ({
		interaction_id: id ?? '',
		selection: interactionStore.get(id) ?? null,
	})),
	saveStructuredInteractionState: vi.fn(async (params) => {
		const selection = params?.selection
			? { kind: params.kind, ...params.selection, saved_at: new Date().toISOString() }
			: null
		if (selection) {
			interactionStore.set(params.interactionId, selection)
		}
		return { interaction_id: params?.interactionId ?? '', selection }
	}),
}))

function makePayload(kind, overrides = {}) {
	return {
		kind,
		interactionId: `${kind}-interaction`,
		data: {
			timezone: 'UTC',
			appointment_duration_minutes: 60,
			appointment_duration_note: '*Appointments last 1h.',
			availability_source: 'provider_rrule',
			requested_window_start_utc: '2026-04-14T09:00:00',
			requested_window_end_utc: '2026-04-14T15:00:00',
			provider: {
				provider_id: 1,
				name: 'Dr. Test Provider',
				specialty: 'General Practice',
			},
			availability_dtstart_utc: '2026-04-14T09:00:00',
			availability_rrule: 'FREQ=DAILY;BYHOUR=9,10,14;BYMINUTE=0;BYSECOND=0',
			blocked_slots_utc: [],
			...overrides,
		},
	}
}

async function flushUi() {
	await Promise.resolve()
	await nextTick()
	await Promise.resolve()
	await nextTick()
}

describe('Structured availability variants', () => {
	it('renders the calendar variant and emits a quick reply when a slot is selected', async () => {
		const wrapper = mount(StructuredAvailabilityPanel, {
			props: {
				payload: makePayload('availability'),
			},
		})

		await flushUi()

		expect(wrapper.text()).toContain('Availability calendar')
		const dayButton = wrapper.findAll('button').find((candidate) => candidate.text().includes('14'))
		expect(dayButton).toBeTruthy()
		await dayButton.trigger('click')
		await flushUi()

		const slotButton = wrapper.findAll('button').find((candidate) => candidate.text().includes('09:00 UTC'))
		expect(slotButton).toBeTruthy()
		await slotButton.trigger('click')
		await wrapper.findAll('button').find((candidate) => candidate.text() === 'Select slot').trigger('click')
		await flushUi()

		expect(wrapper.emitted('quick-reply')[0]).toEqual(['Please book Tue, Apr 14 at 09:00 UTC (UTC).'])
	})

	it('renders the day variant from a focused date', async () => {
		const wrapper = mount(StructuredAvailabilityDayPanel, {
			props: {
				payload: makePayload('availability_day', {
					focus_date_utc: '2026-04-14T00:00:00',
				}),
			},
		})

		await flushUi()

		expect(wrapper.text()).toContain('Selected day')
		expect(wrapper.text()).toContain('Tuesday, April 14')
		const slotButton = wrapper.findAll('button').find((candidate) => candidate.text().includes('10:00 UTC'))
		expect(slotButton).toBeTruthy()
		await slotButton.trigger('click')
		await wrapper.findAll('button').find((candidate) => candidate.text() === 'Select slot').trigger('click')
		await flushUi()

		expect(wrapper.emitted('quick-reply')[0]).toEqual(['Please book Tue, Apr 14 at 10:00 UTC (UTC).'])
	})

	it('renders the slots variant filtered by period', async () => {
		const wrapper = mount(StructuredAvailabilitySlotsPanel, {
			props: {
				payload: makePayload('availability_slots', {
					focus_date_utc: '2026-04-14T00:00:00',
					focus_period: 'morning',
					blocked_slots_utc: ['2026-04-14T10:00:00'],
				}),
			},
		})

		await flushUi()

		expect(wrapper.text()).toContain('Morning slots')
		expect(wrapper.text()).toContain('Filtered to morning')
		expect(wrapper.text()).toContain('09:00 UTC')
		expect(wrapper.text()).not.toContain('14:00 UTC')
		const slotButton = wrapper.findAll('button').find((candidate) => candidate.text().includes('09:00 UTC'))
		expect(slotButton).toBeTruthy()
		await slotButton.trigger('click')
		await wrapper.findAll('button').find((candidate) => candidate.text() === 'Select slot').trigger('click')
		await flushUi()

		expect(wrapper.emitted('quick-reply')[0]).toEqual(['Please book Tue, Apr 14 at 09:00 UTC (UTC).'])
	})
})
