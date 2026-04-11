<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'

import { useLoginForm } from '../composables/useLoginForm'
import { useAuthStore } from '../stores/auth'
import AuthField from './AuthField.vue'

const emit = defineEmits(['switch-mode'])

const authStore = useAuthStore()
const {
	values,
	errors,
	isFieldInvalid,
	markTouched,
	submit,
	isSubmitting,
	serverError,
} = useLoginForm(authStore)

const usernameInvalid = computed(() => isFieldInvalid('username'))
const passwordInvalid = computed(() => isFieldInvalid('password'))

async function submitForm() {
	await submit()
}
</script>

<template>
	<form class="grid gap-5" aria-label="Sign in to your account" novalidate @submit.prevent="submitForm">
		<AuthField
			input-id="login-username"
			label="Email or username"
			hint="Use the same credential you use for triage access."
			:error="errors.username"
			required
		>
			<InputText
				id="login-username"
				v-model="values.username"
				placeholder="name@clinic.com"
				autocomplete="username"
				aria-required="true"
				:invalid="usernameInvalid"
				class="w-full"
				@blur="markTouched('username')"
			/>
		</AuthField>

		<AuthField
			input-id="login-password"
			label="Password"
			hint="Use your secure workspace password."
			:error="errors.password"
			required
		>
			<Password
				input-id="login-password"
				v-model="values.password"
				placeholder="Enter your password"
				autocomplete="current-password"
				aria-required="true"
				:feedback="false"
				:invalid="passwordInvalid"
				toggle-mask
				fluid
				class="w-full"
				@blur="markTouched('password')"
			/>
		</AuthField>

		<p
			v-if="serverError"
			class="m-0 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-700"
			role="alert"
			aria-live="polite"
		>
			{{ serverError }}
		</p>

		<Button
			type="submit"
			:disabled="isSubmitting"
			:loading="isSubmitting"
			label="Authenticate"
			class="w-full border-primary! bg-primary! hover:border-emerald-800! hover:bg-emerald-800!"
			aria-label="Sign in to your account"
		/>

		<p class="m-0 text-center text-sm leading-6 text-slate-500">
			New here?
			<button
				type="button"
				class="border-0 bg-transparent p-0 font-semibold text-indigo-600 underline decoration-indigo-200 underline-offset-4 transition hover:text-indigo-800 focus-visible:outline-indigo-400"
				@click="emit('switch-mode')"
			>
				Create an account
			</button>
		</p>
	</form>
</template>