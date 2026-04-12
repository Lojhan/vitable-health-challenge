import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useChatStore } from '../../../../stores/chat'
import {
	fetchAvailabilityCalendar,
	fetchAvailabilityDaySlots,
} from '../services/mockStructuredApi'
import {
	fetchStructuredInteractionState,
	saveStructuredInteractionState,
} from '../services/structuredInteractionApi'

function getMonthStartIso(date = new Date()) {
	const year = date.getFullYear()
	const month = String(date.getMonth() + 1).padStart(2, '0')
	return `${year}-${month}-01`
}

function startOfWeek(date) {
	const dayIndex = date.getDay()
	const weekStart = new Date(date)
	weekStart.setDate(weekStart.getDate() - dayIndex)
	return weekStart
}

function formatIsoDay(date) {
	const year = date.getFullYear()
	const month = String(date.getMonth() + 1).padStart(2, '0')
	const day = String(date.getDate()).padStart(2, '0')
	return `${year}-${month}-${day}`
}

function parseIsoDay(isoDay) {
	return new Date(`${isoDay}T00:00:00`)
}

function shiftMonthStart(monthStartIso, deltaMonths) {
	const base = new Date(`${monthStartIso}T00:00:00`)
	const shifted = new Date(base.getFullYear(), base.getMonth() + deltaMonths, 1)
	return getMonthStartIso(shifted)
}

function formatHumanDate(isoDay) {
	const parsed = new Date(`${isoDay}T00:00:00`)
	return new Intl.DateTimeFormat(undefined, {
		weekday: 'short',
		month: 'short',
		day: 'numeric',
	}).format(parsed)
}

