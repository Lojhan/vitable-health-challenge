<script setup>
defineProps({
	activities: {
		type: Array,
		default: () => [],
	},
})
</script>

<template>
	<section
		v-if="activities.length > 0"
		class="rounded-xl border border-slate-200/90 bg-white/80 px-3.5 py-3 shadow-sm backdrop-blur"
		aria-label="Assistant activity"
	>
		<p class="m-0 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-slate-500">
			Assistant activity
		</p>
		<ol class="mt-2 grid gap-2">
			<li
				v-for="activity in activities"
				:key="activity.id"
				:class="[
					'flex items-start gap-2.5 rounded-md px-2.5 py-2 transition-colors duration-200',
					activity.state === 'completed'
						? 'bg-slate-50 text-slate-500'
						: 'bg-emerald-50/70 text-slate-700',
				]"
			>
				<span
					:class="[
						'activity-dot mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full',
						activity.state === 'completed' ? 'bg-slate-300' : 'bg-emerald-500',
					]"
					aria-hidden="true"
				/>
				<div class="min-w-0">
					<p class="m-0 text-sm font-medium leading-5">
						{{ activity.label }}
					</p>
					<p v-if="activity.phase" class="mt-0.5 text-xs uppercase tracking-[0.12em] text-slate-400">
						{{ activity.phase }}
					</p>
				</div>
			</li>
		</ol>
	</section>
</template>

<style scoped>
.activity-dot {
	box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.24);
	animation: activity-pulse 1.2s ease-in-out infinite;
}

@keyframes activity-pulse {
	0%,
	100% {
		box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.24);
	}
	50% {
		box-shadow: 0 0 0 6px rgba(16, 185, 129, 0);
	}
}
</style>