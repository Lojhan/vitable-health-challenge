<script setup>
import StructuredAppointmentsPanel from './StructuredAppointmentsPanel.vue'
import StructuredAvailabilityDayPanel from '../availability/components/StructuredAvailabilityDayPanel.vue'
import StructuredAvailabilityPanel from '../availability/components/StructuredAvailabilityPanel.vue'
import StructuredAvailabilitySlotsPanel from '../availability/components/StructuredAvailabilitySlotsPanel.vue'
import StructuredJsonPanel from './StructuredJsonPanel.vue'
import StructuredProvidersPanel from './StructuredProvidersPanel.vue'

defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['quick-reply'])
</script>

<template>
	<section class="py-4" aria-label="Structured assistant result">
		<StructuredProvidersPanel
			v-if="payload.kind === 'providers'"
			:payload="payload"
			@quick-reply="emit('quick-reply', $event)"
		/>
		<StructuredAvailabilityPanel
			v-else-if="payload.kind === 'availability'"
			:payload="payload"
			@quick-reply="emit('quick-reply', $event)"
		/>
		<StructuredAvailabilityDayPanel
			v-else-if="payload.kind === 'availability_day'"
			:payload="payload"
			@quick-reply="emit('quick-reply', $event)"
		/>
		<StructuredAvailabilitySlotsPanel
			v-else-if="payload.kind === 'availability_slots'"
			:payload="payload"
			@quick-reply="emit('quick-reply', $event)"
		/>
		<StructuredAppointmentsPanel
			v-else-if="payload.kind === 'appointments'"
			:payload="payload"
			@quick-reply="emit('quick-reply', $event)"
		/>
		<StructuredJsonPanel
			v-else
			:payload="payload"
			@quick-reply="emit('quick-reply', $event)"
		/>
	</section>
</template>
