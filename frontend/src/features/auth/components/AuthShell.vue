<script setup>
import ThemePreferenceControl from '../../../components/ThemePreferenceControl.vue'

defineProps({
	title: {
		type: String,
		required: true,
	},
	description: {
		type: String,
		required: true,
	},
	formEyebrow: {
		type: String,
		required: true,
	},
	formTitle: {
		type: String,
		required: true,
	},
	formDescription: {
		type: String,
		required: true,
	},
})
</script>

<template>
	<section class="auth-shell min-h-screen bg-(--app-shell-bg) lg:grid lg:grid-cols-2 lg:bg-(--app-shell-bg)">
		<div class="auth-shell__theme-toggle">
			<ThemePreferenceControl />
		</div>
		<div class="hidden lg:flex lg:min-h-screen lg:items-center lg:justify-center lg:bg-primary lg:px-14 xl:px-18">
			<div class="max-w-lg">
				<h1 class="m-0 font-serif text-[clamp(4rem,5.6vw,5.9rem)] leading-[0.9] tracking-[-0.03em] text-white">
					{{ title }}
				</h1>
				<p class="auth-shell__hero-copy mt-8 max-w-md text-[1.15rem] leading-8 font-normal xl:text-[1.3rem] xl:leading-9">
					{{ description }}
				</p>
			</div>
		</div>

		<div class="flex min-h-screen items-center justify-center bg-(--app-shell-bg) px-5 py-8 sm:px-8 lg:px-14 xl:px-18">
			<div class="w-full max-w-md p-6 sm:p-8">
				<p class="auth-shell__eyebrow m-0 text-[0.68rem] font-semibold uppercase tracking-[0.24em]">{{ formEyebrow }}</p>
				<h2 class="auth-shell__title mt-3 text-[clamp(1.95rem,4vw,2.7rem)] leading-tight font-semibold tracking-[-0.02em]">
					{{ formTitle }}
				</h2>
				<p class="auth-shell__description mt-3 text-[0.98rem] leading-7 sm:text-[1.02rem]">
					{{ formDescription }}
				</p>
				<div class="mt-8">
					<slot />
				</div>
			</div>
		</div>
	</section>
</template>

<style scoped>
.auth-shell {
	position: relative;
}

.auth-shell__theme-toggle {
	position: absolute;
	right: 1rem;
	top: 1rem;
	z-index: 2;
}

.auth-shell__eyebrow {
	color: var(--app-auth-eyebrow);
}

.auth-shell__title {
	color: var(--app-text-primary);
}

.auth-shell__description {
	color: var(--app-text-secondary);
}

.auth-shell__hero-copy {
	color: var(--app-auth-hero-copy);
}

@media (min-width: 640px) {
	.auth-shell__theme-toggle {
		right: 1.5rem;
		top: 1.5rem;
	}
}
</style>