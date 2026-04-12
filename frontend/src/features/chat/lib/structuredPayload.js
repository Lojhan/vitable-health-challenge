import { buildAvailabilityQuickActions } from '../structured/availability/lib/availabilityModel'

function normalizeStructuredState(candidate) {
	const normalized = String(candidate ?? 'final').trim().toLowerCase()
	if (['skeleton', 'partial', 'final', 'error'].includes(normalized)) {
		return normalized
	}
	return 'final'
}

function isProvider(candidate) {
	return candidate
		&& typeof candidate === 'object'
		&& 'provider_id' in candidate
		&& 'name' in candidate
		&& 'specialty' in candidate
}

function isAvailabilityPayload(candidate) {
	return Boolean(
		candidate
		&& typeof candidate === 'object'
		&& (
			typeof candidate.availability_rrule === 'string'
			|| Array.isArray(candidate.available_slots_utc)
		),
	)
}

function buildStableInteractionId(rawValue) {
	const normalized = String(rawValue ?? '')
	let hash = 5381

	for (let index = 0; index < normalized.length; index += 1) {
		hash = ((hash << 5) + hash) + normalized.charCodeAt(index)
		hash &= 0xffffffff
	}

	return `structured-${(hash >>> 0).toString(16)}`
}

function coerceInteractionId(candidate, fallback) {
	const normalized = String(candidate ?? '').trim()
	return normalized || fallback
}

function resolvePayloadKind(parsed, fallbackInteractionId) {
	const interactionId = coerceInteractionId(parsed?.interaction_id, fallbackInteractionId)
	const state = normalizeStructuredState(parsed?.ui_state)
	const progressLabel = String(parsed?.progress_message ?? '').trim()
	const errorMessage = String(parsed?.error_message ?? '').trim()

	if (Array.isArray(parsed)) {
		if (parsed.every((item) => isProvider(item))) {
			return { kind: 'providers', data: parsed, interactionId, state: 'final', progressLabel: '', errorMessage: '' }
		}
		return { kind: 'json', data: parsed, interactionId, state: 'final', progressLabel: '', errorMessage: '' }
	}

	if (!parsed || typeof parsed !== 'object') {
		return { kind: 'text', data: String(parsed ?? '') }
	}

	const normalizedType = String(parsed.type ?? parsed.kind ?? '').toLowerCase()

	if (normalizedType === 'providers' && Array.isArray(parsed.providers)) {
		return { kind: 'providers', data: parsed.providers, interactionId, state, progressLabel, errorMessage }
	}

	if (
		normalizedType === 'availability'
		&& isAvailabilityPayload(parsed)
	) {
		return { kind: 'availability', data: parsed, interactionId, state, progressLabel, errorMessage }
	}

	if (
		normalizedType === 'availability_day'
		&& isAvailabilityPayload(parsed)
	) {
		return { kind: 'availability_day', data: parsed, interactionId, state, progressLabel, errorMessage }
	}

	if (
		normalizedType === 'availability_slots'
		&& isAvailabilityPayload(parsed)
	) {
		return { kind: 'availability_slots', data: parsed, interactionId, state, progressLabel, errorMessage }
	}

	if (
		normalizedType === 'appointments'
		&& Array.isArray(parsed.appointments)
	) {
		return { kind: 'appointments', data: parsed, interactionId, state, progressLabel, errorMessage }
	}

	if (Array.isArray(parsed.providers) && parsed.providers.every((item) => isProvider(item))) {
		return { kind: 'providers', data: parsed.providers, interactionId, state, progressLabel, errorMessage }
	}

	if (isAvailabilityPayload(parsed)) {
		return { kind: 'availability', data: parsed, interactionId, state, progressLabel, errorMessage }
	}

	if (Array.isArray(parsed.appointments) && typeof parsed.count === 'number') {
		return { kind: 'appointments', data: parsed, interactionId, state, progressLabel, errorMessage }
	}

	return { kind: 'json', data: parsed, interactionId, state, progressLabel, errorMessage }
}

export function normalizeStructuredPayload(rawContent) {
	if (rawContent == null) {
		return { kind: 'text', data: '' }
	}

	if (typeof rawContent === 'object') {
		return resolvePayloadKind(rawContent, buildStableInteractionId(JSON.stringify(rawContent)))
	}

	if (typeof rawContent !== 'string') {
		return { kind: 'text', data: String(rawContent) }
	}

	const trimmed = rawContent.trim()
	if (!trimmed) {
		return { kind: 'text', data: '' }
	}

	if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
		try {
			const parsed = JSON.parse(trimmed)
			return resolvePayloadKind(parsed, buildStableInteractionId(trimmed))
		} catch (_error) {
			return { kind: 'text', data: rawContent }
		}
	}

	const fencedJsonMatch = trimmed.match(/```json\s*([\s\S]*?)```/i)
	if (fencedJsonMatch?.[1]) {
		try {
			const parsed = JSON.parse(fencedJsonMatch[1].trim())
			return resolvePayloadKind(parsed, buildStableInteractionId(fencedJsonMatch[1].trim()))
		} catch (_error) {
			return { kind: 'text', data: rawContent }
		}
	}

	return { kind: 'text', data: rawContent }
}


export function buildStructuredLeadMessage(payloadKind, payloadState = 'final', progressLabel = '') {
	if (payloadState === 'skeleton' || payloadState === 'partial') {
		return progressLabel || 'Working on a structured response for you.'
	}

	if (payloadState === 'error') {
		return 'I ran into a problem while preparing the structured result.'
	}

	if (payloadKind === 'providers') {
		return 'I found a few providers you can choose from.'
	}

	if (payloadKind === 'availability') {
		return 'Here are the next available time windows.'
	}

	if (payloadKind === 'availability_day') {
		return 'Here is the requested day with its available slots.'
	}

	if (payloadKind === 'availability_slots') {
		return 'Here are the slots that match your requested time window.'
	}

	if (payloadKind === 'appointments') {
		return 'Here is a snapshot of your upcoming appointments.'
	}

	if (payloadKind === 'json') {
		return 'I prepared structured results below.'
	}

	return ''
}

export function buildStructuredQuickActions(payload) {
	if (!payload || payload.kind === 'text' || payload.state === 'skeleton' || payload.state === 'partial' || payload.state === 'error') {
		return []
	}

	if (payload.kind === 'providers') {
		return payload.data.slice(0, 4).map((provider) => ({
			label: `Book with ${provider.name}`,
			prompt: `Book an appointment with ${provider.name} (${provider.specialty}).`,
		}))
	}

	if (
		payload.kind === 'availability'
		|| payload.kind === 'availability_day'
		|| payload.kind === 'availability_slots'
	) {
		return buildAvailabilityQuickActions(payload.data)
	}

	if (payload.kind === 'appointments') {
		return payload.data.appointments.slice(0, 3).map((appointment) => ({
			label: `Open #${appointment.appointment_id}`,
			prompt: `Show details and next steps for appointment #${appointment.appointment_id}.`,
		}))
	}

	return [{
		label: 'Continue with this data',
		prompt: 'Continue using the structured data you just shared.',
	}]
}

export function safeText(value, fallback = 'Not provided') {
	if (value == null) {
		return fallback
	}
	const normalized = String(value).trim()
	return normalized || fallback
}