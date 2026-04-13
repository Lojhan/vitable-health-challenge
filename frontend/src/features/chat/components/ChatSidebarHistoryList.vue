<script setup>
import { computed, ref, watch } from 'vue'
import { useVirtualizer } from '@tanstack/vue-virtual'

const props = defineProps({
	conversationSummaries: {
		type: Array,
		required: true,
	},
	activeConversationId: {
		type: String,
		default: null,
	},
	historyHasMore: {
		type: Boolean,
		default: false,
	},
	isLoadingHistory: {
		type: Boolean,
		default: false,
	},
	isLoadingMoreHistory: {
		type: Boolean,
		default: false,
	},
	formatConversationDate: {
		type: Function,
		required: true,
	},
})

const emit = defineEmits(['request-more', 'select-conversation'])

const scrollRoot = ref(null)
const LOADER_ROW_HEIGHT = 56
const SUMMARY_ROW_HEIGHT = 72

const totalRowCount = computed(() => (
	props.conversationSummaries.length + (props.historyHasMore ? 1 : 0)
))

const virtualizerOptions = computed(() => ({
	count: totalRowCount.value,
	getScrollElement: () => scrollRoot.value,
	estimateSize: (index) => (
		index >= props.conversationSummaries.length ? LOADER_ROW_HEIGHT : SUMMARY_ROW_HEIGHT
	),
	overcan: 8,
}))

const rowVirtualizer = useVirtualizer(virtualizerOptions)

const virtualRows = computed(() => rowVirtualizer.value?.getVirtualItems?.() ?? [])
const fallbackRows = computed(() => {
	const summaryRows = props.conversationSummaries.map((summary, index) => ({
		key: `fallback-${summary.id}`,
		index,
		size: SUMMARY_ROW_HEIGHT,
		start: index * SUMMARY_ROW_HEIGHT,
	}))

	if (!props.historyHasMore) {
		return summaryRows
	}

	return [
		...summaryRows,
		{
			key: 'fallback-loader',
			index: props.conversationSummaries.length,
			size: LOADER_ROW_HEIGHT,
			start: props.conversationSummaries.length * SUMMARY_ROW_HEIGHT,
		},
	]
})
const renderedRows = computed(() => (
	virtualRows.value.length > 0 ? virtualRows.value : fallbackRows.value
))
const totalVirtualSize = computed(() => {
	const virtualizedSize = rowVirtualizer.value?.getTotalSize?.() ?? 0
	if (virtualizedSize > 0) {
		return virtualizedSize
	}

	const lastFallbackRow = fallbackRows.value.at(-1)
	return lastFallbackRow ? lastFallbackRow.start + lastFallbackRow.size : 0
})

watch(
	virtualRows,
	(rows) => {
		const lastRow = rows.at(-1)
		if (!lastRow || props.isLoadingMoreHistory || !props.historyHasMore) {
			return
		}

		const requestThreshold = Math.max(0, props.conversationSummaries.length - 4)
		if (lastRow.index >= requestThreshold) {
			emit('request-more')
		}
	},
	{ deep: true },
)
</script>

<template>
	<nav class="flex-1 overflow-hidden px-2 py-2" aria-label="Past conversations">
		<div
			v-if="conversationSummaries.length === 0 && !isLoadingHistory"
			class="history-list__empty px-2 pt-3 text-sm"
		>
			Your past conversations will appear here.
		</div>

		<div
			ref="scrollRoot"
			class="h-full overflow-y-auto pr-1 vertical-scroll-strip"
			data-testid="chat-history-virtual-list"
		>
			<div
				:style="{
					height: `${totalVirtualSize}px`,
					position: 'relative',
				}"
			>
				<div
					v-for="virtualRow in renderedRows"
					:key="virtualRow.key"
					:style="{
						position: 'absolute',
						top: 0,
						left: 0,
						width: '100%',
						height: `${virtualRow.size}px`,
						transform: `translateY(${virtualRow.start}px)`,
					}"
				>
					<template v-if="virtualRow.index < conversationSummaries.length">
						<button
							type="button"
							class="history-list__button mb-1 w-full rounded-md border px-3 py-2 text-left transition"
							:class="[
								conversationSummaries[virtualRow.index].id === activeConversationId
									? 'history-list__button--active'
									: 'history-list__button--inactive',
							]"
							:aria-current="conversationSummaries[virtualRow.index].id === activeConversationId ? 'page' : undefined"
							:aria-label="`Open conversation: ${conversationSummaries[virtualRow.index].title}`"
							@click="emit('select-conversation', conversationSummaries[virtualRow.index].id)"
						>
							<div class="flex items-center justify-between gap-3">
								<p class="m-0 truncate text-sm font-medium">
									{{ conversationSummaries[virtualRow.index].title }}
								</p>
								<span
									v-if="conversationSummaries[virtualRow.index].isDraft"
									class="history-list__draft-badge rounded-full px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.12em]"
								>
									New
								</span>
							</div>
							<p class="history-list__meta m-0 mt-0.5 text-xs">
								{{ formatConversationDate(conversationSummaries[virtualRow.index].updatedAt) }}
							</p>
						</button>
					</template>

					<div
						v-else
						class="history-list__loader flex h-full items-center justify-center px-3 text-xs font-medium uppercase tracking-[0.16em]"
					>
						<span v-if="isLoadingMoreHistory || isLoadingHistory">Loading more</span>
						<span v-else>Scroll for more</span>
					</div>
				</div>
			</div>
		</div>
	</nav>
</template>

<style scoped>
.vertical-scroll-strip {
	-ms-overflow-style: none;
	scrollbar-width: none;
	-webkit-overflow-scrolling: touch;
}

.vertical-scroll-strip::-webkit-scrollbar {
	display: none;
}

.history-list__empty,
.history-list__meta,
.history-list__loader {
	color: var(--app-text-secondary);
}

.history-list__button--active {
	border-color: color-mix(in srgb, var(--app-primary-500) 45%, var(--app-border-subtle));
	background: color-mix(in srgb, var(--app-primary-500) 14%, var(--app-surface-1));
	color: var(--app-text-primary);
}

.history-list__button--inactive {
	border-color: transparent;
	background: transparent;
	color: var(--app-text-primary);
}

.history-list__button--inactive:hover {
	border-color: var(--app-border-subtle);
	background: var(--app-surface-2);
}

.history-list__draft-badge {
	background: color-mix(in srgb, var(--app-surface-1) 82%, transparent);
	color: var(--app-primary-600);
}
</style>