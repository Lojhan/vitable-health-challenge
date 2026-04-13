import { apiClient } from '../../../../lib/apiClient'
import {
	buildCacheKey,
	getCachedValue,
	setCachedValue,
} from '../../../../lib/cache'

const STRUCTURED_STATE_TTL_MS = 60_000

function buildStructuredInteractionCacheKey(interactionId) {
	return buildCacheKey('chat', 'structured', interactionId)
}

export async function fetchStructuredInteractionState(interactionId) {
	const key = String(interactionId ?? '').trim()
	if (!key) {
		return { interaction_id: '', selection: null }
	}

	const cachedResponse = getCachedValue(buildStructuredInteractionCacheKey(key))
	if (cachedResponse && typeof cachedResponse === 'object') {
		return cachedResponse
	}

	const response = await apiClient.get(
		`/api/chat/structured-interactions/${encodeURIComponent(key)}`,
	)
	return setCachedValue(
		buildStructuredInteractionCacheKey(key),
		response.data,
		STRUCTURED_STATE_TTL_MS,
	)
}

export async function saveStructuredInteractionState({ interactionId, kind, selection } = {}) {
	const key = String(interactionId ?? '').trim()
	if (!key || !selection || typeof selection !== 'object') {
		return { interaction_id: key, selection: null }
	}

	const response = await apiClient.post('/api/chat/structured-interactions', {
		interaction_id: key,
		kind,
		selection,
	})
	return setCachedValue(
		buildStructuredInteractionCacheKey(key),
		response.data,
		STRUCTURED_STATE_TTL_MS,
	)
}
