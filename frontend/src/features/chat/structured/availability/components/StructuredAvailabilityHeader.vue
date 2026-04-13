<script setup>
const props = defineProps({
	isMobile: {
		type: Boolean,
		required: true,
	},
	isMobileTimeStep: {
		type: Boolean,
		required: true,
	},
	headerTitle: {
		type: String,
		required: true,
	},
})

const emit = defineEmits(['previous-month', 'next-month', 'back'])
</script>

<template>
	<div v-if="props.isMobile" class="mb-3 flex items-center justify-between gap-2">
		<button
			v-if="props.isMobileTimeStep"
			type="button"
			class="structured-meta inline-flex cursor-pointer items-center gap-1 bg-transparent px-0 py-1 text-xs font-medium hover:text-[color:var(--app-text-primary)]"
			@click="emit('back')"
		>
			<span class="pi pi-chevron-left text-[0.7rem]" aria-hidden="true" />
			{{ props.headerTitle }}
		</button>
		<button
			v-else
			type="button"
			class="structured-meta inline-flex cursor-pointer items-center bg-transparent px-0 py-1 text-xs font-medium hover:text-[color:var(--app-text-primary)]"
			aria-label="Previous month"
			@click="emit('previous-month')"
		>
			<span class="pi pi-chevron-left text-[0.7rem]" aria-hidden="true" />
		</button>

		<p v-if="!isMobileTimeStep" class="structured-title text-sm font-semibold">{{ props.headerTitle }}</p>

		<button
			v-if="!props.isMobileTimeStep"
			type="button"
			class="structured-meta inline-flex cursor-pointer items-center bg-transparent px-0 py-1 text-xs font-medium hover:text-[color:var(--app-text-primary)]"
			aria-label="Next month"
			@click="emit('next-month')"
		>
			<span class="pi pi-chevron-right text-[0.7rem]" aria-hidden="true" />
		</button>
		<span v-else class="w-4" aria-hidden="true" />
	</div>

	<div v-else class="mb-3 flex items-center justify-center">
		<div class="inline-flex items-center gap-10">
			<button
				type="button"
				class="structured-meta inline-flex cursor-pointer items-center bg-transparent px-0 py-1 text-xs font-medium hover:text-[color:var(--app-text-primary)]"
				aria-label="Previous month"
				@click="emit('previous-month')"
			>
				<span class="pi pi-chevron-left text-[0.7rem]" aria-hidden="true" />
			</button>
			<p class="structured-title text-sm font-semibold">{{ props.headerTitle }}</p>
			<button
				type="button"
				class="structured-meta inline-flex cursor-pointer items-center bg-transparent px-0 py-1 text-xs font-medium hover:text-[color:var(--app-text-primary)]"
				aria-label="Next month"
				@click="emit('next-month')"
			>
				<span class="pi pi-chevron-right text-[0.7rem]" aria-hidden="true" />
			</button>
		</div>
	</div>
</template>
