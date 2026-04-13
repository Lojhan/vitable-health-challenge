<script setup>
const props = defineProps({
	isLoadingSlots: {
		type: Boolean,
		required: true,
	},
	daySlots: {
		type: Array,
		required: true,
	},
	selectedSlotId: {
		type: String,
		default: '',
	},
	hasSelectedSlot: {
		type: Boolean,
		required: true,
	},
	isLocked: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(['pick-slot', 'continue'])
</script>

<template>
	<div v-if="props.isLoadingSlots" class="structured-meta px-1 py-2 text-xs">
		Loading slots...
	</div>

	<div v-else-if="props.daySlots.length" class="grid gap-2 max-h-60 overflow-scroll">
		<button
			v-for="slot in props.daySlots"
			:key="slot.id"
			type="button"
			class="cursor-pointer rounded-md border px-2.5 py-2 text-sm font-semibold transition"
			:class="props.selectedSlotId === slot.id
				? 'structured-chip structured-chip--active'
				: 'structured-chip'"
			:disabled="props.isLocked"
			@click="emit('pick-slot', slot.id)"
		>
			{{ slot.label }}
		</button>
	</div>

	<p v-else class="structured-meta m-0 text-xs">No slots available for this selection.</p>

	<button
		type="button"
		class="structured-primary-button mt-3 w-full cursor-pointer rounded-md px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed"
		:disabled="props.isLocked || !props.hasSelectedSlot"
		@click="emit('continue')"
	>
		{{ props.isLocked ? 'Slot selected' : 'Select slot' }}
	</button>
</template>
