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
	<div v-if="props.isLoadingSlots" class="px-1 py-2 text-xs text-slate-600">
		Loading slots...
	</div>

	<div v-else-if="props.daySlots.length" class="grid gap-2 max-h-60 overflow-scroll">
		<button
			v-for="slot in props.daySlots"
			:key="slot.id"
			type="button"
			class="cursor-pointer rounded-md border px-2.5 py-2 text-sm font-semibold transition"
			:class="props.selectedSlotId === slot.id
				? 'border-indigo-500 bg-indigo-50 text-indigo-700'
				: 'border-indigo-300 bg-white text-indigo-700 hover:border-indigo-500 hover:bg-indigo-50'"
			:disabled="props.isLocked"
			@click="emit('pick-slot', slot.id)"
		>
			{{ slot.label }}
		</button>
	</div>

	<p v-else class="m-0 text-xs text-slate-500">No slots available for this selection.</p>

	<button
		type="button"
		class="mt-3 w-full cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
		:disabled="props.isLocked || !props.hasSelectedSlot"
		@click="emit('continue')"
	>
		{{ props.isLocked ? 'Slot selected' : 'Select slot' }}
	</button>
</template>
