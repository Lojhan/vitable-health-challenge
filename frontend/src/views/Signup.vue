<script setup>
import { ref } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'

import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['signup-success', 'go-to-login'])

const authStore = useAuthStore()
const email = ref('')
const password = ref('')
const firstName = ref('')
const insuranceTier = ref(null)

const tierOptions = [
  { label: 'Bronze', value: 'Bronze' },
  { label: 'Silver', value: 'Silver' },
  { label: 'Gold', value: 'Gold' },
]

async function submitSignup() {
  const ok = await authStore.signup(
    email.value,
    password.value,
    firstName.value,
    insuranceTier.value,
  )
  if (ok) {
    emit('signup-success')
  }
}
</script>

<template>
  <section class="min-h-screen grid place-content-center gap-8 p-8 bg-slate-50">
    <div class="text-center">
      <p class="text-xs tracking-[0.15em] uppercase text-indigo-500 mb-2 mt-0 font-semibold">Vitable Health</p>
      <h1 class="text-[2rem] font-bold mt-0 mb-1 text-slate-900">AI Triage Console</h1>
      <p class="text-slate-500 text-sm mt-2 mb-0">Create your account to get started.</p>
    </div>

    <form
      class="w-[min(400px,90vw)] flex flex-col gap-3 p-8 rounded-2xl bg-white shadow-lg border border-slate-200"
      aria-label="Create a new account"
      novalidate
      @submit.prevent="submitSignup"
    >
      <label for="signup-first-name" class="text-slate-700 text-sm font-medium">
        First Name
      </label>
      <InputText
        id="signup-first-name"
        v-model="firstName"
        placeholder="Enter your first name"
        aria-required="true"
        autocomplete="given-name"
        class="w-full"
      />

      <label for="signup-email" class="text-slate-700 text-sm font-medium">
        Email
      </label>
      <InputText
        id="signup-email"
        v-model="email"
        type="email"
        placeholder="Enter your email"
        aria-required="true"
        autocomplete="email"
        class="w-full"
      />

      <label for="signup-password" class="text-slate-700 text-sm font-medium">
        Password
      </label>
      <Password
        inputId="signup-password"
        v-model="password"
        placeholder="Create a password"
        :feedback="false"
        toggleMask
        fluid
        aria-required="true"
        autocomplete="new-password"
      />

      <label for="insurance-tier" class="text-slate-700 text-sm font-medium">
        Insurance Plan Tier
      </label>
      <Select
        inputId="insurance-tier"
        v-model="insuranceTier"
        :options="tierOptions"
        option-label="label"
        option-value="value"
        placeholder="Select your insurance tier"
        aria-required="true"
        data-testid="tier-select"
        class="w-full"
      />

      <p
        v-if="authStore.signupError"
        class="m-0 text-red-700 bg-red-50 border border-red-200 p-2.5 rounded-lg text-sm"
        role="alert"
        aria-live="polite"
      >
        {{ authStore.signupError }}
      </p>

      <Button
        type="submit"
        :disabled="authStore.isLoading || !insuranceTier"
        :loading="authStore.isLoading"
        label="Create Account"
        class="w-full"
        aria-label="Create your account"
      />

      <p class="text-center text-sm text-slate-500 mt-2 mb-0">
        Already have an account?
        <button
          type="button"
          class="bg-transparent border-0 cursor-pointer text-inherit p-0 underline hover:text-indigo-800 focus-visible:outline-indigo-400"
          @click="emit('go-to-login')"
        >
          Sign in
        </button>
      </p>
    </form>
  </section>
</template>

<style scoped>
/* No custom backgrounds needed — light mode uses Tailwind utilities only */
</style>
