import { describe, expect, it } from 'vitest'

import {
	buildAvailabilityCalendar,
	buildAvailabilityDaySlots,
	findBestAvailableDay,
	getAvailabilitySlots,
} from '../availabilityModel'

function makePayload(overrides = {}) {
	return {
		timezone: 'UTC',
		requested_window_start_utc: '2026-04-14T09:00:00',
		requested_window_end_utc: '2026-04-15T15:00:00',
		availability_dtstart_utc: '2026-04-14T09:00:00',
		availability_rrule: 'FREQ=DAILY;BYHOUR=9,10,14;BYMINUTE=0;BYSECOND=0',
		blocked_slots_utc: [],
		...overrides,
	}
}

describe('availabilityModel', () => {
	it('expands RRULE occurrences and subtracts blocked slots', () => {
		const slots = getAvailabilitySlots(makePayload({
			blocked_slots_utc: ['2026-04-14T10:00:00', '2026-04-15T14:00:00'],
		}))

		expect(slots).toEqual([
			'2026-04-14T09:00:00',
			'2026-04-14T14:00:00',
			'2026-04-15T09:00:00',
			'2026-04-15T10:00:00',
		])
	})

	it('builds calendar day counts from the shared raw contract', () => {
		const calendar = buildAvailabilityCalendar({
			monthStartIso: '2026-04-01',
			payloadData: makePayload({
				blocked_slots_utc: ['2026-04-14T10:00:00'],
			}),
		})

		const april14 = calendar.days.find((day) => day.iso_day === '2026-04-14')
		const april15 = calendar.days.find((day) => day.iso_day === '2026-04-15')

		expect(april14.slot_count).toBe(2)
		expect(april15.slot_count).toBe(3)
	})

	it('derives day slots and focuses the best available day for a period', () => {
		const payloadData = makePayload({
			blocked_slots_utc: ['2026-04-14T10:00:00', '2026-04-15T09:00:00'],
		})

		expect(findBestAvailableDay(payloadData, { period: 'morning' })).toBe('2026-04-14')

		const daySlots = buildAvailabilityDaySlots({
			isoDay: '2026-04-14',
			payloadData,
			period: 'morning',
		})

		expect(daySlots.title).toContain('morning')
		expect(daySlots.slots.map((slot) => slot.iso_datetime_utc)).toEqual(['2026-04-14T09:00:00'])
	})
})
