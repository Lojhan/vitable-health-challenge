import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useChatStore } from '../../../../../stores/chat'
import {
	buildAvailabilityCalendar,
	buildAvailabilityDaySlots,
	findBestAvailableDay,
	getAvailabilityTotalSlots,
	normalizeFocusDate,
	normalizePeriod,
	parseUtcDateTime,
	toHumanDayTitle,
} from '../lib/availabilityModel'
import {
	fetchStructuredInteractionState,
	saveStructuredInteractionState,
} from '../../services/structuredInteractionApi'

function getMonthStartIso(date = new Date()) {
	const year = date.getUTCFullYear()
	const month = String(date.getUTCMonth() + 1).padStart(2, '0')
	return `${year}-${month}-01`
}

function startOfWeek(date) {
	const dayIndex = date.getUTCDay()
	const weekStart = new Date(date)
	weekStart.setUTCDate(weekStart.getUTCDate() - dayIndex)
	return weekStart
}

function formatIsoDay(date) {
	const year = date.getUTCFullYear()
	const month = String(date.getUTCMonth() + 1).padStart(2, '0')
	const day = String(date.getUTCDate()).padStart(2, '0')
	return `${year}-${month}-${day}`
}

function parseIsoDay(isoDay) {
	return new Date(`${isoDay}T00:00:00Z`)
}

function shiftMonthStart(monthStartIso, deltaMonths) {
	const base = new Date(`${monthStartIso}T00:00:00Z`)
	const shifted = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth() + deltaMonths, 1))
	return getMonthStartIso(shifted)
}

function formatHumanDate(isoDay) {
	const parsed = parseIsoDay(isoDay)
	return new Intl.DateTimeFormat(undefined, {
		weekday: 'short',
		month: 'short',
		day: 'numeric',
		timeZone: 'UTC',
	}).format(parsed)
}

function isAvailabilitySelectionKind(candidate) {
	return String(candidate ?? '').trim().startsWith('availability')
}

