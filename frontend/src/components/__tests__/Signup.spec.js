import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { describe, expect, it } from 'vitest'
import Signup from '../../views/Signup.vue'

const mountSignup = () =>
  mount(Signup, {
    global: {
      plugins: [createPinia(), [PrimeVue, { theme: { preset: Aura } }]],
    },
  })

describe('Signup', () => {
  it('renders Insurance Plan Tier label', () => {
    const wrapper = mountSignup()
    expect(wrapper.text()).toContain('Insurance Plan Tier')
  })

  it('renders the tier Select dropdown', () => {
    const wrapper = mountSignup()
    const select = wrapper.find('[data-testid="tier-select"]')
    expect(select.exists()).toBe(true)
  })

  it('captures the selected tier in component state', async () => {
    const wrapper = mountSignup()

    // Set insuranceTier via the component's exposed reactive data by triggering
    // the Select's update:modelValue event directly
    const select = wrapper.findComponent({ name: 'Select' })
    await select.vm.$emit('update:modelValue', 'Gold')

    // The submit button should now be enabled (insuranceTier is truthy)
    const submitBtn = wrapper.find('button[type="submit"]')
    expect(submitBtn.attributes('disabled')).toBeUndefined()
  })

  it('submit button is disabled when no tier is selected', () => {
    const wrapper = mountSignup()
    const submitBtn = wrapper.find('button[type="submit"]')
    expect(submitBtn.attributes('disabled')).toBeDefined()
  })

  it('renders all three tier options inside Select', async () => {
    const wrapper = mountSignup()
    const select = wrapper.findComponent({ name: 'Select' })
    const options = select.props('options')
    const values = options.map((o) => o.value)
    expect(values).toEqual(['Bronze', 'Silver', 'Gold'])
  })
})
