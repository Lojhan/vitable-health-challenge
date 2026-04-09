<script setup>
import { ref } from 'vue'
import ChatInterface from './components/ChatInterface.vue'
import Login from './views/Login.vue'
import Signup from './views/Signup.vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
const showSignup = ref(false)
</script>

<template>
  <ChatInterface v-if="authStore.isAuthenticated" />
  <Signup
    v-else-if="showSignup"
    @signup-success="showSignup = false"
    @go-to-login="showSignup = false"
  />
  <Login v-else @go-to-signup="showSignup = true" />
</template>
