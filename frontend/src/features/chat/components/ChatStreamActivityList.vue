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
		class="stream-activity-panel rounded-xl border px-3.5 py-3 shadow-sm backdrop-blur"
		aria-label="Assistant activity"
	>
		<p class="stream-activity-panel__heading m-0 text-[0.72rem] font-semibold uppercase tracking-[0.16em]">
			Assistant activity
		</p>
		<ol class="mt-2 grid gap-2">
			<li
				v-for="activity in activities"
				:key="activity.id"
				:class="[
					'stream-activity-row flex items-start gap-2.5 rounded-md px-2.5 py-2 transition-colors duration-200',
					activity.state === 'completed'
						? 'stream-activity-row--completed'
						: 'stream-activity-row--active',
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
					<p class="stream-activity-row__label m-0 text-sm font-medium leading-5">
						{{ activity.label }}
					</p>
					<p v-if="activity.phase" class="stream-activity-row__phase mt-0.5 text-xs uppercase tracking-[0.12em]">
						{{ activity.phase }}
					</p>
				</div>
			</li>
		</ol>
	</section>
</template>

<style scoped>
.stream-activity-panel {
	border-color: var(--app-border-subtle);
	background: color-mix(in srgb, var(--app-surface-1) 86%, transparent);
}

.stream-activity-panel__heading,
.stream-activity-row__phase {
	color: var(--app-text-secondary);
}

.stream-activity-row--completed {
	background: var(--app-surface-2);
}

.stream-activity-row--active {
	background: color-mix(in srgb, var(--app-success-500) 12%, var(--app-surface-1));
}

.stream-activity-row__label {
	color: var(--app-text-primary);
}

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