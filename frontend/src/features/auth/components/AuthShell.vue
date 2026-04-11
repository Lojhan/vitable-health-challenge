<script setup>
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
	<section class="min-h-screen bg-(--app-shell-bg) lg:grid lg:grid-cols-2 lg:bg-(--app-shell-bg)">
		<div class="hidden lg:flex lg:min-h-screen lg:items-center lg:justify-center lg:bg-primary lg:px-14 xl:px-18">
			<div class="max-w-lg">
				<h1 class="m-0 font-serif text-[clamp(4rem,5.6vw,5.9rem)] leading-[0.9] tracking-[-0.03em] text-white">
					{{ title }}
				</h1>
				<p class="mt-8 max-w-md text-[1.15rem] leading-8 font-normal text-emerald-50/95 xl:text-[1.3rem] xl:leading-9">
					{{ description }}
				</p>
			</div>
		</div>

		<div class="flex min-h-screen items-center justify-center bg-(--app-shell-bg) px-5 py-8 sm:px-8 lg:px-14 xl:px-18">
			<div class="w-full max-w-md p-6 sm:p-8">
				<p class="m-0 text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-primary">{{ formEyebrow }}</p>
				<h2 class="mt-3 text-[clamp(1.95rem,4vw,2.7rem)] leading-tight font-semibold tracking-[-0.02em] text-slate-900">
					{{ formTitle }}
				</h2>
				<p class="mt-3 text-[0.98rem] leading-7 text-slate-500 sm:text-[1.02rem]">
					{{ formDescription }}
				</p>
				<div class="mt-8">
					<slot />
				</div>
			</div>
		</div>
	</section>
</template>