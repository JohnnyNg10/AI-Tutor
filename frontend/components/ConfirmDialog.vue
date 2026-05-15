<template>
  <Teleport to="body">
    <div class="dialog-overlay" @click.self="$emit('cancel')">
      <div class="dialog-card">
        <div class="dialog-icon">
          <AlertTriangle :size="28" color="var(--color-error)" />
        </div>
        <h3 class="dialog-title">{{ title }}</h3>
        <p class="dialog-message">{{ message }}</p>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="$emit('cancel')">取消</button>
          <button class="btn btn-danger-fill" @click="$emit('confirm')">{{ confirmText }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { AlertTriangle } from 'lucide-vue-next'

defineProps({
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确认' }
})

defineEmits(['confirm', 'cancel'])
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-card {
  background: var(--color-bg-white);
  border-radius: var(--radius-card);
  padding: 32px;
  max-width: 400px;
  width: 90%;
  text-align: center;
  box-shadow: var(--shadow-dropdown);
}

.dialog-icon { margin-bottom: 12px; }

.dialog-title {
  font-size: var(--font-lg);
  font-weight: 600;
  color: var(--color-text-title);
  margin-bottom: 8px;
}

.dialog-message {
  font-size: var(--font-base);
  color: var(--color-text-secondary);
  margin-bottom: 24px;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.btn-danger-fill {
  background: var(--color-error);
  color: #fff;
  border: none;
  border-radius: var(--radius-base);
  padding: 10px 20px;
  cursor: pointer;
  font-size: var(--font-base);
  font-family: var(--font-family);
  transition: all 0.2s;
}
.btn-danger-fill:hover {
  opacity: 0.9;
}
</style>
