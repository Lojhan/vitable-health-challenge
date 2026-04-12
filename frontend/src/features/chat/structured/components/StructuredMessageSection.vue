<script setup>
import { computed } from 'vue'

import StructuredAppointmentsPanel from './StructuredAppointmentsPanel.vue'
import StructuredAvailabilityDayPanel from '../availability/components/StructuredAvailabilityDayPanel.vue'
import StructuredAvailabilityPanel from '../availability/components/StructuredAvailabilityPanel.vue'
import StructuredAvailabilitySlotsPanel from '../availability/components/StructuredAvailabilitySlotsPanel.vue'
import StructuredJsonPanel from './StructuredJsonPanel.vue'
import StructuredProvidersPanel from './StructuredProvidersPanel.vue'

const props = defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['quick-reply'])

const componentRegistry = {
	providers: StructuredProvidersPanel,
	availability: StructuredAvailabilityPanel,
	availability_day: StructuredAvailabilityDayPanel,
	availability_slots: StructuredAvailabilitySlotsPanel,
	appointments: StructuredAppointmentsPanel,
	json: StructuredJsonPanel,
}

const resolvedComponent = computed(() => componentRegistry[props.payload.kind] ?? StructuredJsonPanel)
</script>

<template>
	<section class="py-4" aria-label="Structured assistant result">
		<component
			:is="resolvedComponent"
			:payload="payload"
			@quick-reply="emit('quick-reply', $event)"
		/>
	</section>
</template>
