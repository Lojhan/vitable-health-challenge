import { computed, watch } from 'vue'

import { signupSchema } from '../schemas/authSchemas'
import { useZodForm } from './useZodForm'

export function useSignupForm(authStore, options = {}) {
	const { onSuccess } = options
	const form = useZodForm({
		schema: signupSchema,
		initialValues: {
			firstName: '',
			email: '',
			password: '',
			insuranceTier: '',
		},
	})

	watch(
		[
			() => form.values.firstName,
			() => form.values.email,
			() => form.values.password,
			() => form.values.insuranceTier,
		],
		() => {
			authStore.clearSignupError()
		},
	)

	async function submit() {
		const result = form.validate()
		if (!result.success) {
			return false
		}

		const didSucceed = await authStore.signup(
			result.data.email,
			result.data.password,
			result.data.firstName,
			result.data.insuranceTier,
		)

		if (didSucceed) {
			form.reset()
			await onSuccess?.()
		}

		return didSucceed
	}

	return {
		...form,
		submit,
		isSubmitting: computed(() => authStore.isLoading),
		serverError: computed(() => authStore.signupError),
	}
}