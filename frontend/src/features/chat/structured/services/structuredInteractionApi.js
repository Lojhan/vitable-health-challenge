import { apiClient } from '../../../../lib/apiClient'

export async function fetchStructuredInteractionState(interactionId) {
	const key = String(interactionId ?? '').trim()
	if (!key) {
		return { interaction_id: '', selection: null }
	}

	const response = await apiClient.get(
		`/api/chat/structured-interactions/${encodeURIComponent(key)}`,
	)
	return response.data
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
	return response.data
}
