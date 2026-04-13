<script setup>
defineProps({
	inputId: {
		type: String,
		default: '',
	},
	label: {
		type: String,
		required: true,
	},
	hint: {
		type: String,
		default: '',
	},
	error: {
		type: String,
		default: '',
	},
	required: {
		type: Boolean,
		default: false,
	},
})
</script>

<template>
	<div class="grid gap-2">
		<label :for="inputId" class="auth-field__label text-sm font-semibold tracking-[0.01em]">
			{{ label }}
			<span v-if="required" class="ml-1 text-red-600" aria-hidden="true">*</span>
		</label>
		<slot />
		<p v-if="error" class="m-0 text-sm leading-6 text-red-700" role="alert" aria-live="polite">
			{{ error }}
		</p>
		<p v-else-if="hint" class="auth-field__hint m-0 text-xs leading-5">
			{{ hint }}
		</p>
	</div>
</template>

<style scoped>
.auth-field__label {
	color: var(--app-text-primary);
}

.auth-field__hint {
	color: var(--app-text-secondary);
}
</style>