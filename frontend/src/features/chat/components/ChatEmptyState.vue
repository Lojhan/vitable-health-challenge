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
    class="mx-auto grid w-full max-w-4xl gap-4 rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-[0_24px_70px_-42px_rgba(15,23,42,0.45)] sm:p-7"
  >
    <div
      class="grid gap-3 sm:items-start"
    >
      <div class="space-y-3">
        <p
          class="m-0 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600"
        >
          New conversation
        </p>
        <div class="space-y-2 grid gap-2">
          <h3 class="m-0 text-2xl font-semibold tracking-tight text-slate-900">
            Start with your symptoms, concern, or goal.
          </h3>
          <p class="m-0 max-w-2xl text-sm leading-6 text-slate-600">
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
        class="m-0 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
      >
        Suggested prompts
      </p>
      <div class="grid gap-2 md:grid-cols-3">
        <button
          v-for="prompt in suggestedPrompts"
          :key="prompt"
          type="button"
          class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm leading-5 text-slate-700 transition hover:-translate-y-0.5 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-950"
          @click="emit('quick-reply', prompt)"
        >
          {{ prompt }}
        </button>
      </div>
    </div>
  </section>
</template>
