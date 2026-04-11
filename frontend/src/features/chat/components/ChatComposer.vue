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
		class="sticky bottom-0 z-20 border-t border-slate-200 bg-slate-50/95 px-3 py-3 backdrop-blur sm:px-4"
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
				class="w-full border-slate-200! bg-white! text-slate-800! placeholder:text-slate-400!"
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
