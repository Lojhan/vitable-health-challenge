import { z } from 'zod'

import { INSURANCE_TIER_VALUES } from '../constants/insuranceTiers'

function requiredText(fieldLabel) {
	return z.string().trim().min(1, `${fieldLabel} is required`)
}

export const loginSchema = z.object({
	username: requiredText('Email or username'),
	password: requiredText('Password'),
})

export const signupSchema = z.object({
	firstName: requiredText('First name')
		.min(2, 'First name must be at least 2 characters long')
		.max(60, 'First name must be 60 characters or fewer')
		.regex(/^[\p{L}\p{M}' -]+$/u, 'First name can only contain letters, spaces, apostrophes, and hyphens'),
	email: requiredText('Email').email('Enter a valid email address'),
	password: requiredText('Password').min(8, 'Password must be at least 8 characters long'),
	insuranceTier: z
		.string()
		.trim()
		.refine((value) => INSURANCE_TIER_VALUES.includes(value), 'Select an insurance plan tier'),
})