export function useStructuredAvailability(payload) {
	const interactionId = computed(() => String(payload?.interactionId ?? '').trim())
	const timezone = computed(() => payload?.data?.timezone ?? 'UTC')
	const groupedHumanUtc = computed(() => payload?.data?.grouped_human_utc ?? [])
	const monthStartIso = ref(getMonthStartIso())
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
	const viewMode = ref('month')
	let mediaQueryList = null
	let hasHydratedSavedSelection = false

	const calendarByIsoDay = computed(() => {
		const map = new Map()
		calendarDays.value.forEach((day) => {
			map.set(day.iso_day, day)
		})
		return map
	})

	const weekRows = computed(() => {
		const rows = []
		let row = []

		const firstWeekday = calendarDays.value[0]?.weekday_index ?? 0
		for (let i = 0; i < firstWeekday; i += 1) {
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
	})

	const monthTitle = computed(() => {
		const parsed = new Date(`${monthStartIso.value}T00:00:00`)
		return new Intl.DateTimeFormat(undefined, {
			month: 'long',
			year: 'numeric',
		}).format(parsed)
	})

	const weekTitle = computed(() => {
		if (!weekStartIso.value) {
			return ''
		}

		const weekStart = parseIsoDay(weekStartIso.value)
		const weekEnd = new Date(weekStart)
		weekEnd.setDate(weekEnd.getDate() + 6)

		const formatter = new Intl.DateTimeFormat(undefined, {
			month: 'short',
			day: 'numeric',
		})

		return `${formatter.format(weekStart)} - ${formatter.format(weekEnd)}`
	})

	const weekDays = computed(() => {
		if (!weekStartIso.value) {
			return []
		}

		const start = parseIsoDay(weekStartIso.value)
		const formatter = new Intl.DateTimeFormat(undefined, { weekday: 'short' })

		return Array.from({ length: 7 }, (_value, index) => {
			const dayDate = new Date(start)
			dayDate.setDate(start.getDate() + index)
			const isoDay = formatIsoDay(dayDate)
			const source = calendarByIsoDay.value.get(isoDay)

			return {
				iso_day: isoDay,
				display_day: dayDate.getDate(),
				weekday_label: formatter.format(dayDate),
				is_available: source?.is_available ?? false,
				slot_count: source?.slot_count ?? 0,
			}
		})
	})

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
		viewMode.value = isMobile.value ? 'week' : 'month'
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
			const response = await fetchAvailabilityCalendar({
				monthStartIso: monthStartIso.value,
				groupedHumanUtc: groupedHumanUtc.value,
			})
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

	function syncWeekStartAfterMonthChange() {
		if (selectedDayIso.value) {
			setWeekStartFromDay(selectedDayIso.value)
			return
		}

		setWeekStartFromDay(calendarDays.value[0]?.iso_day ?? '')
	}

	async function loadSlotsForDay(isoDay) {
		if (!isoDay) {
			daySlots.value = []
			selectedDayTitle.value = ''
			return
		}

		isLoadingSlots.value = true
		try {
			const response = await fetchAvailabilityDaySlots({
				isoDay,
				groupedHumanUtc: groupedHumanUtc.value,
			})
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
		syncWeekStartAfterMonthChange()
	}

	async function goToNextMonth() {
		monthStartIso.value = shiftMonthStart(monthStartIso.value, 1)
		await loadCalendar()
		syncWeekStartAfterMonthChange()
	}

	async function ensureMonthForDay(isoDay) {
		const targetMonthStartIso = getMonthStartIso(parseIsoDay(isoDay))
		if (targetMonthStartIso === monthStartIso.value) {
			return
		}

		monthStartIso.value = targetMonthStartIso
		await loadCalendar()
	}

	async function goToPreviousWeek() {
		const currentAnchorIsoDay = selectedDayIso.value || weekStartIso.value
		if (!currentAnchorIsoDay) {
			return
		}

		const previousDay = parseIsoDay(currentAnchorIsoDay)
		previousDay.setDate(previousDay.getDate() - 7)
		const targetIsoDay = formatIsoDay(previousDay)

		await ensureMonthForDay(targetIsoDay)

		if (selectedDayIso.value) {
			await selectDay(targetIsoDay)
			return
		}

		setWeekStartFromDay(targetIsoDay)
	}

	async function goToNextWeek() {
		const currentAnchorIsoDay = selectedDayIso.value || weekStartIso.value
		if (!currentAnchorIsoDay) {
			return
		}

		const nextDay = parseIsoDay(currentAnchorIsoDay)
		nextDay.setDate(nextDay.getDate() + 7)
		const targetIsoDay = formatIsoDay(nextDay)

		await ensureMonthForDay(targetIsoDay)

		if (selectedDayIso.value) {
			await selectDay(targetIsoDay)
			return
		}

		setWeekStartFromDay(targetIsoDay)
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
			if (response.selection?.kind === 'availability') {
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
				kind: 'availability',
				selection: {
					day_iso_utc: selectedDayIso.value,
					day_human: selectedDayHumanDate.value,
					slot_id: slot.id,
					slot_label: slot.label,
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

		await ensureMonthForDay(persistedDayIso)
		await loadSlotsForDay(persistedDayIso)

		if (selectedSlotSelection.value.slot_id) {
			selectedSlotId.value = selectedSlotSelection.value.slot_id
		}
	}

	function setViewMode(mode) {
		if (mode !== 'week' && mode !== 'month') {
			return
		}

		viewMode.value = mode
	}

	watch(
		groupedHumanUtc,
		async () => {
			const persistedDayIso = selectedSlotSelection.value?.day_iso_utc ?? ''
			selectedDayIso.value = ''
			weekStartIso.value = ''
			await loadCalendar()

			if (hasHydratedSavedSelection && persistedDayIso) {
				await hydrateSavedSelectionIntoCalendar()
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
		monthTitle,
		weekTitle,
		weekRows,
		weekDays,
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
		viewMode,
		goToPreviousMonth,
		goToNextMonth,
		goToPreviousWeek,
		goToNextWeek,
		selectDay,
		selectSlot,
		saveSlotSelection,
		setViewMode,
	}
}
