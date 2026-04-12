<script setup>
import { computed, toRef } from 'vue'

import { useStructuredProviders } from '../composables/useStructuredProviders'

const props = defineProps({
	payload: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['quick-reply'])
const uiState = computed(() => String(props.payload?.state ?? 'final').trim().toLowerCase())
const isSkeletonState = computed(() => uiState.value === 'skeleton')
const isPartialState = computed(() => uiState.value === 'partial')
const isErrorState = computed(() => uiState.value === 'error')
const isProgressState = computed(() => isSkeletonState.value || isPartialState.value)
const progressLabel = computed(() => props.payload?.progressLabel || 'Preparing provider options...')
const errorMessage = computed(() => props.payload?.errorMessage || 'Unable to load provider options right now.')

const {
	selectedSpecialty,
	specialties,
	providers,
	isLoadingProviders,
	isLoadingProfile,
	isLoadingSavedSelection,
	detailsOpen,
	selectedProvider,
	selectedProfile,
	selectedProviderSelection,
	hasPastSelection,
	isMobile,
	selectSpecialty,
	openProviderDetails,
	closeProviderDetails,
	saveProviderSelection,
	} = useStructuredProviders(toRef(props, 'payload'))

const providerCountLabel = computed(() => {
	if (isLoadingProviders.value) {
		return 'Loading providers...'
	}
	if (providers.value.length === 0) {
		return 'No providers match this specialty.'
	}
	return `${providers.value.length} providers available`
})

async function selectProviderAndContinue(provider) {
	if (hasPastSelection.value) {
		return
	}

	await saveProviderSelection(provider)
	emit('quick-reply', `Book an appointment with ${provider.name} (${provider.specialty}).`)
	closeProviderDetails()
}

function averageRating(reviews) {
	if (!reviews || reviews.length === 0) {
		return 'No ratings yet'
	}

	const sum = reviews.reduce((acc, review) => acc + review.rating, 0)
	return `${(sum / reviews.length).toFixed(1)} / 5`
}
</script>

<template>
	<div class="grid gap-3">
		<div v-if="isProgressState" class="grid gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-3 shadow-sm">
			<div class="flex items-center justify-between gap-3">
				<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Available providers</p>
				<p class="m-0 text-xs text-slate-500">{{ progressLabel }}</p>
			</div>
			<div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
				<div v-for="index in 3" :key="index" class="rounded-lg border border-slate-200 bg-slate-50 p-3">
					<div class="h-3 w-24 rounded-full bg-slate-200 state-skeleton-line" />
					<div class="mt-2 h-2.5 w-18 rounded-full bg-slate-200 state-skeleton-line state-skeleton-line-delay" />
					<div class="mt-3 h-2.5 w-full rounded-full bg-slate-200 state-skeleton-line" />
					<div class="mt-1.5 h-2.5 w-4/5 rounded-full bg-slate-200 state-skeleton-line state-skeleton-line-delay" />
				</div>
			</div>
		</div>

		<div v-else-if="isErrorState" class="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-800">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-rose-700">Provider options unavailable</p>
			<p class="m-0 mt-1.5">{{ errorMessage }}</p>
		</div>

		<template v-else>
		<div v-if="isLoadingSavedSelection" class="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
			Loading your previous provider selection...
		</div>

		<div v-else-if="hasPastSelection" class="rounded-md border border-emerald-200 bg-emerald-50 p-3">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">Selected provider</p>
			<p class="m-0 mt-1 text-sm font-semibold text-emerald-900">{{ selectedProviderSelection.provider_name }}</p>
			<p class="m-0 mt-0.5 text-xs text-emerald-800">{{ selectedProviderSelection.specialty }}</p>
			<p class="m-0 mt-1 text-xs text-emerald-700">This step is completed for this message.</p>
		</div>

		<div class="flex items-center justify-between gap-2">
			<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Available providers</p>
			<p class="m-0 text-xs text-slate-500">{{ providerCountLabel }}</p>
		</div>

		<div class="horizontal-scroll-strip -mx-0.5 overflow-x-auto pb-0.5">
			<div class="flex min-w-max gap-2 px-0.5">
				<button
					v-for="specialty in specialties"
					:key="specialty"
					type="button"
				class="rounded-full border px-3 py-1.5 text-xs font-medium transition cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
					:disabled="hasPastSelection"
					:class="selectedSpecialty === specialty
						? 'border-indigo-600 bg-indigo-600 text-white'
						: 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:text-indigo-700'"
					@click="selectSpecialty(specialty)"
				>
					{{ specialty }}
				</button>
			</div>
		</div>

		<div class="horizontal-scroll-strip -mx-0.5 overflow-x-auto pb-1">
			<div class="flex min-w-max gap-3 px-0.5">
				<article
					v-for="provider in providers"
					:key="provider.provider_id"
					class="w-66 shrink-0 rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
				>
					<p class="m-0 text-sm font-semibold text-slate-900">{{ provider.name }}</p>
					<p class="m-0 mt-1 text-xs font-medium text-indigo-700">{{ provider.specialty }}</p>
					<p class="m-0 mt-2 text-xs text-slate-600">{{ provider.tagline }}</p>
					<button
						type="button"
						class="mt-3 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
						:disabled="hasPastSelection"
						@click="openProviderDetails(provider)"
					>
						{{ hasPastSelection ? 'Completed' : 'View profile' }}
					</button>
				</article>
			</div>
		</div>

		<div
			v-if="detailsOpen"
			class="fixed inset-0 z-40 bg-slate-950/35"
			aria-hidden="true"
			@click="closeProviderDetails"
		/>

		<section
			v-if="detailsOpen"
			:class="[
				'fixed z-60 border border-slate-200 bg-white shadow-2xl',
				isMobile
					? 'inset-x-2 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] max-h-[calc(100vh-8rem-env(safe-area-inset-bottom))] rounded-2xl px-4 py-6'
					: 'left-1/2 top-1/2 w-[min(44rem,92vw)] max-h-[86vh] -translate-x-1/2 -translate-y-1/2 rounded-lg p-5',
			]"
			aria-label="Provider profile details"
		>
			<div class="mb-4 flex items-start justify-between gap-3">
				<div>
					<p class="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Provider profile</p>
					<h4 class="m-0 mt-1 text-lg font-semibold text-slate-900">{{ selectedProvider?.name }}</h4>
					<p class="m-0 mt-0.5 text-sm text-slate-600">{{ selectedProvider?.specialty }}</p>
				</div>
			</div>

			<div v-if="isLoadingProfile" class="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
				Loading provider details...
			</div>

			<div v-else-if="selectedProfile" class="grid max-h-[calc(78vh-7rem)] gap-3 overflow-y-auto pr-1">
				<p class="m-0 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
					{{ selectedProfile.description }}
				</p>

				<div>
					<div class="flex items-center justify-between gap-2">
						<p class="m-0 text-sm font-semibold text-slate-900">Reviews</p>
						<p class="m-0 text-xs text-slate-600">{{ averageRating(selectedProfile.reviews) }}</p>
					</div>
					<ul class="m-0 mt-2 grid gap-2 p-0 list-none">
						<li
							v-for="review in selectedProfile.reviews"
							:key="review.id"
							class="rounded-md border border-slate-100 bg-slate-50 px-2.5 py-2"
						>
							<p class="m-0 text-xs font-semibold text-slate-700">{{ review.author }} · {{ review.rating }}/5</p>
							<p class="m-0 mt-1 text-xs text-slate-600">{{ review.text }}</p>
						</li>
					</ul>
				</div>

				<div>
					<p class="m-0 text-sm font-semibold text-slate-900">Past appointments</p>
					<ul class="m-0 mt-2 grid gap-2 p-0 list-none">
						<li
							v-for="appointment in selectedProfile.pastAppointments"
							:key="appointment.id"
							class="rounded-md border border-slate-100 bg-slate-50 px-2.5 py-2"
						>
							<p class="m-0 text-xs font-semibold text-slate-700">{{ appointment.date }}</p>
							<p class="m-0 mt-1 text-xs text-slate-600">{{ appointment.reason }}</p>
						</li>
					</ul>
				</div>
			</div>

			<button
				v-if="selectedProvider"
				type="button"
				class="mt-4 w-full rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500 cursor-pointer disabled:cursor-not-allowed disabled:bg-indigo-300"
				:disabled="hasPastSelection"
				@click="selectProviderAndContinue(selectedProvider)"
			>
				{{ hasPastSelection ? 'Provider already selected' : `Select ${selectedProvider.name}` }}
			</button>
		</section>
		</template>
	</div>
</template>

<style scoped>
.horizontal-scroll-strip {
	-ms-overflow-style: none;
	scrollbar-width: none;
	-webkit-overflow-scrolling: touch;
}

.horizontal-scroll-strip::-webkit-scrollbar {
	display: none;
}

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
