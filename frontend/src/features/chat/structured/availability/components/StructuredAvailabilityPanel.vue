<script setup>
import { computed, ref, toRef, watch } from 'vue'

import { safeText } from '../../../lib/structuredPayload'
import { useStructuredAvailabilityState } from '../composables/useStructuredAvailabilityState'
import StructuredAvailabilityCalendarGrid from './StructuredAvailabilityCalendarGrid.vue'
import StructuredAvailabilityHeader from './StructuredAvailabilityHeader.vue'
import StructuredAvailabilitySlotsList from './StructuredAvailabilitySlotsList.vue'

const props = defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['quick-reply'])
const uiState = computed(() => String(props.payload?.state ?? 'final').trim().toLowerCase())
const isSkeletonState = computed(() => uiState.value === 'skeleton')
const isPartialState = computed(() => uiState.value === 'partial')
const isErrorState = computed(() => uiState.value === 'error')
const isProgressState = computed(() => isSkeletonState.value || isPartialState.value)
const progressLabel = computed(() => props.payload?.progressLabel || 'Preparing the availability calendar...')
const errorMessage = computed(() => props.payload?.errorMessage || 'Unable to load availability right now.')

const {
	totalSlots,
	timezone,
	monthTitle,
	weekRows,
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
	isMobile,
	goToPreviousMonth,
	goToNextMonth,
	selectDay,
	selectSlot,
	saveSlotSelection,
} = useStructuredAvailabilityState(toRef(props, 'payload'))

const mobileStep = ref('date')
const selectedSlot = computed(() => daySlots.value.find((slot) => slot.id === selectedSlotId.value) ?? null)
const desktopMode = computed(() => !isMobile.value)
const isMobileDateStep = computed(() => isMobile.value && mobileStep.value === 'date')
const isMobileTimeStep = computed(() => isMobile.value && mobileStep.value === 'time')
const showDateSelection = computed(() => !isMobile.value || isMobileDateStep.value)
const showTimeSelection = computed(() => !isMobile.value || isMobileTimeStep.value)
const weekDayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

async function handleDaySelect(isoDay) {
	if (hasPastSelection.value) {
		return
	}

	await selectDay(isoDay)

	if (isMobile.value) {
		mobileStep.value = 'time'
	}
}

function handleSlotPick(slotId) {
	if (hasPastSelection.value) {
		return
	}

	selectSlot(slotId)
}

function goBackToDateStep() {
	mobileStep.value = 'date'
}

async function continueWithSlot() {
	if (!selectedDayIso.value || !selectedSlot.value || hasPastSelection.value) {
		return
	}

	await saveSlotSelection(selectedSlot.value)

	emit(
		'quick-reply',
		`Please book ${selectedDayHumanDate.value} at ${selectedSlot.value.label} (${safeText(timezone.value, 'UTC')}).`,
	)

	if (isMobile.value) {
		mobileStep.value = 'date'
	}
}

const headerTitle = computed(() => {
	if (isMobileTimeStep.value && selectedDayHumanDate.value) {
		return selectedDayHumanDate.value
	}

	return monthTitle.value
})

watch(isMobile, (mobile) => {
	if (!mobile) {
		mobileStep.value = 'date'
	}
})
</script>

