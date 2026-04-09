import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import App from '../../App.vue'


describe('App', () => {
  it('renders healthcare heading', () => {
    const wrapper = mount(App, {
      global: {
        plugins: [
          createPinia(),
          [
            PrimeVue,
            {
              theme: { preset: Aura },
            },
          ],
        ],
      },
    })

    expect(wrapper.text()).toContain('AI Triage Console')
  })
})
