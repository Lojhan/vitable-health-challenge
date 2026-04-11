<script setup>
import AuthShell from '../components/AuthShell.vue'
import SignupForm from '../components/SignupForm.vue'

const emit = defineEmits(['signup-success', 'go-to-login'])
</script>

<template>
	<AuthShell
		title="Create a secure workspace for triage-first care."
		description="Set up an account once, then move between chat, scheduling, and billing-aware actions without re-entering care context."
		form-eyebrow="Provision access"
		form-title="Create your account"
		form-description="Enter your identity and coverage details to unlock the guided triage workspace."
	>
		<SignupForm @success="emit('signup-success')" @switch-mode="emit('go-to-login')" />
	</AuthShell>
</template>