<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'

import { INSURANCE_TIER_OPTIONS } from '../constants/insuranceTiers'
import { useSignupForm } from '../composables/useSignupForm'
import { useAuthStore } from '../stores/auth'
import AuthField from './AuthField.vue'

const emit = defineEmits(['success', 'switch-mode'])

const authStore = useAuthStore()
const {
	values,
	errors,
	isFieldInvalid,
	markTouched,
	submit,
	isSubmitting,
	serverError,
} = useSignupForm(authStore, {
	onSuccess: () => emit('success'),
})

const firstNameInvalid = computed(() => isFieldInvalid('firstName'))
const emailInvalid = computed(() => isFieldInvalid('email'))
const passwordInvalid = computed(() => isFieldInvalid('password'))
const insuranceTierInvalid = computed(() => isFieldInvalid('insuranceTier'))

async function submitForm() {
	await submit()
}
</script>

<template>
	<form class="grid gap-5" aria-label="Create a new account" novalidate @submit.prevent="submitForm">
		<AuthField
			input-id="signup-first-name"
			label="First name"
			hint="We use this to personalize the triage experience."
			:error="errors.firstName"
			required
		>
			<InputText
				id="signup-first-name"
				v-model="values.firstName"
				placeholder="Jordan"
				autocomplete="given-name"
				aria-required="true"
				:invalid="firstNameInvalid"
				class="w-full"
				@blur="markTouched('firstName')"
			/>
		</AuthField>

		<AuthField
			input-id="signup-email"
			label="Email"
			hint="This becomes your sign-in identifier."
			:error="errors.email"
			required
		>
			<InputText
				id="signup-email"
				v-model="values.email"
				type="email"
				placeholder="name@clinic.com"
				autocomplete="email"
				aria-required="true"
				:invalid="emailInvalid"
				class="w-full"
				@blur="markTouched('email')"
			/>
		</AuthField>

		<AuthField
			input-id="signup-password"
			label="Password"
			hint="Use at least 8 characters."
			:error="errors.password"
			required
		>
			<Password
				input-id="signup-password"
				v-model="values.password"
				placeholder="Create a password"
				autocomplete="new-password"
				aria-required="true"
				:feedback="false"
				:invalid="passwordInvalid"
				toggle-mask
				fluid
				class="w-full"
				@blur="markTouched('password')"
			/>
		</AuthField>

		<AuthField
			input-id="insurance-tier"
			label="Insurance plan tier"
			hint="This tunes benefit-aware messaging and scheduling flows."
			:error="errors.insuranceTier"
			required
		>
			<Select
				input-id="insurance-tier"
				v-model="values.insuranceTier"
				:options="INSURANCE_TIER_OPTIONS"
				option-label="label"
				option-value="value"
				placeholder="Select your insurance tier"
				aria-required="true"
				data-testid="tier-select"
				:invalid="insuranceTierInvalid"
				class="w-full"
				@blur="markTouched('insuranceTier')"
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
			label="Create account"
			class="w-full border-primary! bg-primary! hover:border-emerald-800! hover:bg-emerald-800!"
			aria-label="Create your account"
		/>

		<p class="m-0 text-center text-sm leading-6 text-slate-500">
			Already have an account?
			<button
				type="button"
				class="border-0 bg-transparent p-0 font-semibold text-indigo-600 underline decoration-indigo-200 underline-offset-4 transition hover:text-indigo-800 focus-visible:outline-indigo-400"
				@click="emit('switch-mode')"
			>
				Sign in
			</button>
		</p>
	</form>
</template>