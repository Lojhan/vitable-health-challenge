<script setup>
const emit = defineEmits(["quick-reply"]);

const suggestedPrompts = [
  "I have a sore throat and fever. What should I do?",
  "Help me understand whether these symptoms are urgent.",
  "Find me the right kind of doctor for recurring migraines.",
];
</script>

<template>
  <section
    class="empty-state-panel mx-auto grid w-full max-w-4xl gap-4 rounded-3xl border p-5 sm:p-7"
  >
    <div
      class="grid gap-3 sm:items-start"
    >
      <div class="space-y-3">
        <p
          class="empty-state__eyebrow m-0 text-xs font-semibold uppercase tracking-[0.18em]"
        >
          New conversation
        </p>
        <div class="space-y-2 grid gap-2">
          <h3 class="empty-state__title m-0 text-2xl font-semibold tracking-tight">
            Start with your symptoms, concern, or goal.
          </h3>
          <p class="empty-state__copy m-0 max-w-2xl text-sm leading-6">
            Describe what you are feeling, how long it has been happening, and
            anything that seems to make it better or worse. The assistant can
            help triage, suggest next steps, and guide you toward appointments
            when needed.
          </p>
        </div>
      </div>
    </div>

    <div class="grid gap-2.5">
      <p
        class="empty-state__label m-0 text-xs font-semibold uppercase tracking-[0.16em]"
      >
        Suggested prompts
      </p>
      <div class="grid gap-2 md:grid-cols-3">
        <button
          v-for="prompt in suggestedPrompts"
          :key="prompt"
          type="button"
          class="empty-state-prompt rounded-2xl border px-4 py-3 text-left text-sm leading-5 transition hover:-translate-y-0.5"
          @click="emit('quick-reply', prompt)"
        >
          {{ prompt }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.empty-state-panel {
  border-color: var(--app-border-subtle);
  background: color-mix(in srgb, var(--app-surface-1) 92%, transparent);
  box-shadow: 0 24px 70px -42px rgba(15, 23, 42, 0.45);
}

.empty-state__eyebrow {
  color: var(--app-success-600);
}

.empty-state__title {
  color: var(--app-text-primary);
}

.empty-state__copy,
.empty-state__label {
  color: var(--app-text-secondary);
}

.empty-state-prompt {
  border-color: var(--app-border-subtle);
  background: var(--app-surface-2);
  color: var(--app-text-secondary);
}

.empty-state-prompt:hover {
  border-color: color-mix(in srgb, var(--app-success-500) 56%, var(--app-border-subtle));
  background: color-mix(in srgb, var(--app-success-500) 12%, var(--app-surface-2));
  color: var(--app-text-primary);
}
</style>
