import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
	buildCacheKey,
	clearCachedEntriesByPrefix,
	getCachedValue,
	removeCachedValue,
	setCachedValue,
} from '../cache'

describe('cache utility', () => {
	beforeEach(() => {
		globalThis.localStorage?.clear?.()
		vi.useRealTimers()
	})

	it('returns cached values until their ttl expires', () => {
		vi.useFakeTimers()
		const cacheKey = buildCacheKey('chat', 'history', 'initial')

		setCachedValue(cacheKey, { sessions: [1] }, 1000)
		expect(getCachedValue(cacheKey)).toEqual({ sessions: [1] })

		vi.advanceTimersByTime(1001)
		expect(getCachedValue(cacheKey)).toBe(null)
	})

	it('removes namespaced entries by prefix', () => {
		const historyKey = buildCacheKey('chat', 'history', 'initial')
		const sessionKey = buildCacheKey('chat', 'session', '7')

		setCachedValue(historyKey, { ok: true }, 1000)
		setCachedValue(sessionKey, { ok: true }, 1000)
		clearCachedEntriesByPrefix(buildCacheKey('chat', 'history'))

		expect(getCachedValue(historyKey)).toBe(null)
		expect(getCachedValue(sessionKey)).toEqual({ ok: true })

		removeCachedValue(sessionKey)
		expect(getCachedValue(sessionKey)).toBe(null)
	})
})