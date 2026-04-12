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
const uiState = computed(() => String(props.payload?.state ?? 'final').trim().toLowerCase())
const progressLabel = computed(() => props.payload?.progressLabel || 'Preparing structured data...')
const errorMessage = computed(() => props.payload?.errorMessage || 'Unable to prepare structured data right now.')
</script>

<template>
	<div class="grid gap-2.5">
		<div v-if="uiState === 'skeleton' || uiState === 'partial'" class="rounded-lg border border-slate-200 bg-white px-3.5 py-3 shadow-sm">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Structured data</p>
			<p class="m-0 mt-1.5 text-sm text-slate-600">{{ progressLabel }}</p>
		</div>
		<div v-else-if="uiState === 'error'" class="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-800">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-rose-700">Structured data unavailable</p>
			<p class="m-0 mt-1.5">{{ errorMessage }}</p>
		</div>
		<template v-else>
		<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Structured data</p>
		<pre class="m-0 overflow-x-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-700">{{ JSON.stringify(payload.data, null, 2) }}</pre>
		<StructuredQuickActions :actions="actions" @quick-reply="emit('quick-reply', $event)" />
		</template>
	</div>
</template>
