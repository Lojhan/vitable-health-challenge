import { computed, watch } from 'vue'

import { loginSchema } from '../schemas/authSchemas'
import { useZodForm } from './useZodForm'

export function useLoginForm(authStore) {
	const form = useZodForm({
		schema: loginSchema,
		initialValues: {
			username: '',
			password: '',
		},
	})

	watch(
		[() => form.values.username, () => form.values.password],
		() => {
			authStore.clearLoginError()
		},
	)

	async function submit() {
		const result = form.validate()
		if (!result.success) {
			return false
		}

		return authStore.login(result.data.username, result.data.password)
	}

	return {
		...form,
		submit,
		isSubmitting: computed(() => authStore.isLoading),
		serverError: computed(() => authStore.loginError),
	}
}