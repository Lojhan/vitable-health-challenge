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
		<div v-if="uiState === 'skeleton' || uiState === 'partial'" class="structured-panel rounded-lg border px-3.5 py-3">
			<p class="structured-heading m-0 text-xs font-semibold uppercase tracking-[0.14em]">Structured data</p>
			<p class="structured-copy-muted m-0 mt-1.5 text-sm">{{ progressLabel }}</p>
		</div>
		<div v-else-if="uiState === 'error'" class="structured-danger structured-danger-text rounded-lg border px-3.5 py-3 text-sm">
			<p class="structured-danger-text m-0 text-xs font-semibold uppercase tracking-[0.14em]">Structured data unavailable</p>
			<p class="m-0 mt-1.5">{{ errorMessage }}</p>
		</div>
		<template v-else>
		<p class="structured-heading m-0 text-xs font-semibold uppercase tracking-[0.14em]">Structured data</p>
		<pre class="structured-card structured-copy-strong m-0 overflow-x-auto whitespace-pre-wrap rounded-md border p-3 text-xs leading-5">{{ JSON.stringify(payload.data, null, 2) }}</pre>
		<StructuredQuickActions :actions="actions" @quick-reply="emit('quick-reply', $event)" />
		</template>
	</div>
</template>
