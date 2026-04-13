import { computed, shallowRef, watch } from "vue";
import { defineStore } from "pinia";

const THEME_PREFERENCE_KEY = "vh_theme_preference";
const MEDIA_QUERY = "(prefers-color-scheme: dark)";

function readStoredPreference() {
  try {
    const storedPreference =
      globalThis.localStorage?.getItem(THEME_PREFERENCE_KEY);
    if (
      storedPreference === "light" ||
      storedPreference === "dark" ||
      storedPreference === "system"
    ) {
      return storedPreference;
    }
  } catch (_error) {
    return "system";
  }

  return "system";
}

function resolveSystemTheme() {
  if (typeof globalThis.matchMedia !== "function") {
    return "light";
  }

  return globalThis.matchMedia(MEDIA_QUERY).matches ? "dark" : "light";
}

function persistPreference(nextPreference) {
  try {
    globalThis.localStorage?.setItem(THEME_PREFERENCE_KEY, nextPreference);
  } catch (_error) {
    // Ignore storage failures and keep the in-memory preference.
  }
}

function applyTheme(nextTheme) {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  root.classList.toggle("dark", nextTheme === "dark");
  root.style.colorScheme = nextTheme;
}

export const useThemeStore = defineStore("theme", () => {
  const preference = shallowRef(readStoredPreference());
  const systemTheme = shallowRef(resolveSystemTheme());
  const resolvedTheme = computed(() =>
    preference.value === "system" ? systemTheme.value : preference.value,
  );
  let mediaQueryList = null;
  let teardownMediaQueryListener = null;

  function handleSystemThemeChange(event) {
    systemTheme.value = event.matches ? "dark" : "light";
  }

  function attachSystemThemeListener() {
    if (mediaQueryList || typeof globalThis.matchMedia !== "function") {
      return;
    }

    mediaQueryList = globalThis.matchMedia(MEDIA_QUERY);
    systemTheme.value = mediaQueryList.matches ? "dark" : "light";

    if (typeof mediaQueryList.addEventListener === "function") {
      mediaQueryList.addEventListener("change", handleSystemThemeChange);
      teardownMediaQueryListener = () => {
        mediaQueryList?.removeEventListener("change", handleSystemThemeChange);
      };
      return;
    }

    if (typeof mediaQueryList.addListener === "function") {
      mediaQueryList.addListener(handleSystemThemeChange);
      teardownMediaQueryListener = () => {
        mediaQueryList?.removeListener(handleSystemThemeChange);
      };
    }
  }

  function initializeTheme() {
    attachSystemThemeListener();
    applyTheme(resolvedTheme.value);
  }

  function dispose() {
    teardownMediaQueryListener?.();
    teardownMediaQueryListener = null;
    mediaQueryList = null;
  }

  function setPreference(nextPreference) {
    if (!["light", "dark", "system"].includes(nextPreference)) {
      return;
    }

    preference.value = nextPreference;
  }

  watch(preference, (nextPreference) => {
    persistPreference(nextPreference);
  });

  watch(
    resolvedTheme,
    (nextTheme) => {
      applyTheme(nextTheme);
    },
    { immediate: true },
  );

  return {
    preference,
    resolvedTheme,
    initializeTheme,
    setPreference,
    dispose,
  };
});
