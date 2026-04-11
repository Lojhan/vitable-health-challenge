import { reactive, readonly, shallowRef, watch } from 'vue'

function createFieldState(fields, initialValue) {
	return Object.fromEntries(fields.map((field) => [field, initialValue]))
}

export function useZodForm({ schema, initialValues }) {
	const fields = Object.keys(initialValues)
	const values = reactive({ ...initialValues })
	const internalErrors = reactive(createFieldState(fields, ''))
	const touchedState = reactive(createFieldState(fields, false))
	const hasSubmitted = shallowRef(false)

	function getSnapshot() {
		return fields.reduce((snapshot, field) => {
			snapshot[field] = values[field]
			return snapshot
		}, {})
	}

	function mapIssues(result) {
		const nextErrors = createFieldState(fields, '')

		if (result.success) {
			return nextErrors
		}

		for (const issue of result.error.issues) {
			const field = issue.path[0]
			if (typeof field === 'string' && field in nextErrors && !nextErrors[field]) {
				nextErrors[field] = issue.message
			}
		}

		return nextErrors
	}

	function syncErrors(nextErrors) {
		for (const field of fields) {
			internalErrors[field] = nextErrors[field] ?? ''
		}
	}

	function validate() {
		hasSubmitted.value = true
		const result = schema.safeParse(getSnapshot())
		syncErrors(mapIssues(result))
		return result
	}

	function validateField(field) {
		const result = schema.safeParse(getSnapshot())
		const nextErrors = mapIssues(result)
		internalErrors[field] = nextErrors[field] ?? ''
		return !internalErrors[field]
	}

	function markTouched(field) {
		touchedState[field] = true
		validateField(field)
	}

	function reset(nextValues = initialValues) {
		for (const field of fields) {
			values[field] = nextValues[field] ?? initialValues[field]
			internalErrors[field] = ''
			touchedState[field] = false
		}
		hasSubmitted.value = false
	}

	function isFieldInvalid(field) {
		return Boolean(internalErrors[field]) && (touchedState[field] || hasSubmitted.value)
	}

	for (const field of fields) {
		watch(
			() => values[field],
			() => {
				if (touchedState[field] || hasSubmitted.value) {
					validateField(field)
				}
			},
		)
	}

	return {
		values,
		errors: readonly(internalErrors),
		touched: readonly(touchedState),
		hasSubmitted: readonly(hasSubmitted),
		isFieldInvalid,
		markTouched,
		validate,
		reset,
	}
}