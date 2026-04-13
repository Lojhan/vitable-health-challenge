<script setup>
import { useThemeStore } from '../stores/theme'

const themeStore = useThemeStore()

const options = [
	{ label: 'System', value: 'system' },
	{ label: 'Light', value: 'light' },
	{ label: 'Dark', value: 'dark' },
]
</script>

<template>
	<div class="theme-control" role="group" aria-label="Color theme preference">
		<button
			v-for="option in options"
			:key="option.value"
			type="button"
			class="theme-control__option"
			:class="{
				'theme-control__option--active': themeStore.preference === option.value,
			}"
			:aria-pressed="themeStore.preference === option.value"
			@click="themeStore.setPreference(option.value)"
		>
			{{ option.label }}
		</button>
	</div>
</template>

<style scoped>
.theme-control {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	padding: 0.22rem;
	border: 1px solid var(--app-border-subtle);
	border-radius: 999px;
	background: var(--app-surface-0);
	box-shadow: var(--app-shadow-soft);
	backdrop-filter: blur(14px);
}

.theme-control__option {
	border: 0;
	border-radius: 999px;
	background: transparent;
	color: var(--app-text-secondary);
	cursor: pointer;
	font: inherit;
	font-size: 0.73rem;
	font-weight: 600;
	letter-spacing: 0.01em;
	padding: 0.22rem 0.52rem;
	transition: background-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.theme-control__option:hover {
	background: var(--app-surface-2);
	color: var(--app-text-primary);
}

.theme-control__option--active {
	background: var(--app-primary-600);
	color: var(--app-text-inverse);
}
</style>