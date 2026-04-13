<script setup>
import InputText from "primevue/inputtext";
import Button from "primevue/button";

defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  messageInputId: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["update:modelValue", "submit"]);

function updateValue(event) {
  emit("update:modelValue", event.target.value);
}
</script>

<template>
  <form
    class="chat-composer absolute bottom-0 z-20 px-3 py-3 sm:py-8 sm:px-4 w-full"
    aria-label="Send a message"
    @submit.prevent="emit('submit')"
  >
    <label :for="messageInputId" class="sr-only">
      Describe your symptoms
    </label>
    <div class="mx-auto w-full max-w-5xl">
      <div
        class="chat-composer__surface flex items-center gap-2 rounded-2xl border px-2 py-1"
      >
        <InputText
          :id="messageInputId"
          :model-value="modelValue"
          placeholder="Type your symptoms..."
          aria-label="Describe your symptoms and current condition"
          class="app-themed-input chat-composer__input w-full"
          @input="updateValue"
        />
        <Button
          type="submit"
          icon="pi pi-send"
          label="Send"
          aria-label="Send your message to the AI nurse"
          class="chat-composer__send shrink-0 rounded-xl!"
        />
      </div>
    </div>
  </form>
</template>

<style scoped>
.chat-composer {
  border: 0;
  background: linear-gradient(
    180deg,
    transparent 0%,
    color-mix(in srgb, var(--app-page-bg) 50%, transparent) 10%,
    var(--app-page-bg) 50%
  );
}

.chat-composer__surface {
  border-color: color-mix(in srgb, var(--app-border-subtle) 78%, transparent);
  background: var(--app-surface-0);

  box-shadow:
    0 14px 28px -22px rgba(15, 23, 42, 0.55),
    0 0 0 1px color-mix(in srgb, var(--app-surface-2) 75%, transparent) inset;
}

:deep(.chat-composer__input.p-inputtext),
:deep(.chat-composer__input) {
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0.9rem 1rem 0.9rem 1.15rem !important;
}

:deep(.chat-composer__input.p-inputtext:enabled:focus),
:deep(.chat-composer__input:enabled:focus) {
  box-shadow: none !important;
}

:deep(.chat-composer__send.p-button) {
  border-color: color-mix(
    in srgb,
    var(--app-primary-500) 24%,
    transparent
  ) !important;
  background: color-mix(
    in srgb,
    var(--app-primary-500) 12%,
    transparent
  ) !important;
  color: var(--app-primary-700) !important;
}

:deep(.chat-composer__send.p-button:not(:disabled):hover) {
  border-color: color-mix(
    in srgb,
    var(--app-primary-500) 36%,
    transparent
  ) !important;
  background: color-mix(
    in srgb,
    var(--app-primary-500) 18%,
    transparent
  ) !important;
  color: var(--app-primary-800) !important;
}
</style>
