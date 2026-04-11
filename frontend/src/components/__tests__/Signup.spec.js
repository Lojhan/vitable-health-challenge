import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import SignupView from '../../features/auth/views/SignupView.vue'

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
      props: ['modelValue', 'id', 'type', 'placeholder', 'autocomplete', 'invalid'],
      emits: ['update:modelValue', 'blur'],
      template: `
        <input
          :id="id"
          :type="type || 'text'"
          :value="modelValue"
          :placeholder="placeholder"
          :autocomplete="autocomplete"
          :data-invalid="invalid"
          @input="$emit('update:modelValue', $event.target.value)"
          @blur="$emit('blur')"
        >
      `,
    }),
  }
})

vi.mock('primevue/password', async () => {
  const { defineComponent } = await import('vue')

  return {
    default: defineComponent({
      name: 'Password',
      props: ['modelValue', 'inputId', 'placeholder', 'autocomplete', 'invalid'],
      emits: ['update:modelValue', 'blur'],
      template: `
        <input
          :id="inputId"
          type="password"
          :value="modelValue"
          :placeholder="placeholder"
          :autocomplete="autocomplete"
          :data-invalid="invalid"
          @input="$emit('update:modelValue', $event.target.value)"
          @blur="$emit('blur')"
        >
      `,
    }),
  }
})

vi.mock('primevue/select', async () => {
  const { defineComponent } = await import('vue')

  return {
    default: defineComponent({
      name: 'Select',
      props: ['modelValue', 'options', 'optionLabel', 'optionValue', 'inputId', 'invalid'],
      emits: ['update:modelValue', 'blur'],
      template: `
        <select
          :id="inputId"
          data-testid="tier-select"
          :data-invalid="invalid"
          @change="$emit('update:modelValue', $event.target.value)"
          @blur="$emit('blur')"
        >
          <option value="">Select</option>
          <option
            v-for="option in options"
            :key="option[optionValue]"
            :value="option[optionValue]"
          >
            {{ option[optionLabel] }}
          </option>
        </select>
      `,
    }),
  }
})

vi.mock('primevue/button', async () => {
  const { defineComponent } = await import('vue')

  return {
    default: defineComponent({
      name: 'Button',
      props: ['label', 'disabled', 'loading', 'type'],
      template: `
        <button :type="type || 'button'" :disabled="disabled || loading">
          {{ label }}
        </button>
      `,
    }),
  }
})

const mountSignup = () =>
  mount(SignupView)

describe('Signup', () => {
  it('renders Insurance Plan Tier label', () => {
    const wrapper = mountSignup()
    expect(wrapper.text()).toContain('Insurance plan tier')
  })

  it('renders the tier Select dropdown', () => {
    const wrapper = mountSignup()
    const select = wrapper.find('[data-testid="tier-select"]')
    expect(select.exists()).toBe(true)
  })

  it('captures the selected tier in component state', async () => {
    const wrapper = mountSignup()

    const select = wrapper.findComponent({ name: 'Select' })
    await select.vm.$emit('update:modelValue', 'Gold')
    await select.vm.$emit('blur')

    expect(wrapper.text()).not.toContain('Select an insurance plan tier')
  })

  it('shows a validation error after submit when no tier is selected', async () => {
    const wrapper = mountSignup()
    await wrapper.find('form').trigger('submit')

    expect(wrapper.text()).toContain('Select an insurance plan tier')
  })

  it('renders all three tier options inside Select', async () => {
    const wrapper = mountSignup()
    const select = wrapper.findComponent({ name: 'Select' })
    const options = select.props('options')
    const values = options.map((o) => o.value)
    expect(values).toEqual(['Bronze', 'Silver', 'Gold'])
  })
})
