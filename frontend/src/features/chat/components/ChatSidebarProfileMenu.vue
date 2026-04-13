<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import ThemePreferenceControl from "../../../components/ThemePreferenceControl.vue";

const props = defineProps({
  profileLabel: {
    type: String,
    default: "Profile",
  },
  profileCaption: {
    type: String,
    default: "Theme and session settings",
  },
});

const emit = defineEmits(["logout"]);

const menuOpen = ref(false);
const menuRoot = ref(null);

const profileInitials = computed(() => {
  const initials = props.profileLabel
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]?.toUpperCase() ?? "")
    .join("");

  return initials || "P";
});

function toggleMenu() {
  menuOpen.value = !menuOpen.value;
}

function closeMenu() {
  menuOpen.value = false;
}

function handleLogout() {
  closeMenu();
  emit("logout");
}

function onGlobalPointerDown(event) {
  if (!menuOpen.value) {
    return;
  }

  if (!menuRoot.value?.contains(event.target)) {
    closeMenu();
  }
}

function onGlobalKeyDown(event) {
  if (event.key === "Escape") {
    closeMenu();
  }
}

onMounted(() => {
  window.addEventListener("pointerdown", onGlobalPointerDown);
  window.addEventListener("keydown", onGlobalKeyDown);
});

onBeforeUnmount(() => {
  window.removeEventListener("pointerdown", onGlobalPointerDown);
  window.removeEventListener("keydown", onGlobalKeyDown);
});
</script>

<template>
  <div ref="menuRoot" class="sidebar-profile relative border-t">
    <transition name="profile-pop">
      <div
        v-if="menuOpen"
        data-testid="sidebar-profile-menu"
        class="sidebar-profile__panel absolute right-3 bottom-[calc(100%+0.65rem)] left-3 z-20 rounded-2xl border p-3"
        role="dialog"
        aria-label="Profile and settings"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <p
              class="sidebar-profile__eyebrow m-0 text-[0.68rem] font-semibold uppercase tracking-[0.18em]"
            >
              Appearance
            </p>
            <h3 class="sidebar-profile__title m-0 mt-1 text-sm font-semibold">
              Theme preference
            </h3>
            <p class="sidebar-profile__copy m-0 mt-1 text-xs leading-5">
              Switch between system, light, and dark mode.
            </p>
          </div>
          <button
            type="button"
            class="sidebar-profile__dismiss inline-flex h-8 w-8 items-center justify-center rounded-full border-0 bg-transparent cursor-pointer"
            aria-label="Close profile settings"
            @click="closeMenu"
          >
            <span class="pi pi-times text-sm" aria-hidden="true" />
          </button>
        </div>

        <div class="mt-3">
          <ThemePreferenceControl />
        </div>

        <button
          type="button"
          class="sidebar-profile__logout mt-4 flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm font-medium cursor-pointer"
          @click="handleLogout"
        >
          <span>Logout</span>
          <span class="pi pi-sign-out text-sm" aria-hidden="true" />
        </button>
      </div>
    </transition>

    <button
      type="button"
      data-testid="sidebar-profile-trigger"
      class="sidebar-profile__trigger flex w-full items-center gap-3 text-left cursor-pointer px-3 py-4 h-16"
      :aria-expanded="menuOpen"
      aria-haspopup="dialog"
      @click="toggleMenu"
    >
      <span
        class="sidebar-profile__avatar flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold"
      >
        {{ profileInitials }}
      </span>
      <span class="min-w-0 flex-1">
        <span
          class="sidebar-profile__label block truncate text-sm font-semibold"
          >{{ profileLabel }}</span
        >
        <span class="sidebar-profile__caption mt-0.5 block truncate text-xs">{{
          profileCaption
        }}</span>
      </span>
      <span
        class="pi text-sm"
        :class="menuOpen ? 'pi-chevron-down' : 'pi-chevron-up'"
        aria-hidden="true"
      />
    </button>
  </div>
</template>

<style scoped>
.sidebar-profile {
  border-color: var(--app-border-subtle);
}

.sidebar-profile__panel,
.sidebar-profile__trigger,
.sidebar-profile__logout {
  border-color: var(--app-border-subtle);
  background: var(--app-surface-0);
  box-shadow: var(--app-shadow-soft);
}

.sidebar-profile__avatar {
  background:
    radial-gradient(
      circle at top,
      color-mix(in srgb, var(--app-primary-500) 28%, transparent),
      transparent 68%
    ),
    color-mix(in srgb, var(--app-primary-500) 12%, var(--app-surface-2));
  color: var(--app-primary-700);
  flex-shrink: 0;
}

.sidebar-profile__eyebrow,
.sidebar-profile__caption,
.sidebar-profile__copy {
  color: var(--app-text-secondary);
}

.sidebar-profile__title,
.sidebar-profile__label {
  color: var(--app-text-primary);
}

.sidebar-profile__trigger,
.sidebar-profile__dismiss,
.sidebar-profile__logout {
  transition:
    background-color 160ms ease,
    color 160ms ease,
    border-color 160ms ease,
    transform 160ms ease;
}

.sidebar-profile__trigger:hover,
.sidebar-profile__dismiss:hover,
.sidebar-profile__logout:hover {
  background: var(--app-surface-2);
}

.sidebar-profile__dismiss {
  color: var(--app-text-secondary);
}

.sidebar-profile__logout {
  color: var(--app-text-primary);
}

.profile-pop-enter-active,
.profile-pop-leave-active {
  transition:
    opacity 160ms ease,
    transform 160ms ease;
}

.profile-pop-enter-from,
.profile-pop-leave-to {
  opacity: 0;
  transform: translateY(0.35rem);
}
</style>
