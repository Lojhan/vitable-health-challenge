<script setup>
import { computed } from 'vue'

import { safeText } from '../../lib/structuredPayload'

const props = defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const uiState = computed(() => String(props.payload?.state ?? 'final').trim().toLowerCase())
const isSkeletonState = computed(() => uiState.value === 'skeleton')
const isPartialState = computed(() => uiState.value === 'partial')
const isErrorState = computed(() => uiState.value === 'error')
const isProgressState = computed(() => isSkeletonState.value || isPartialState.value)
const progressLabel = computed(() => props.payload?.progressLabel || 'Looking up your upcoming appointments...')
const errorMessage = computed(() => props.payload?.errorMessage || 'Unable to load appointments right now.')

const appointmentCountLabel = computed(() => {
	const count = Number(props.payload?.data?.count ?? props.payload?.data?.appointments?.length ?? 0)
	return `${count} upcoming appointment${count === 1 ? '' : 's'}`
})

const hasAppointments = computed(() => Array.isArray(props.payload?.data?.appointments) && props.payload.data.appointments.length > 0)
</script>

<template>
	<div class="grid gap-3">
		<div v-if="isProgressState" class="grid gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-3 shadow-sm">
			<div class="flex items-center justify-between gap-2">
				<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Upcoming appointments</p>
				<p class="m-0 text-xs text-slate-500">{{ progressLabel }}</p>
			</div>
			<div class="grid gap-2.5">
				<div v-for="index in 2" :key="index" class="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
					<div class="h-3 w-40 rounded-full bg-slate-200 state-skeleton-line" />
					<div class="mt-2 h-2.5 w-32 rounded-full bg-slate-200 state-skeleton-line state-skeleton-line-delay" />
					<div class="mt-3 h-2.5 w-full rounded-full bg-slate-200 state-skeleton-line" />
					<div class="mt-1.5 h-2.5 w-5/6 rounded-full bg-slate-200 state-skeleton-line state-skeleton-line-delay" />
				</div>
			</div>
		</div>

		<div v-else-if="isErrorState" class="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-800">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-rose-700">Appointments unavailable</p>
			<p class="m-0 mt-1.5">{{ errorMessage }}</p>
		</div>

		<template v-else>
		<div class="flex items-center justify-between gap-2">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Upcoming appointments</p>
			<p class="m-0 text-xs text-slate-500">{{ appointmentCountLabel }}</p>
		</div>

		<ul v-if="hasAppointments" class="m-0 mt-0.5 grid gap-2.5 p-0 list-none">
			<li
				v-for="appointment in payload.data.appointments"
				:key="appointment.appointment_id"
				class="rounded-md border border-slate-200 bg-white px-3 py-3"
			>
				<div class="flex items-start justify-between gap-3 border-b border-slate-100 pb-2">
					<div class="min-w-0">
						<p class="m-0 text-sm font-semibold text-slate-900">{{ safeText(appointment.title, 'Appointment') }} {{ appointment.provider_name ? 'with' : '' }} {{ safeText(appointment.provider_name, 'Unknown Provider') }}</p>
						<p class="m-0 mt-1 text-xs text-slate-600">{{ safeText(appointment.time_slot_human_utc, appointment.time_slot) }}</p>
					</div>
				</div>

				<div class="mt-2 grid gap-1.5">
					<div class="grid grid-cols-[5.5rem_1fr] items-start gap-2 text-xs">
						<p class="m-0 font-semibold text-slate-700">Reason</p>
						<p class="m-0 text-slate-600">{{ safeText(appointment.appointment_reason) }}</p>
					</div>
					<div class="grid grid-cols-[5.5rem_1fr] items-start gap-2 text-xs">
						<p class="m-0 font-semibold text-slate-700">Symptoms</p>
						<p class="m-0 text-slate-600">{{ safeText(appointment.symptoms_summary) }}</p>
					</div>
				</div>
			</li>
		</ul>

		<div v-else class="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-center">
			<p class="m-0 text-sm font-medium text-slate-700">No upcoming appointments yet</p>
			<p class="m-0 mt-1 text-xs text-slate-500">When appointments are booked, they will appear here in this timeline.</p>
		</div>
		</template>
	</div>
</template>

<style scoped>
.state-skeleton-line {
	animation: structured-state-pulse 1s ease-in-out infinite;
}

.state-skeleton-line-delay {
	animation-delay: 0.14s;
}

@keyframes structured-state-pulse {
	0%,
	100% {
		opacity: 0.52;
	}
	50% {
		opacity: 1;
	}
}
</style>
