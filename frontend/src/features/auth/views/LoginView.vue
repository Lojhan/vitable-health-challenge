<script setup>
import LoginForm from '../components/LoginForm.vue'
import AuthShell from '../components/AuthShell.vue'

const emit = defineEmits(['go-to-signup'])
</script>

<template>
	<AuthShell
		title="Care navigation with a calmer front door."
		description="Sign in to continue symptom triage, scheduling, and billing-aware support from one operational surface."
		form-eyebrow="Secure access"
		form-title="Welcome back"
		form-description="Authenticate with your existing account to continue where the last conversation left off."
	>
		<LoginForm @switch-mode="emit('go-to-signup')" />
	</AuthShell>
</template>