<script setup>
import StructuredMessageSection from '../structured/components/StructuredMessageSection.vue'

const props = defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['quick-reply'])
</script>

<template>
	<StructuredMessageSection :payload="props.payload" @quick-reply="emit('quick-reply', $event)" />
</template>

<style scoped>
</style>