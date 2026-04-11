<script setup>
import { shallowRef } from 'vue'
import ChatView from './features/chat/views/ChatView.vue'
import LoginView from './features/auth/views/LoginView.vue'
import SignupView from './features/auth/views/SignupView.vue'
import { useAuthStore } from './features/auth/stores/auth'

const authStore = useAuthStore()
const showSignup = shallowRef(false)
</script>

<template>
  <ChatView v-if="authStore.isAuthenticated" />
  <SignupView
    v-else-if="showSignup"
    @signup-success="showSignup = false"
    @go-to-login="showSignup = false"
  />
  <LoginView v-else @go-to-signup="showSignup = true" />
</template>
