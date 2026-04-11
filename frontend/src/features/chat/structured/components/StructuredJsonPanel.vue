<script setup>
import { computed } from 'vue'

import { buildStructuredQuickActions } from '../../lib/structuredPayload'
import StructuredQuickActions from './StructuredQuickActions.vue'

const props = defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['quick-reply'])
const actions = computed(() => buildStructuredQuickActions(props.payload))
</script>

<template>
	<div class="grid gap-2.5">
		<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Structured data</p>
		<pre class="m-0 overflow-x-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-700">{{ JSON.stringify(payload.data, null, 2) }}</pre>
		<StructuredQuickActions :actions="actions" @quick-reply="emit('quick-reply', $event)" />
	</div>
</template>
