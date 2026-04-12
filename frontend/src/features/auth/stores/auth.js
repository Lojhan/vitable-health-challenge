import { computed, shallowRef } from 'vue'
import { defineStore } from 'pinia'

import {
	apiClient,
	setupAuthFailureInterceptor,
	setupAuthInterceptor,
} from '../../../lib/apiClient'

const ACCESS_TOKEN_KEY = 'vh_auth_token'
const REFRESH_TOKEN_KEY = 'vh_refresh_token'

function readStoredToken(key) {
	return localStorage.getItem(key) ?? ''
}

const responseMapping = {
    409: 'An account with that email already exists.',
}

function resolveSignupErrorMessage(error) {
	const status = error.response?.status
	return responseMapping[status] ?? 'Unable to create account. Please try again.'
}

export const useAuthStore = defineStore('auth', () => {
	const token = shallowRef(readStoredToken(ACCESS_TOKEN_KEY))
	const refreshToken = shallowRef(readStoredToken(REFRESH_TOKEN_KEY))
	const loginError = shallowRef('')
	const signupError = shallowRef('')
	const isLoading = shallowRef(false)
	let refreshPromise = null

	setupAuthInterceptor(() => token.value)
	setupAuthFailureInterceptor(async () => {
		await refreshAccessToken()
	})

	const isAuthenticated = computed(() => Boolean(token.value))

	function clearLoginError() {
		loginError.value = ''
	}

	function clearSignupError() {
		signupError.value = ''
	}

	function clearErrors() {
		clearLoginError()
		clearSignupError()
	}

	function persistToken(key, value) {
		if (value) {
			localStorage.setItem(key, value)
			return
		}

		localStorage.removeItem(key)
	}

	function setTokens(nextAccessToken, nextRefreshToken) {
		token.value = nextAccessToken ?? ''
		refreshToken.value = nextRefreshToken ?? ''

		persistToken(ACCESS_TOKEN_KEY, token.value)
		persistToken(REFRESH_TOKEN_KEY, refreshToken.value)
	}

	async function login(username, password) {
		isLoading.value = true
		clearLoginError()

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
		clearSignupError()

		try {
			await apiClient.post('/api/auth/signup', {
				email,
				password,
				first_name: firstName,
				insurance_tier: insuranceTier,
			})
			return true
		} catch (error) {
			signupError.value = resolveSignupErrorMessage(error)
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
		clearErrors()
		setTokens('', '')
	}

	return {
		token,
		refreshToken,
		loginError,
		signupError,
		isLoading,
		isAuthenticated,
		clearLoginError,
		clearSignupError,
		clearErrors,
		login,
		signup,
		refreshAccessToken,
		logout,
	}
})