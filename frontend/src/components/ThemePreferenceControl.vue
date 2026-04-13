<script setup>
import { useThemeStore } from '../stores/theme'

const themeStore = useThemeStore()

const options = [
	{ label: 'System', value: 'system', icon: 'pi pi-desktop' },
	{ label: 'Light', value: 'light', icon: 'pi pi-sun' },
	{ label: 'Dark', value: 'dark', icon: 'pi pi-moon' },
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
			:title="option.label"
			:aria-label="`Use ${option.label.toLowerCase()} theme`"
			:aria-pressed="themeStore.preference === option.value"
			@click="themeStore.setPreference(option.value)"
		>
			<span :class="option.icon" aria-hidden="true" />
			<span class="theme-control__sr-only">{{ option.label }}</span>
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
	display: inline-flex;
	align-items: center;
	justify-content: center;
	height: 2rem;
	width: 2rem;
	border: 0;
	border-radius: 999px;
	background: transparent;
	color: var(--app-text-secondary);
	cursor: pointer;
	font: inherit;
	font-size: 0.9rem;
	padding: 0;
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

.theme-control__sr-only {
	position: absolute;
	width: 1px;
	height: 1px;
	padding: 0;
	margin: -1px;
	overflow: hidden;
	clip: rect(0, 0, 0, 0);
	white-space: nowrap;
	border: 0;
}
</style>