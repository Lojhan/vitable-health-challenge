<script setup>
defineProps({
	actions: {
		type: Array,
		default: () => [],
	},
})

const emit = defineEmits(['quick-reply'])
</script>

<template>
	<div v-if="actions.length" class="mt-3 flex flex-wrap gap-2">
		<button
			v-for="action in actions"
			:key="action.label"
			type="button"
			class="rounded-md border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 transition hover:border-indigo-400 hover:bg-indigo-50 cursor-pointer"
			@click="emit('quick-reply', action.prompt)"
		>
			{{ action.label }}
		</button>
	</div>
</template>
