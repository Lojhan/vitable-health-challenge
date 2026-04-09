Act as a UX and Accessibility Specialist. The healthcare UI must be perfectly usable for all patients, including those with visual impairments or using screen readers.

Tasks:

Review all Vue components (ChatInterface.vue, Login.vue, Signup.vue) and ensure adequate contrast ratios (WCAG AA compliance) for text and buttons.

Implement chat semantics using role="log" with aria-live="polite", aria-atomic="false", and aria-relevant="additions" on the chat message container so screen readers announce incoming AI messages.

Ensure the <EMERGENCY_OVERRIDE> red alert state uses aria-live="assertive" and shifts focus immediately to the emergency action button.

Ensure all form fields, specifically PrimeVue Password and Select controls, have proper label association via inputId plus clear aria-label/aria-required usage.

Save this prompt to .github/prompts/11-a11y-audit.md and execute Memory Check.