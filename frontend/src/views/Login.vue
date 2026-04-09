<script setup>
import { ref } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'

import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['go-to-signup'])

const authStore = useAuthStore()
const username = ref('')
const password = ref('')

async function submitLogin() {
  await authStore.login(username.value, password.value)
}
</script>

<template>
  <section class="min-h-screen grid place-content-center gap-8 p-8 bg-slate-50">
    <div class="text-center">
      <p class="text-xs tracking-[0.22em] uppercase text-indigo-500 m-0 font-semibold">Vitable Health</p>
      <h1 class="mt-2 mb-1 text-[clamp(2rem,4vw,3rem)] font-bold text-slate-900">AI Triage Console</h1>
      <p class="m-0 text-slate-500 text-sm">Secure clinician-grade symptom triage with context-aware support.</p>
    </div>

    <form
      class="w-[min(420px,92vw)] grid gap-3.5 p-8 rounded-2xl bg-white shadow-lg border border-slate-200"
      aria-label="Sign in to your account"
      novalidate
      @submit.prevent="submitLogin"
    >
      <label for="username" class="text-slate-700 font-semibold text-sm">
        Username
      </label>
      <InputText
        id="username"
        v-model="username"
        placeholder="Enter your username"
        aria-required="true"
        autocomplete="username"
        class="w-full"
      />

      <label for="login-password" class="text-slate-700 font-semibold text-sm">
        Password
      </label>
      <Password
        inputId="login-password"
        v-model="password"
        placeholder="Enter your password"
        :feedback="false"
        toggleMask
        fluid
        aria-required="true"
        autocomplete="current-password"
      />

      <p
        v-if="authStore.loginError"
        class="m-0 text-red-700 bg-red-50 border border-red-200 p-2.5 rounded-lg text-sm"
        role="alert"
        aria-live="polite"
      >
        {{ authStore.loginError }}
      </p>

      <Button
        type="submit"
        :disabled="authStore.isLoading"
        :loading="authStore.isLoading"
        label="Authenticate"
        class="w-full"
        aria-label="Sign in to your account"
      />

      <p class="text-center text-sm text-slate-500 m-0">
        New here?
        <button
          type="button"
          class="bg-transparent border-0 text-indigo-600 cursor-pointer text-[0.875rem] p-0 underline hover:text-indigo-800 focus-visible:outline-indigo-400"
          @click="emit('go-to-signup')"
        >
          Create an account
        </button>
      </p>
    </form>
  </section>
</template>

<style scoped>
/* No custom backgrounds needed — light mode uses Tailwind utilities only */
</style>
