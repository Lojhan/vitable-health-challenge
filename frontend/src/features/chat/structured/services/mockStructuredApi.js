const MOCK_NETWORK_DELAY_MS = 180
const STRUCTURED_SELECTIONS = new Map()

const PROVIDERS = [
	{
		provider_id: 1,
		name: 'Dr. Sarah Chen',
		specialty: 'General Practice',
		tagline: 'Preventive care and whole-family follow-ups.',
	},
	{
		provider_id: 2,
		name: 'Dr. Marcus Rivera',
		specialty: 'Internal Medicine',
		tagline: 'Chronic condition management with data-led care plans.',
	},
	{
		provider_id: 3,
		name: 'Dr. Priya Nair',
		specialty: 'Pediatrics',
		tagline: 'Gentle child-focused consults and long-term care tracking.',
	},
	{
		provider_id: 4,
		name: 'Dr. James Okafor',
		specialty: 'Cardiology',
		tagline: 'Cardiac risk evaluation and recovery monitoring.',
	},
	{
		provider_id: 5,
		name: 'Dr. Sofia Martins',
		specialty: 'Dermatology',
		tagline: 'Skin health consultations with practical routines.',
	},
]

const PROVIDER_PROFILES = {
	1: {
		description:
			'Dr. Sarah Chen is known for clear communication and practical next steps for acute and preventive needs.',
		reviews: [
			{ id: 'r1', author: 'Maya L.', rating: 5, text: 'Very attentive and gave me a clear action plan.' },
			{ id: 'r2', author: 'Lucas F.', rating: 4, text: 'Fast follow-up and easy to talk to.' },
		],
		pastAppointments: [
			{ id: 'a101', date: '2026-02-12', reason: 'Seasonal allergy follow-up' },
			{ id: 'a122', date: '2026-03-20', reason: 'Sore throat assessment' },
		],
	},
	2: {
		description:
			'Dr. Marcus Rivera combines diagnostics with stepwise care adjustments for complex symptoms.',
		reviews: [
			{ id: 'r3', author: 'Nora P.', rating: 5, text: 'Excellent for long-term care planning.' },
		],
		pastAppointments: [
			{ id: 'a204', date: '2026-01-09', reason: 'Blood pressure review' },
		],
	},
	3: {
		description:
			'Dr. Priya Nair focuses on pediatric continuity and parent education during treatment.',
		reviews: [
			{ id: 'r4', author: 'Amelia G.', rating: 5, text: 'Great with kids and reassuring.' },
		],
		pastAppointments: [
			{ id: 'a311', date: '2026-02-02', reason: 'Routine pediatric checkup' },
		],
	},
	4: {
		description:
			'Dr. James Okafor specializes in follow-up care after cardiac warning signs and tests.',
		reviews: [
			{ id: 'r5', author: 'Ethan D.', rating: 4, text: 'Helpful explanations about test results.' },
		],
		pastAppointments: [
			{ id: 'a411', date: '2025-12-01', reason: 'ECG follow-up discussion' },
		],
	},
	5: {
		description:
			'Dr. Sofia Martins helps patients build realistic treatment routines for recurring skin concerns.',
		reviews: [
			{ id: 'r6', author: 'Tara K.', rating: 5, text: 'Treatment worked quickly and instructions were clear.' },
		],
		pastAppointments: [
			{ id: 'a508', date: '2026-03-01', reason: 'Eczema treatment check-in' },
		],
	},
}

const SLOT_CATALOG_BY_PERIOD = {
	morning: ['08:00', '09:00', '10:00', '11:00', '12:00'],
	afternoon: ['13:00', '14:00', '15:00', '16:00', '17:00'],
	night: ['18:00', '19:00', '20:00'],
	evening: ['18:00', '19:00', '20:00'],
}

function respond(data) {
	return new Promise((resolve) => {
		setTimeout(() => resolve(data), MOCK_NETWORK_DELAY_MS)
	})
}

function normalizeInteractionId(interactionId) {
	const normalized = String(interactionId ?? '').trim()
	return normalized || ''
}

export async function fetchStructuredInteractionState(interactionId) {
	const key = normalizeInteractionId(interactionId)
	if (!key) {
		return respond({
			endpoint: '/api/chat/structured-interactions/lookup',
			interaction_id: '',
			selection: null,
		})
	}

	return respond({
		endpoint: '/api/chat/structured-interactions/lookup',
		interaction_id: key,
		selection: STRUCTURED_SELECTIONS.get(key) ?? null,
	})
}

