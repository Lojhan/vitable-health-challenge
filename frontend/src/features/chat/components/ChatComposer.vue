<script setup>
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'

defineProps({
	modelValue: {
		type: String,
		required: true,
	},
	messageInputId: {
		type: String,
		required: true,
	},
})

const emit = defineEmits(['update:modelValue', 'submit'])

function updateValue(event) {
	emit('update:modelValue', event.target.value)
}
</script>

<template>
	<form
		class="chat-composer sticky bottom-0 z-20 border-t px-3 py-3 backdrop-blur sm:px-4"
		aria-label="Send a message"
		@submit.prevent="emit('submit')"
	>
		<label :for="messageInputId" class="sr-only">
			Describe your symptoms
		</label>
		<div class="mx-auto w-full max-w-5xl">
			<div class="flex items-center gap-2">
			<InputText
				:id="messageInputId"
				:model-value="modelValue"
				placeholder="Type your symptoms..."
				aria-label="Describe your symptoms and current condition"
				class="app-themed-input chat-composer__input w-full"
				@input="updateValue"
			/>
			<Button
				type="submit"
				icon="pi pi-send"
				label="Send"
				aria-label="Send your message to the AI nurse"
				class="shrink-0 border-primary! bg-primary! text-white! hover:border-indigo-600! hover:bg-indigo-600!"
			/>
			</div>
		</div>
	</form>
</template>

<style scoped>
.chat-composer {
	border-color: var(--app-border-subtle);
	background: color-mix(in srgb, var(--app-surface-0) 94%, transparent);
	box-shadow: 0 -16px 32px -28px rgba(15, 23, 42, 0.4);
}
</style>
