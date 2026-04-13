import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import App from '../../App.vue'

const authStore = reactive({
  token: '',
  refreshToken: '',
  loginError: '',
  signupError: '',
  isLoading: false,
  isAuthenticated: false,
  clearLoginError: vi.fn(),
  clearSignupError: vi.fn(),
  clearErrors: vi.fn(),
  login: vi.fn(async () => true),
  signup: vi.fn(async () => true),
  refreshAccessToken: vi.fn(async () => true),
  logout: vi.fn(),
})

vi.mock('../../features/auth/stores/auth', () => ({
  useAuthStore: () => authStore,
}))

vi.mock('primevue/inputtext', async () => {
  const { defineComponent } = await import('vue')

  return {
    default: defineComponent({
      name: 'InputText',
      props: ['modelValue'],
      template: '<input :value="modelValue">',
    }),
  }
})

vi.mock('primevue/password', async () => {
  const { defineComponent } = await import('vue')

  return {
    default: defineComponent({
      name: 'Password',
      props: ['modelValue'],
      template: '<input type="password" :value="modelValue">',
    }),
  }
})

vi.mock('primevue/button', async () => {
  const { defineComponent } = await import('vue')

  return {
    default: defineComponent({
      name: 'Button',
      props: ['label', 'type'],
      template: `<button :type="type || 'button'">{{ label }}</button>`,
    }),
  }
})

describe('App', () => {
  it('renders the login experience by default', () => {
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia()],
      },
    })

    expect(wrapper.text()).toContain('Care navigation with a calmer front door.')
    expect(wrapper.text()).toContain('Sign in to continue symptom triage, scheduling, and billing-aware support from one operational surface.')
  })
})