export async function saveStructuredInteractionState({ interactionId, kind, selection } = {}) {
	const key = normalizeInteractionId(interactionId)
	if (!key || !selection || typeof selection !== 'object') {
		return respond({
			endpoint: '/api/chat/structured-interactions/save',
			interaction_id: key,
			selection: null,
		})
	}

	const nextSelection = {
		kind,
		...selection,
		saved_at: new Date().toISOString(),
	}

	STRUCTURED_SELECTIONS.set(key, nextSelection)

	return respond({
		endpoint: '/api/chat/structured-interactions/save',
		interaction_id: key,
		selection: nextSelection,
	})
}

// Mock endpoints designed to mirror future backend contracts.
export async function fetchProviders({ specialty } = {}) {
	const normalizedSpecialty = String(specialty ?? '').trim()
	const filtered = normalizedSpecialty && normalizedSpecialty !== 'All'
		? PROVIDERS.filter((provider) => provider.specialty === normalizedSpecialty)
		: PROVIDERS

	return respond({
		endpoint: '/api/chat/providers',
		providers: filtered,
		specialties: ['All', ...new Set(PROVIDERS.map((provider) => provider.specialty))],
	})
}

export async function fetchProviderProfile(providerId) {
	const provider = PROVIDERS.find((candidate) => candidate.provider_id === providerId)
	const profile = PROVIDER_PROFILES[providerId]

	return respond({
		endpoint: `/api/chat/providers/${providerId}`,
		provider,
		profile: profile ?? {
			description: 'No profile data available for this provider yet.',
			reviews: [],
			pastAppointments: [],
		},
	})
}

function formatIsoDay(date) {
	const year = date.getFullYear()
	const month = String(date.getMonth() + 1).padStart(2, '0')
	const day = String(date.getDate()).padStart(2, '0')
	return `${year}-${month}-${day}`
}

function buildMonthCalendar({ monthStartIso, groupedHumanUtc = [] }) {
	const monthStartDate = new Date(`${monthStartIso}T00:00:00`)
	const firstDay = new Date(monthStartDate.getFullYear(), monthStartDate.getMonth(), 1)
	const nextMonth = new Date(monthStartDate.getFullYear(), monthStartDate.getMonth() + 1, 1)
	const byIsoDay = new Map(
		groupedHumanUtc.map((entry) => [entry.day_iso_utc, entry]),
	)

	const days = []
	for (let d = new Date(firstDay); d < nextMonth; d.setDate(d.getDate() + 1)) {
		const isoDay = formatIsoDay(d)
		const source = byIsoDay.get(isoDay)
		days.push({
			iso_day: isoDay,
			display_day: d.getDate(),
			weekday_index: d.getDay(),
			is_available: Boolean(source),
			slot_count: source?.slot_count ?? 0,
			period: source?.period ?? null,
		})
	}

	return {
		month_start_iso: monthStartIso,
		days,
	}
}

function buildSlotsForDay({ isoDay, groupedHumanUtc = [] }) {
	const source = groupedHumanUtc.find((entry) => entry.day_iso_utc === isoDay)
	if (!source) {
		return {
			iso_day: isoDay,
			title: 'No availability',
			slots: [],
		}
	}

	const period = String(source.period ?? 'morning').toLowerCase()
	const catalog = SLOT_CATALOG_BY_PERIOD[period] ?? SLOT_CATALOG_BY_PERIOD.morning
	const slots = catalog.slice(0, source.slot_count).map((time, index) => ({
		id: `${isoDay}-${time}`,
		time,
		window: source.windows_utc?.[0] ?? '',
		label: `${time} UTC`,
		available: index < source.slot_count,
	}))

	return {
		iso_day: isoDay,
		title: `${source.day} (${period})`,
		slots,
	}
}

// Mock endpoints for availability calendar rendering and slot selection.
export async function fetchAvailabilityCalendar({ monthStartIso, groupedHumanUtc } = {}) {
	return respond({
		endpoint: '/api/chat/availability/calendar',
		calendar: buildMonthCalendar({ monthStartIso, groupedHumanUtc }),
	})
}

export async function fetchAvailabilityDaySlots({ isoDay, groupedHumanUtc } = {}) {
	return respond({
		endpoint: '/api/chat/availability/day-slots',
		day_slots: buildSlotsForDay({ isoDay, groupedHumanUtc }),
	})
}
