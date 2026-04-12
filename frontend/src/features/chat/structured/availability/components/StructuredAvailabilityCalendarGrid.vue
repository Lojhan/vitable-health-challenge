<script setup>
const props = defineProps({
	weekDayHeaders: {
		type: Array,
		required: true,
	},
	weekRows: {
		type: Array,
		required: true,
	},
	selectedDayIso: {
		type: String,
		default: '',
	},
	showDateSelection: {
		type: Boolean,
		required: true,
	},
	isLocked: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(['select-day'])

function dayCircleClasses(day) {
	if (!day) {
		return ''
	}

	if (props.selectedDayIso === day.iso_day) {
		return 'bg-emerald-700 text-white ring-2 ring-emerald-200'
	}

	if (day.is_available) {
		return 'bg-slate-100 text-slate-700 hover:bg-slate-200'
	}

	return 'bg-transparent text-slate-300'
}
</script>

<template>
	<div v-if="props.showDateSelection" class="grid grid-cols-7 text-center text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-slate-500">
		<span v-for="weekday in props.weekDayHeaders" :key="weekday">{{ weekday }}</span>
	</div>

	<div v-if="props.showDateSelection" class="grid gap-1">
		<div
			v-for="(week, weekIndex) in props.weekRows"
			:key="`week-${weekIndex}`"
			class="grid grid-cols-7"
		>
			<template v-for="(day, dayIndex) in week" :key="day?.iso_day ?? `empty-${weekIndex}-${dayIndex}`">
				<div v-if="!day" class="h-11" />
				<button
					v-else
					type="button"
					class="mx-auto grid h-11 w-11 cursor-pointer place-items-center rounded-full text-sm font-medium transition disabled:cursor-default"
					:class="dayCircleClasses(day)"
					:disabled="props.isLocked || !day.is_available"
					@click="emit('select-day', day.iso_day)"
				>
					{{ day.display_day }}
				</button>
			</template>
		</div>
	</div>
</template>
