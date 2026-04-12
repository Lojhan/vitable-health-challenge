import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { useChatStore } from '../../../../stores/chat'
import {
	fetchProviderProfile,
	fetchProviders,
} from '../services/mockStructuredApi'
import {
	fetchStructuredInteractionState,
	saveStructuredInteractionState,
} from '../services/structuredInteractionApi'

export function useStructuredProviders(payload) {
	const interactionId = computed(() => String(payload?.interactionId ?? '').trim())
	const initialProviders = computed(() => payload?.data ?? [])
	const selectedSpecialty = ref('All')
	const specialties = ref(['All'])
	const providers = ref(initialProviders.value)
	const isLoadingProviders = ref(false)
	const isLoadingProfile = ref(false)
	const isLoadingSavedSelection = ref(false)
	const detailsOpen = ref(false)
	const selectedProviderSelection = ref(null)
	const selectedProviderDetails = ref(null)
	const isMobile = ref(false)
	let mediaQueryList = null

	const selectedProvider = computed(() => selectedProviderDetails.value?.provider ?? null)
	const selectedProfile = computed(() => selectedProviderDetails.value?.profile ?? null)
	const hasPastSelection = computed(() => Boolean(selectedProviderSelection.value))

	function updateIsMobile(event) {
		isMobile.value = Boolean(event?.matches)
	}

	function setupViewportWatcher() {
		if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
			return
		}

		mediaQueryList = window.matchMedia('(max-width: 768px)')
		updateIsMobile(mediaQueryList)

		if (typeof mediaQueryList.addEventListener === 'function') {
			mediaQueryList.addEventListener('change', updateIsMobile)
			return
		}

		if (typeof mediaQueryList.addListener === 'function') {
			mediaQueryList.addListener(updateIsMobile)
		}
	}

	function teardownViewportWatcher() {
		if (!mediaQueryList) {
			return
		}

		if (typeof mediaQueryList.removeEventListener === 'function') {
			mediaQueryList.removeEventListener('change', updateIsMobile)
		} else if (typeof mediaQueryList.removeListener === 'function') {
			mediaQueryList.removeListener(updateIsMobile)
		}

		mediaQueryList = null
	}

	async function loadProviders(specialty = selectedSpecialty.value) {
		isLoadingProviders.value = true
		try {
			const response = await fetchProviders({ specialty })
			selectedSpecialty.value = specialty || 'All'
			specialties.value = response.specialties
			providers.value = response.providers
		} finally {
			isLoadingProviders.value = false
		}
	}

	async function selectSpecialty(specialty) {
		if (hasPastSelection.value || isLoadingProviders.value || selectedSpecialty.value === specialty) {
			return
		}

		await loadProviders(specialty)
	}

	async function openProviderDetails(provider) {
		if (!provider || hasPastSelection.value || isLoadingProfile.value) {
			return
		}

		isLoadingProfile.value = true
		try {
			const response = await fetchProviderProfile(provider.provider_id)
			selectedProviderDetails.value = {
				provider: response.provider,
				profile: response.profile,
			}
			detailsOpen.value = true
		} finally {
			isLoadingProfile.value = false
		}
	}

	function closeProviderDetails() {
		detailsOpen.value = false
	}

	async function loadSavedSelection() {
		if (!interactionId.value) {
			return
		}

		isLoadingSavedSelection.value = true
		try {
			const response = await fetchStructuredInteractionState(interactionId.value)
			if (response.selection?.kind === 'providers') {
				selectedProviderSelection.value = response.selection
			}
		} finally {
			isLoadingSavedSelection.value = false
		}
	}

	async function saveProviderSelection(provider) {
		if (!provider || !interactionId.value) {
			return
		}

		const response = await saveStructuredInteractionState({
			interactionId: interactionId.value,
			kind: 'providers',
			selection: {
				provider_id: provider.provider_id,
				provider_name: provider.name,
				specialty: provider.specialty,
			},
		})

		selectedProviderSelection.value = response.selection
	}

	onMounted(async () => {
		setupViewportWatcher()
		const chatStore = useChatStore()
		if (chatStore.isStreaming) {
			await loadProviders('All')
		} else {
			await Promise.all([
				loadProviders('All'),
				loadSavedSelection(),
			])
		}
	})

	onBeforeUnmount(() => {
		teardownViewportWatcher()
	})

	return {
		selectedSpecialty,
		specialties,
		providers,
		isLoadingProviders,
		isLoadingProfile,
		detailsOpen,
		selectedProvider,
		selectedProfile,
		selectedProviderSelection,
		hasPastSelection,
		isLoadingSavedSelection,
		isMobile,
		selectSpecialty,
		openProviderDetails,
		closeProviderDetails,
		saveProviderSelection,
	}
}
