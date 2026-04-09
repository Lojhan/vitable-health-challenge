import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  apiClient,
  setupAuthFailureInterceptor,
  setupAuthInterceptor,
} from '../lib/apiClient'

const ACCESS_TOKEN_KEY = 'vh_auth_token'
const REFRESH_TOKEN_KEY = 'vh_refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(ACCESS_TOKEN_KEY) ?? '')
  const refreshToken = ref(localStorage.getItem(REFRESH_TOKEN_KEY) ?? '')
  const loginError = ref('')
  const signupError = ref('')
  const isLoading = ref(false)
  let refreshPromise = null

  setupAuthInterceptor(() => token.value)
  setupAuthFailureInterceptor(async () => {
    logout()
  })

  const isAuthenticated = computed(() => Boolean(token.value))

  function setTokens(nextAccessToken, nextRefreshToken) {
    token.value = nextAccessToken ?? ''
    refreshToken.value = nextRefreshToken ?? ''

    if (token.value) {
      localStorage.setItem(ACCESS_TOKEN_KEY, token.value)
    } else {
      localStorage.removeItem(ACCESS_TOKEN_KEY)
    }

    if (refreshToken.value) {
      localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken.value)
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY)
    }
  }

  async function login(username, password) {
    isLoading.value = true
    loginError.value = ''

    try {
      const response = await apiClient.post('/api/auth/token', {
        username,
        password,
      })
      setTokens(response.data.access, response.data.refresh)
      return true
    } catch (_error) {
      loginError.value = 'Unable to login with those credentials.'
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function signup(email, password, firstName, insuranceTier) {
    isLoading.value = true
    signupError.value = ''

    try {
      await apiClient.post('/api/auth/signup', {
        email,
        password,
        first_name: firstName,
        insurance_tier: insuranceTier,
      })
      return true
    } catch (error) {
      const status = error.response?.status
      signupError.value =
        status === 409
          ? 'An account with that email already exists.'
          : 'Unable to create account. Please try again.'
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function refreshAccessToken() {
    if (!refreshToken.value) {
      logout()
      return false
    }

    if (refreshPromise) {
      return refreshPromise
    }

    refreshPromise = (async () => {
      try {
        const response = await apiClient.post('/api/auth/refresh', {
          refresh: refreshToken.value,
        })
        setTokens(response.data.access, response.data.refresh)
        return true
      } catch (_error) {
        logout()
        return false
      } finally {
        refreshPromise = null
      }
    })()

    return refreshPromise
  }

  function logout() {
    setTokens('', '')
  }

  return {
    token,
    refreshToken,
    loginError,
    signupError,
    isLoading,
    isAuthenticated,
    login,
    signup,
    refreshAccessToken,
    logout,
  }
})