export function useStructuredAvailabilityState(payload, options = {}) {
	const interactionId = computed(() => String(payload?.interactionId ?? '').trim())
	const payloadKind = computed(() => String(payload?.kind ?? 'availability'))
	const timezone = computed(() => payload?.data?.timezone ?? 'UTC')
	const availabilityData = computed(() => payload?.data ?? {})
	const availabilitySignature = computed(() => JSON.stringify(availabilityData.value ?? {}))
	const focusDateIso = computed(() => normalizeFocusDate(
		options.focusDateIso ?? availabilityData.value.focus_date_utc ?? availabilityData.value.focus_datetime_utc,
	))
	const focusPeriod = computed(() => normalizePeriod(options.focusPeriod ?? availabilityData.value.focus_period))
	const totalSlots = computed(() => getAvailabilityTotalSlots(availabilityData.value))
	const initialMonthDate = parseUtcDateTime(availabilityData.value.requested_window_start_utc)
	const monthStartIso = ref(getMonthStartIso(initialMonthDate ?? new Date()))
	const calendarDays = ref([])
	const weekStartIso = ref('')
	const selectedDayIso = ref('')
	const daySlots = ref([])
	const selectedDayTitle = ref('')
	const selectedSlotId = ref('')
	const selectedSlotSelection = ref(null)
	const isLoadingCalendar = ref(false)
	const isLoadingSlots = ref(false)
	const isLoadingSavedSelection = ref(false)
	const isSavingSelection = ref(false)
	const isMobile = ref(false)
	let mediaQueryList = null
	let hasHydratedSavedSelection = false

	const selectedDayHumanDate = computed(() => (
		selectedDayIso.value ? formatHumanDate(selectedDayIso.value) : ''
	))
	const hasPastSelection = computed(() => Boolean(selectedSlotSelection.value))

	function setWeekStartFromDay(isoDay) {
		if (!isoDay) {
			weekStartIso.value = ''
			return
		}

		const selectedDayDate = parseIsoDay(isoDay)
		weekStartIso.value = formatIsoDay(startOfWeek(selectedDayDate))
	}

	function syncMobileState(event) {
		isMobile.value = Boolean(event?.matches)
	}

	function setupViewportWatcher() {
		if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
			return
		}

		mediaQueryList = window.matchMedia('(max-width: 768px)')
		syncMobileState(mediaQueryList)

		if (typeof mediaQueryList.addEventListener === 'function') {
			mediaQueryList.addEventListener('change', syncMobileState)
			return
		}

		if (typeof mediaQueryList.addListener === 'function') {
			mediaQueryList.addListener(syncMobileState)
		}
	}

	function teardownViewportWatcher() {
		if (!mediaQueryList) {
			return
		}

		if (typeof mediaQueryList.removeEventListener === 'function') {
			mediaQueryList.removeEventListener('change', syncMobileState)
		} else if (typeof mediaQueryList.removeListener === 'function') {
			mediaQueryList.removeListener(syncMobileState)
		}

		mediaQueryList = null
	}

	async function loadCalendar() {
		isLoadingCalendar.value = true
		try {
			const response = {
				calendar: buildAvailabilityCalendar({
					monthStartIso: monthStartIso.value,
					payloadData: availabilityData.value,
				}),
			}
			calendarDays.value = response.calendar.days

			if (selectedDayIso.value && !response.calendar.days.some((day) => day.iso_day === selectedDayIso.value)) {
				selectedDayIso.value = ''
				daySlots.value = []
				selectedDayTitle.value = ''
				selectedSlotId.value = ''
			}

			if (!weekStartIso.value) {
				setWeekStartFromDay(response.calendar.days[0]?.iso_day ?? '')
			}
		} finally {
			isLoadingCalendar.value = false
		}
	}

	async function loadSlotsForDay(isoDay) {
		if (!isoDay) {
			daySlots.value = []
			selectedDayTitle.value = ''
			return
		}

		isLoadingSlots.value = true
		try {
			const response = {
				day_slots: buildAvailabilityDaySlots({
					isoDay,
					payloadData: availabilityData.value,
					period: options.filterToFocusPeriod ? focusPeriod.value : '',
				}),
			}
			selectedDayTitle.value = response.day_slots.title
			daySlots.value = response.day_slots.slots
			selectedSlotId.value = ''
		} finally {
			isLoadingSlots.value = false
		}
	}

	async function goToPreviousMonth() {
		monthStartIso.value = shiftMonthStart(monthStartIso.value, -1)
		await loadCalendar()
		if (selectedDayIso.value) {
			setWeekStartFromDay(selectedDayIso.value)
		}
	}

	async function goToNextMonth() {
		monthStartIso.value = shiftMonthStart(monthStartIso.value, 1)
		await loadCalendar()
		if (selectedDayIso.value) {
			setWeekStartFromDay(selectedDayIso.value)
		}
	}

	async function selectDay(isoDay) {
		selectedDayIso.value = isoDay
		setWeekStartFromDay(isoDay)
		await loadSlotsForDay(isoDay)
	}

	function selectSlot(slotId) {
		if (hasPastSelection.value) {
			return
		}

		selectedSlotId.value = slotId
	}

	async function loadSavedSelection() {
		if (!interactionId.value) {
			hasHydratedSavedSelection = true
			return
		}

		isLoadingSavedSelection.value = true
		try {
			const response = await fetchStructuredInteractionState(interactionId.value)
			if (isAvailabilitySelectionKind(response.selection?.kind)) {
				selectedSlotSelection.value = response.selection
			}
		} finally {
			hasHydratedSavedSelection = true
			isLoadingSavedSelection.value = false
		}
	}

	async function saveSlotSelection(slot) {
		if (!slot || !selectedDayIso.value || !interactionId.value || hasPastSelection.value) {
			return
		}

		isSavingSelection.value = true
		try {
			const response = await saveStructuredInteractionState({
				interactionId: interactionId.value,
				kind: payloadKind.value,
				selection: {
					day_iso_utc: selectedDayIso.value,
					day_human: selectedDayHumanDate.value,
					slot_id: slot.id,
					slot_label: slot.label,
					slot_iso_utc: slot.iso_datetime_utc,
					timezone: timezone.value,
				},
			})

			selectedSlotSelection.value = response.selection
		} finally {
			isSavingSelection.value = false
		}
	}

	async function hydrateSavedSelectionIntoCalendar() {
		if (!selectedSlotSelection.value?.day_iso_utc) {
			return
		}

		const persistedDayIso = selectedSlotSelection.value.day_iso_utc
		selectedDayIso.value = persistedDayIso
		setWeekStartFromDay(persistedDayIso)

		if (monthStartIso.value !== getMonthStartIso(parseIsoDay(persistedDayIso))) {
			monthStartIso.value = getMonthStartIso(parseIsoDay(persistedDayIso))
			await loadCalendar()
		}
		await loadSlotsForDay(persistedDayIso)

		if (selectedSlotSelection.value.slot_id) {
			selectedSlotId.value = selectedSlotSelection.value.slot_id
		}
	}

	function resolveDefaultDayIso() {
		return findBestAvailableDay(availabilityData.value, {
			focusDateIso: focusDateIso.value,
			period: options.filterToFocusPeriod ? focusPeriod.value : '',
		})
	}

	watch(
		[availabilitySignature, focusDateIso, focusPeriod],
		async () => {
			selectedDayIso.value = ''
			weekStartIso.value = ''
			await loadCalendar()

			if (hasHydratedSavedSelection && selectedSlotSelection.value?.day_iso_utc) {
				await hydrateSavedSelectionIntoCalendar()
				return
			}

			const defaultDayIso = resolveDefaultDayIso()
			if (defaultDayIso) {
				selectedDayIso.value = defaultDayIso
				setWeekStartFromDay(defaultDayIso)
				await loadSlotsForDay(defaultDayIso)
			}
		},
		{ immediate: true },
	)

	onMounted(async () => {
		setupViewportWatcher()
		const chatStore = useChatStore()
		if (!chatStore.isStreaming) {
			await loadSavedSelection()
			if (selectedSlotSelection.value?.day_iso_utc) {
				await hydrateSavedSelectionIntoCalendar()
			}
		}
	})

	onBeforeUnmount(() => {
		teardownViewportWatcher()
	})

	return {
		timezone,
		totalSlots,
		focusDateIso,
		focusPeriod,
		monthStartIso,
		monthTitle: computed(() => new Intl.DateTimeFormat(undefined, {
			month: 'long',
			year: 'numeric',
			timeZone: 'UTC',
		}).format(parseIsoDay(monthStartIso.value))),
		selectedDayIso,
		selectedDayHumanDate,
		selectedDayTitle,
		daySlots,
		selectedSlotId,
		selectedSlotSelection,
		hasPastSelection,
		isLoadingCalendar,
		isLoadingSlots,
		isLoadingSavedSelection,
		isSavingSelection,
		isMobile,
		weekRows: computed(() => {
			const rows = []
			let row = []
			const firstWeekday = calendarDays.value[0]?.weekday_index ?? 0
			for (let index = 0; index < firstWeekday; index += 1) {
				row.push(null)
			}
			calendarDays.value.forEach((day) => {
				row.push(day)
				if (row.length === 7) {
					rows.push(row)
					row = []
				}
			})
			if (row.length > 0) {
				while (row.length < 7) {
					row.push(null)
				}
				rows.push(row)
			}
			return rows
		}),
		goToPreviousMonth,
		goToNextMonth,
		selectDay,
		selectSlot,
		saveSlotSelection,
		resolveDefaultDayTitle: computed(() => {
			if (selectedDayIso.value) {
				return toHumanDayTitle(selectedDayIso.value)
			}
			return ''
		}),
	}
}
