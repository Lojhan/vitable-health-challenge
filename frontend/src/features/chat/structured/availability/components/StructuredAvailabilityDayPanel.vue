<script setup>
import { computed, toRef } from 'vue'

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
} = useStructuredAvailabilityState(toRef(props, 'payload'))

const selectedSlot = computed(() => daySlots.value.find((slot) => slot.id === selectedSlotId.value) ?? null)

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
		<div v-if="isLoadingSavedSelection" class="structured-subtle rounded-md border p-3 text-xs">
			Loading your previous slot selection...
		</div>

		<div v-else-if="hasPastSelection" class="structured-success rounded-md border p-3">
			<p class="structured-success-text m-0 text-xs font-semibold uppercase tracking-[0.12em]">Selected availability</p>
			<p class="structured-success-text m-0 mt-1 text-sm font-semibold">
				{{ selectedSlotSelection.day_human }} at {{ selectedSlotSelection.slot_label }}
			</p>
			<p class="structured-success-text m-0 mt-0.5 text-xs">Timezone: {{ selectedSlotSelection.timezone }}</p>
			<p class="structured-success-text m-0 mt-1 text-xs">This step is completed for this message.</p>
		</div>

		<div class="flex items-center justify-between gap-2">
			<p class="structured-heading m-0 text-xs font-semibold uppercase tracking-[0.14em]">Selected day</p>
			<p class="structured-meta m-0 text-xs">{{ totalSlots }} total slots · {{ safeText(timezone, 'UTC') }}</p>
		</div>

		<div class="structured-card rounded-lg border p-4 shadow-sm">
			<p class="structured-title m-0 text-sm font-semibold">{{ selectedDayTitle || resolveDefaultDayTitle || 'Availability details' }}</p>
			<p v-if="selectedDayHumanDate" class="structured-meta m-0 mt-1 text-xs">{{ selectedDayHumanDate }}</p>
			<p v-else class="structured-meta m-0 mt-1 text-xs">No exact date was supplied, so the earliest available day is shown.</p>

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

		<p v-if="payload.data.appointment_duration_note" class="structured-meta m-0 text-xs">
			{{ payload.data.appointment_duration_note }}
		</p>
	</div>
</template>
