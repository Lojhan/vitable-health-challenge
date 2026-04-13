import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AuthShell from '../../../auth/components/AuthShell.vue'
import StructuredProvidersPanel from '../../structured/components/StructuredProvidersPanel.vue'
import StructuredAvailabilityPanel from '../../structured/availability/components/StructuredAvailabilityPanel.vue'

vi.mock('../../../../stores/chat', () => ({
	useChatStore: () => ({ isStreaming: false }),
}))

vi.mock('../../structured/services/structuredInteractionApi', () => ({
	fetchStructuredInteractionState: vi.fn(async () => ({ interaction_id: '', selection: null })),
	saveStructuredInteractionState: vi.fn(async (params) => ({ interaction_id: params?.interactionId ?? '', selection: params?.selection ?? null })),
}))

describe('dark mode surface regressions', () => {
	it('renders auth shell copy and eyebrow with semantic dark-mode classes', () => {
		const wrapper = mount(AuthShell, {
			props: {
				title: 'Care navigation with a calmer front door.',
				description: 'Sign in to continue symptom triage, scheduling, and billing-aware support from one operational surface.',
				formEyebrow: 'Secure access',
				formTitle: 'Welcome back',
				formDescription: 'Authenticate with your existing account to continue where the last conversation left off.',
			},
			slots: {
				default: '<div>form slot</div>',
			},
			global: {
				stubs: {
					ThemePreferenceControl: true,
				},
			},
		})

		expect(wrapper.get('.auth-shell__eyebrow').text()).toContain('Secure access')
		expect(wrapper.get('.auth-shell__description').text()).toContain('Authenticate with your existing account')
		expect(wrapper.get('.auth-shell__hero-copy').text()).toContain('Sign in to continue symptom triage')
	})

	it('renders providers panels with structured dark-mode surface classes', () => {
		const wrapper = mount(StructuredProvidersPanel, {
			props: {
				payload: {
					kind: 'providers',
					interactionId: 'providers-dark-regression',
					data: [
						{ provider_id: 1, name: 'Dr. Sarah Chen', specialty: 'General Practice', tagline: 'Preventive care and whole-family follow-ups.' },
					],
				},
			},
		})

		expect(wrapper.get('.structured-heading').text()).toContain('Available providers')
		expect(wrapper.get('.structured-card').text()).toContain('Dr. Sarah Chen')
		expect(wrapper.get('.structured-secondary-button').text()).toContain('View profile')
	})

	it('renders availability panel surfaces with structured dark-mode classes', () => {
		const wrapper = mount(StructuredAvailabilityPanel, {
			props: {
				payload: {
					kind: 'availability',
					interactionId: 'availability-dark-regression',
					data: {
						timezone: 'UTC',
						appointment_duration_note: '*Appointments last 1h.',
						appointment_duration_minutes: 60,
						requested_window_start_utc: '2026-04-14T09:00:00',
						requested_window_end_utc: '2026-04-14T15:00:00',
						availability_source: 'provider_rrule',
						provider: { provider_id: 1, name: 'Dr. Test Provider', specialty: 'General Practice' },
						availability_dtstart_utc: '2026-04-14T09:00:00',
						availability_rrule: 'FREQ=DAILY;BYHOUR=9,10,14;BYMINUTE=0;BYSECOND=0',
						blocked_slots_utc: [],
					},
				},
			},
		})

		expect(wrapper.get('.structured-heading').text()).toContain('Availability calendar')
		expect(wrapper.find('.structured-title').exists()).toBe(true)
		expect(wrapper.findAll('.structured-chip').length).toBeGreaterThan(0)
	})
})