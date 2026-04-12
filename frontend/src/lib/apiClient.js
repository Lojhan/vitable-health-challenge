import axios from 'axios'

function resolveApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`
  }

  return 'http://localhost:8000'
}

const baseURL = resolveApiBaseUrl()

export const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

let interceptorId = null
let responseInterceptorId = null

export function setupAuthInterceptor(getToken) {
  if (interceptorId !== null) {
    apiClient.interceptors.request.eject(interceptorId)
  }

  interceptorId = apiClient.interceptors.request.use((config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
}

export function setupAuthFailureInterceptor(onUnauthorized) {
  if (responseInterceptorId !== null) {
    apiClient.interceptors.response.eject(responseInterceptorId)
  }

  responseInterceptorId = apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
      const status = error.response?.status
      const originalConfig = error.config

      if (
        status === 401 &&
        typeof onUnauthorized === 'function' &&
        !originalConfig?._retry
      ) {
        originalConfig._retry = true
        const refreshed = await onUnauthorized()
        if (refreshed) {
          return apiClient(originalConfig)
        }
      }

      return Promise.reject(error)
    },
  )
}

export function getApiBaseUrl() {
  return baseURL
}
