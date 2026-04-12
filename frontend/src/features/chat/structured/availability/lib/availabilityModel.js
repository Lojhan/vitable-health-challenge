import { rrulestr } from 'rrule'

function pad(value) {
	return String(value).padStart(2, '0')
}

export function parseUtcDateTime(isoDateTime) {
	const normalized = String(isoDateTime ?? '').trim()
	if (!normalized) {
		return null
	}

	if (normalized.endsWith('Z') || /[+-]\d\d:\d\d$/.test(normalized)) {
		return new Date(normalized)
	}

	return new Date(`${normalized}Z`)
}

export function formatIsoDateTime(date) {
	return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`
}

export function formatIsoDay(date) {
	return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
}

export function normalizeFocusDate(candidate) {
	const parsed = parseUtcDateTime(candidate)
	if (!parsed || Number.isNaN(parsed.getTime())) {
		return ''
	}
	return formatIsoDay(parsed)
}

export function normalizePeriod(candidate) {
	const normalized = String(candidate ?? '').trim().toLowerCase()
	if (normalized === 'morning' || normalized === 'afternoon' || normalized === 'night' || normalized === 'evening') {
		return normalized
	}
	return ''
}

function periodForHour(hour) {
	if (hour < 12) {
		return 'morning'
	}
	if (hour < 18) {
		return 'afternoon'
	}
	return 'evening'
}

export function toUtcDisplayLabel(isoDateTime) {
	const parsed = parseUtcDateTime(isoDateTime)
	if (!parsed || Number.isNaN(parsed.getTime())) {
		return 'Unavailable'
	}

	return `${pad(parsed.getUTCHours())}:${pad(parsed.getUTCMinutes())} UTC`
}

export function toHumanDayTitle(isoDay) {
	const parsed = parseUtcDateTime(`${isoDay}T00:00:00`)
	if (!parsed || Number.isNaN(parsed.getTime())) {
		return 'No availability'
	}

	return new Intl.DateTimeFormat(undefined, {
		weekday: 'long',
		month: 'long',
		day: 'numeric',
		timeZone: 'UTC',
	}).format(parsed)
}

function sortIsoDateTimes(values) {
	return [...new Set(values)].sort((left, right) => left.localeCompare(right))
}

export function getAvailabilitySlots(payloadData = {}) {
	if (
		Array.isArray(payloadData.available_slots_utc)
		&& (
			payloadData.available_slots_utc.length > 0
			|| payloadData.availability_source === 'open_slots'
		)
	) {
		return sortIsoDateTimes(payloadData.available_slots_utc)
	}

	const dtstart = parseUtcDateTime(payloadData.availability_dtstart_utc)
	const windowStart = parseUtcDateTime(payloadData.requested_window_start_utc)
	const windowEnd = parseUtcDateTime(payloadData.requested_window_end_utc)
	const ruleText = String(payloadData.availability_rrule ?? '').trim()

	if (!dtstart || !windowStart || !windowEnd || !ruleText) {
		return []
	}

	try {
		const rule = rrulestr(ruleText, { dtstart })
		const blockedSlots = new Set(payloadData.blocked_slots_utc ?? [])
		return sortIsoDateTimes(
			rule
				.between(windowStart, windowEnd, true)
				.map((occurrence) => formatIsoDateTime(occurrence))
				.filter((isoDateTime) => !blockedSlots.has(isoDateTime)),
		)
	} catch (_error) {
		return []
	}
}

export function getAvailabilityTotalSlots(payloadData = {}) {
	return getAvailabilitySlots(payloadData).length
}

export function getAvailabilityIsoDays(payloadData = {}, { period = '' } = {}) {
	const normalizedPeriod = normalizePeriod(period)
	const days = new Set()

	for (const slot of getAvailabilitySlots(payloadData)) {
		const parsed = parseUtcDateTime(slot)
		if (!parsed || Number.isNaN(parsed.getTime())) {
			continue
		}
		if (normalizedPeriod && periodForHour(parsed.getUTCHours()) !== normalizedPeriod) {
			continue
		}
		days.add(formatIsoDay(parsed))
	}

	return [...days].sort((left, right) => left.localeCompare(right))
}

export function findBestAvailableDay(payloadData = {}, { focusDateIso = '', period = '' } = {}) {
	const normalizedFocusDate = normalizeFocusDate(focusDateIso)
	const isoDays = getAvailabilityIsoDays(payloadData, { period })
	if (normalizedFocusDate && isoDays.includes(normalizedFocusDate)) {
		return normalizedFocusDate
	}
	return isoDays[0] ?? ''
}

export function buildAvailabilityCalendar({ monthStartIso, payloadData } = {}) {
	const monthStartDate = parseUtcDateTime(`${monthStartIso}T00:00:00`)
	if (!monthStartDate || Number.isNaN(monthStartDate.getTime())) {
		return {
			month_start_iso: monthStartIso,
			days: [],
		}
	}

	const nextMonth = new Date(Date.UTC(
		monthStartDate.getUTCFullYear(),
		monthStartDate.getUTCMonth() + 1,
		1,
	))
	const byIsoDay = new Map()

	for (const isoDay of getAvailabilityIsoDays(payloadData)) {
		byIsoDay.set(isoDay, 0)
	}

	for (const slot of getAvailabilitySlots(payloadData)) {
		const slotDate = parseUtcDateTime(slot)
		const isoDay = formatIsoDay(slotDate)
		byIsoDay.set(isoDay, (byIsoDay.get(isoDay) ?? 0) + 1)
	}

	const days = []
	for (
		let cursor = new Date(Date.UTC(monthStartDate.getUTCFullYear(), monthStartDate.getUTCMonth(), 1));
		cursor < nextMonth;
		cursor.setUTCDate(cursor.getUTCDate() + 1)
	) {
		const isoDay = formatIsoDay(cursor)
		const slotCount = byIsoDay.get(isoDay) ?? 0
		days.push({
			iso_day: isoDay,
			display_day: cursor.getUTCDate(),
			weekday_index: cursor.getUTCDay(),
			is_available: slotCount > 0,
			slot_count: slotCount,
		})
	}

	return {
		month_start_iso: monthStartIso,
		days,
	}
}

export function buildAvailabilityDaySlots({ isoDay, payloadData, period = '' } = {}) {
	const normalizedPeriod = normalizePeriod(period)
	const slots = getAvailabilitySlots(payloadData)
		.filter((slot) => slot.startsWith(`${isoDay}T`))
		.filter((slot) => {
			if (!normalizedPeriod) {
				return true
			}
			const parsed = parseUtcDateTime(slot)
			return periodForHour(parsed.getUTCHours()) === normalizedPeriod
		})
		.map((slot) => ({
			id: slot,
			iso_datetime_utc: slot,
			label: toUtcDisplayLabel(slot),
			period: periodForHour(parseUtcDateTime(slot).getUTCHours()),
			available: true,
		}))

	const title = slots.length > 0 ? toHumanDayTitle(isoDay) : 'No availability'
	return {
		iso_day: isoDay,
		title: normalizedPeriod && slots.length > 0 ? `${title} (${normalizedPeriod})` : title,
		slots,
	}
}

export function buildAvailabilityQuickActions(payloadData = {}, limit = 2) {
	return getAvailabilitySlots(payloadData).slice(0, limit).map((slot) => {
		const isoDay = slot.slice(0, 10)
		const dayLabel = new Intl.DateTimeFormat(undefined, {
			weekday: 'short',
			month: 'short',
			day: 'numeric',
			timeZone: 'UTC',
		}).format(parseUtcDateTime(`${isoDay}T00:00:00`))
		const slotLabel = toUtcDisplayLabel(slot)

		return {
			label: `Pick ${slotLabel}`,
			prompt: `Please book ${dayLabel} at ${slotLabel}.`,
		}
	})
}
