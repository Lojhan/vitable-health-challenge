import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import { useThemeStore } from '../theme'

function createDocumentStub() {
	const activeClasses = new Set()

	return {
		documentElement: {
			classList: {
				toggle(name, active) {
					if (active) {
						activeClasses.add(name)
						return
					}

					activeClasses.delete(name)
				},
				contains(name) {
					return activeClasses.has(name)
				},
				remove(name) {
					activeClasses.delete(name)
				},
			},
			style: {},
		},
	}
}

describe('theme store', () => {
	beforeEach(() => {
		setActivePinia(createPinia())
		globalThis.localStorage?.clear?.()
		vi.unstubAllGlobals()
		vi.stubGlobal('document', createDocumentStub())
	})

	it('defaults to system preference and applies dark mode when the system preference is dark', () => {
		vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
			matches: true,
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
		}))

		const store = useThemeStore()
		store.initializeTheme()

		expect(store.preference).toBe('system')
		expect(store.resolvedTheme).toBe('dark')
		expect(document.documentElement.classList.contains('dark')).toBe(true)
		expect(document.documentElement.style.colorScheme).toBe('dark')
	})

	it('persists manual preference changes', async () => {
		vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
			matches: false,
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
		}))

		const store = useThemeStore()
		store.setPreference('dark')
		await nextTick()

		expect(store.preference).toBe('dark')
		expect(document.documentElement.classList.contains('dark')).toBe(true)
		expect(localStorage.getItem('vh_theme_preference')).toBe('dark')
	})
})