const CACHE_NAMESPACE = 'vh_cache'
const CACHE_VERSION = 'v1'

function resolveStorage() {
	try {
		return globalThis.localStorage ?? null
	} catch (_error) {
		return null
	}
}

function buildStorageKey(key) {
	return `${CACHE_NAMESPACE}::${CACHE_VERSION}::${key}`
}

export function buildCacheKey(...parts) {
	return parts
		.map((part) => String(part ?? '').trim())
		.filter(Boolean)
		.join('.')
}

export function getCachedValue(key) {
	const storage = resolveStorage()
	if (!storage) {
		return null
	}

	try {
		const rawValue = storage.getItem(buildStorageKey(key))
		if (!rawValue) {
			return null
		}

		const parsedValue = JSON.parse(rawValue)
		if (!parsedValue || typeof parsedValue !== 'object') {
			storage.removeItem(buildStorageKey(key))
			return null
		}

		if (typeof parsedValue.expiresAt === 'number' && parsedValue.expiresAt <= Date.now()) {
			storage.removeItem(buildStorageKey(key))
			return null
		}

		return parsedValue.value ?? null
	} catch (_error) {
		storage.removeItem(buildStorageKey(key))
		return null
	}
}

export function setCachedValue(key, value, ttlMs) {
	const storage = resolveStorage()
	if (!storage || !Number.isFinite(ttlMs) || ttlMs <= 0) {
		return value
	}

	try {
		storage.setItem(buildStorageKey(key), JSON.stringify({
			expiresAt: Date.now() + ttlMs,
			value,
		}))
	} catch (_error) {
		return value
	}

	return value
}

export function removeCachedValue(key) {
	const storage = resolveStorage()
	if (!storage) {
		return
	}

	storage.removeItem(buildStorageKey(key))
}

export function clearCachedEntriesByPrefix(prefix = '') {
	const storage = resolveStorage()
	if (!storage) {
		return
	}

	const storagePrefix = buildStorageKey(prefix)
	const keysToRemove = []

	for (let index = 0; index < storage.length; index += 1) {
		const storageKey = storage.key(index)
		if (storageKey?.startsWith(storagePrefix)) {
			keysToRemove.push(storageKey)
		}
	}

	keysToRemove.forEach((storageKey) => {
		storage.removeItem(storageKey)
	})
}