<template>
	<div class="grid gap-3">
		<div v-if="isProgressState" class="grid gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-3 shadow-sm">
			<div class="flex items-center justify-between gap-2">
				<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Availability calendar</p>
				<p class="m-0 text-xs text-slate-500">{{ progressLabel }}</p>
			</div>
			<div class="grid gap-2">
				<div class="grid grid-cols-7 gap-1.5">
					<span v-for="day in 7" :key="`header-${day}`" class="h-2 rounded-full bg-slate-200 state-skeleton-line" />
				</div>
				<div class="grid grid-cols-7 gap-1.5">
					<span v-for="cell in 35" :key="cell" class="aspect-square rounded-lg bg-slate-100 state-skeleton-cell" />
				</div>
			</div>
		</div>

		<div v-else-if="isErrorState" class="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-800">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-rose-700">Availability unavailable</p>
			<p class="m-0 mt-1.5">{{ errorMessage }}</p>
		</div>

		<template v-else>
		<div v-if="isLoadingSavedSelection" class="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
			Loading your previous slot selection...
		</div>

		<div v-else-if="hasPastSelection" class="rounded-md border border-emerald-200 bg-emerald-50 p-3">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">Selected availability</p>
			<p class="m-0 mt-1 text-sm font-semibold text-emerald-900">
				{{ selectedSlotSelection.day_human }} at {{ selectedSlotSelection.slot_label }}
			</p>
			<p class="m-0 mt-0.5 text-xs text-emerald-800">Timezone: {{ selectedSlotSelection.timezone }}</p>
			<p class="m-0 mt-1 text-xs text-emerald-700">This step is completed for this message.</p>
		</div>

		<div class="flex items-center justify-between gap-2">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Availability calendar</p>
			<p class="m-0 text-xs text-slate-500">{{ totalSlots }} slots · {{ safeText(timezone, 'UTC') }}</p>
		</div>

		<div class="p-2">
			<div class="flex items-center justify-center gap-4 md:gap-6">
				<div class="grid w-full max-w-120 gap-2">
					<StructuredAvailabilityHeader
						:is-mobile="isMobile"
						:is-mobile-time-step="isMobileTimeStep"
						:header-title="headerTitle"
						@back="!hasPastSelection && goBackToDateStep()"
						@previous-month="!hasPastSelection && goToPreviousMonth()"
						@next-month="!hasPastSelection && goToNextMonth()"
					/>

					<div v-if="isLoadingCalendar" class="px-1 py-2 text-xs text-slate-600">
						Loading calendar...
					</div>

					<div v-else class="grid gap-2">
						<StructuredAvailabilityCalendarGrid
							:week-day-headers="weekDayHeaders"
							:week-rows="weekRows"
							:selected-day-iso="selectedDayIso"
							:show-date-selection="showDateSelection"
							:is-locked="hasPastSelection"
							@select-day="handleDaySelect"
						/>

						<div v-if="isMobileTimeStep" class="grid gap-2">
							<StructuredAvailabilitySlotsList
								:is-loading-slots="isLoadingSlots"
								:day-slots="daySlots"
								:selected-slot-id="selectedSlotId"
								:has-selected-slot="Boolean(selectedSlot)"
								:is-locked="hasPastSelection"
								@pick-slot="handleSlotPick"
								@continue="continueWithSlot"
							/>
						</div>
					</div>
				</div>

				<div v-if="desktopMode" class="w-full p-3 md:w-68 md:pt-11">
					<div v-if="showTimeSelection">
						<p class="text-sm font-semibold text-slate-900">{{ selectedDayTitle || 'Select a day' }}</p>
						<p v-if="selectedDayHumanDate" class="m-0 mt-0.5 text-xs text-slate-500">{{ selectedDayHumanDate }}</p>

						<div class="mt-3">
							<StructuredAvailabilitySlotsList
								:is-loading-slots="isLoadingSlots"
								:day-slots="daySlots"
								:selected-slot-id="selectedSlotId"
								:has-selected-slot="Boolean(selectedSlot)"
								:is-locked="hasPastSelection"
								@pick-slot="handleSlotPick"
								@continue="continueWithSlot"
							/>
						</div>
					</div>

					<p v-else class="mt-1 text-right text-xs text-slate-500">
						Select a date to continue.
					</p>
				</div>
			</div>
		</div>

		<p v-if="payload.data.appointment_duration_note" class="m-0 text-xs text-slate-500">
			{{ payload.data.appointment_duration_note }}
		</p>
		</template>
	</div>
</template>

<style scoped>
.state-skeleton-line,
.state-skeleton-cell {
	animation: structured-state-pulse 1s ease-in-out infinite;
}

.state-skeleton-cell:nth-child(odd) {
	animation-delay: 0.1s;
}

@keyframes structured-state-pulse {
	0%,
	100% {
		opacity: 0.52;
	}
	50% {
		opacity: 1;
	}
}
</style>
