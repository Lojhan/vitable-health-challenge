<script setup>
import { computed } from 'vue'

import { safeText } from '../../../lib/structuredPayload'
import { useStructuredAvailabilityState } from '../composables/useStructuredAvailabilityState'
import StructuredAvailabilitySlotsList from './StructuredAvailabilitySlotsList.vue'

const props = defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['quick-reply'])

const {
	totalSlots,
	focusPeriod,
	timezone,
	selectedDayIso,
	selectedDayHumanDate,
	selectedDayTitle,
	daySlots,
	selectedSlotId,
	selectedSlotSelection,
	hasPastSelection,
	isLoadingSlots,
	isLoadingSavedSelection,
	selectSlot,
	saveSlotSelection,
	resolveDefaultDayTitle,
} = useStructuredAvailabilityState(props.payload, { filterToFocusPeriod: true })

const selectedSlot = computed(() => daySlots.value.find((slot) => slot.id === selectedSlotId.value) ?? null)
const sectionTitle = computed(() => {
	if (focusPeriod.value) {
		return `${focusPeriod.value.charAt(0).toUpperCase()}${focusPeriod.value.slice(1)} slots`
	}
	return 'Available slots'
})

function handleSlotPick(slotId) {
	if (hasPastSelection.value) {
		return
	}
	selectSlot(slotId)
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
}
</script>

<template>
	<div class="grid gap-3">
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
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">{{ sectionTitle }}</p>
			<p class="m-0 text-xs text-slate-500">{{ totalSlots }} total slots · {{ safeText(timezone, 'UTC') }}</p>
		</div>

		<div class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
			<p class="m-0 text-sm font-semibold text-slate-900">{{ selectedDayTitle || resolveDefaultDayTitle || 'Matching availability' }}</p>
			<p v-if="selectedDayHumanDate" class="m-0 mt-1 text-xs text-slate-500">{{ selectedDayHumanDate }}</p>
			<p v-if="focusPeriod" class="m-0 mt-1 text-xs text-indigo-700">Filtered to {{ focusPeriod }}</p>

			<div class="mt-4">
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

		<p v-if="payload.data.appointment_duration_note" class="m-0 text-xs text-slate-500">
			{{ payload.data.appointment_duration_note }}
		</p>
	</div>
</template>
