import { nextTick, onMounted, ref, watch } from 'vue'

const AUTO_FOLLOW_THRESHOLD_PX = 96

export function isNearFeedBottom(element, threshold = AUTO_FOLLOW_THRESHOLD_PX) {
	if (!element) {
		return true
	}

	const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight
	return distanceFromBottom <= threshold
}

export function useChatFeedAutoFollow({ feedRoot, feedVersion }) {
	const autoFollowEnabled = ref(true)

	async function scrollToBottom({ force = false } = {}) {
		const element = feedRoot.value
		if (!element) {
			return
		}

		if (!force && !autoFollowEnabled.value) {
			return
		}

		await nextTick()

		if (typeof element.scrollTo === 'function') {
			element.scrollTo({
				top: element.scrollHeight,
				behavior: 'auto',
			})
			return
		}

		element.scrollTop = element.scrollHeight
	}

	function handleFeedScroll() {
		autoFollowEnabled.value = isNearFeedBottom(feedRoot.value)
	}

	watch(
		feedVersion,
		async () => {
			await scrollToBottom()
		},
		{ flush: 'post' },
	)

	onMounted(() => {
		void scrollToBottom({ force: true })
	})

	return {
		autoFollowEnabled,
		handleFeedScroll,
		scrollToBottom,
	}
}