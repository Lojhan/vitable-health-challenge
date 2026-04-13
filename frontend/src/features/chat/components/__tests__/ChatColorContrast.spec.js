import { readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

const STYLE_SHEET_PATH = path.resolve(process.cwd(), 'src/style.css')
const STYLE_SHEET = readFileSync(STYLE_SHEET_PATH, 'utf8')

function extractCssBlock(selector) {
	const startIndex = STYLE_SHEET.indexOf(`${selector} {`)
	if (startIndex < 0) {
		throw new Error(`Missing CSS block for ${selector}`)
	}

	const blockStart = STYLE_SHEET.indexOf('{', startIndex)
	let depth = 0
	for (let index = blockStart; index < STYLE_SHEET.length; index += 1) {
		const character = STYLE_SHEET[index]
		if (character === '{') {
			depth += 1
		}
		if (character === '}') {
			depth -= 1
			if (depth === 0) {
				return STYLE_SHEET.slice(blockStart + 1, index)
			}
		}
	}

	throw new Error(`Unterminated CSS block for ${selector}`)
}

function parseVariables(block) {
	return Object.fromEntries(
		block
			.split('\n')
			.map((line) => line.trim())
			.filter((line) => line.startsWith('--'))
			.map((line) => {
				const [name, ...rest] = line.split(':')
				return [name.trim(), rest.join(':').replace(/;$/, '').trim()]
			}),
	)
}

const LIGHT_THEME_VARIABLES = parseVariables(extractCssBlock(':root'))
const DARK_THEME_VARIABLES = {
	...LIGHT_THEME_VARIABLES,
	...parseVariables(extractCssBlock(':root.dark')),
}

function resolveThemeValue(variables, token, seen = new Set()) {
	if (seen.has(token)) {
		throw new Error(`Circular CSS variable reference for ${token}`)
	}

	const rawValue = variables[token]
	if (!rawValue) {
		throw new Error(`Missing CSS variable ${token}`)
	}

	const varMatch = rawValue.match(/^var\((--[^)]+)\)$/)
	if (varMatch) {
		return resolveThemeValue(variables, varMatch[1], new Set([...seen, token]))
	}

	return rawValue
}

function parseChannelValue(value) {
	return Number.parseFloat(value.trim())
}

function parseColor(value) {
	const normalized = value.trim().toLowerCase()

	if (normalized.startsWith('#')) {
		const hex = normalized.slice(1)
		if (hex.length === 6) {
			return {
				r: Number.parseInt(hex.slice(0, 2), 16),
				g: Number.parseInt(hex.slice(2, 4), 16),
				b: Number.parseInt(hex.slice(4, 6), 16),
				a: 1,
			}
		}
	}

	const rgbMatch = normalized.match(/^rgba?\(([^)]+)\)$/)
	if (rgbMatch) {
		const channels = rgbMatch[1].split(',').map(parseChannelValue)
		return {
			r: channels[0],
			g: channels[1],
			b: channels[2],
			a: channels[3] ?? 1,
		}
	}

	throw new Error(`Unsupported color value: ${value}`)
}

function compositeColor(foreground, background) {
	const alpha = foreground.a ?? 1
	if (alpha >= 1) {
		return { r: foreground.r, g: foreground.g, b: foreground.b, a: 1 }
	}

	return {
		r: (foreground.r * alpha) + (background.r * (1 - alpha)),
		g: (foreground.g * alpha) + (background.g * (1 - alpha)),
		b: (foreground.b * alpha) + (background.b * (1 - alpha)),
		a: 1,
	}
}

function toRelativeLuminance(channel) {
	const normalized = channel / 255
	if (normalized <= 0.03928) {
		return normalized / 12.92
	}

	return ((normalized + 0.055) / 1.055) ** 2.4
}

function contrastRatio(foreground, background) {
	const foregroundLuminance = (
		(0.2126 * toRelativeLuminance(foreground.r))
		+ (0.7152 * toRelativeLuminance(foreground.g))
		+ (0.0722 * toRelativeLuminance(foreground.b))
	)
	const backgroundLuminance = (
		(0.2126 * toRelativeLuminance(background.r))
		+ (0.7152 * toRelativeLuminance(background.g))
		+ (0.0722 * toRelativeLuminance(background.b))
	)

	const lighter = Math.max(foregroundLuminance, backgroundLuminance)
	const darker = Math.min(foregroundLuminance, backgroundLuminance)
	return (lighter + 0.05) / (darker + 0.05)
}

function resolveContrastRatio(variables, foregroundToken, backgroundToken, fallbackBackgroundToken = '--app-page-bg') {
	const foregroundColor = parseColor(resolveThemeValue(variables, foregroundToken))
	const backgroundColor = parseColor(resolveThemeValue(variables, backgroundToken))

	if ((foregroundColor.a ?? 1) < 1 || (backgroundColor.a ?? 1) < 1) {
		const fallbackBackground = parseColor(resolveThemeValue(variables, fallbackBackgroundToken))
		return contrastRatio(
			compositeColor(foregroundColor, fallbackBackground),
			compositeColor(backgroundColor, fallbackBackground),
		)
	}

	return contrastRatio(foregroundColor, backgroundColor)
}

describe('chat dark mode color contrast', () => {
	it('keeps primary and secondary dark-mode text above readable contrast thresholds', () => {
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-text-primary', '--app-surface-1')).toBeGreaterThanOrEqual(7)
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-text-secondary', '--app-surface-1')).toBeGreaterThanOrEqual(4.5)
	})

	it('keeps the shared input text and placeholder readable on the dark input surface', () => {
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-input-text', '--app-input-bg', '--app-surface-1')).toBeGreaterThanOrEqual(7)
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-input-placeholder', '--app-input-bg', '--app-surface-1')).toBeGreaterThanOrEqual(4.5)
	})

	it('keeps accent text used in the empty state and sidebar badges readable in dark mode', () => {
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-success-600', '--app-surface-1')).toBeGreaterThanOrEqual(4.5)
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-primary-600', '--app-surface-1')).toBeGreaterThanOrEqual(4.5)
	})

	it('keeps auth shell eyebrow and hero copy readable in dark mode', () => {
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-auth-eyebrow', '--app-shell-bg')).toBeGreaterThanOrEqual(4.5)
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-auth-hero-copy', '--el-color-primary')).toBeGreaterThanOrEqual(4.5)
	})

	it('keeps auth button enabled, hover, and disabled states visually distinct and readable in dark mode', () => {
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-button-primary-text', '--app-button-primary-bg')).toBeGreaterThanOrEqual(4.5)
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-button-primary-text', '--app-button-primary-hover-bg')).toBeGreaterThanOrEqual(4.5)
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-button-primary-disabled-text', '--app-button-primary-disabled-bg')).toBeGreaterThanOrEqual(3)
		expect(resolveThemeValue(DARK_THEME_VARIABLES, '--app-button-primary-bg')).not.toBe(resolveThemeValue(DARK_THEME_VARIABLES, '--app-button-primary-disabled-bg'))
		expect(resolveThemeValue(DARK_THEME_VARIABLES, '--app-button-primary-bg')).not.toBe(resolveThemeValue(DARK_THEME_VARIABLES, '--app-button-primary-hover-bg'))
	})

	it('keeps destructive alert text readable on its dark emergency surface', () => {
		expect(resolveContrastRatio(DARK_THEME_VARIABLES, '--app-alert-danger-text', '--app-alert-danger-bg', '--app-page-bg')).toBeGreaterThanOrEqual(4.5)
	})
})