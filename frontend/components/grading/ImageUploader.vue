<template>
  <div class="image-uploader">
    <div class="upload-grid">
      <div
        v-for="(img, i) in images"
        :key="'img-' + i"
        class="uploaded-thumb"
      >
        <img :src="img.preview" alt="" class="thumb-img" />
        <button class="remove-btn" @click="$emit('remove', i)" title="删除">
          <X :size="14" />
        </button>
      </div>

      <div
        class="upload-zone"
        @click="triggerUpload"
        @dragover.prevent="dragover = true"
        @dragleave.prevent="dragover = false"
        @drop.prevent="handleDrop"
        :class="{ dragover }"
      >
        <Camera :size="40" />
        <p class="upload-text">{{ title }}</p>
        <p class="upload-hint">{{ hint }}</p>
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          multiple
          @change="handleFiles"
          class="file-input"
        />
      </div>
    </div>
    <p class="upload-count" v-if="images.length > 0">
      已上传 {{ images.length }} 张图片
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Camera, X } from 'lucide-vue-next'

const props = defineProps({
  title: { type: String, default: '点击上传图片' },
  hint: { type: String, default: '支持 JPG / PNG' },
  images: { type: Array, default: () => [] }
})

const emit = defineEmits(['add', 'remove'])

const fileInput = ref(null)
const dragover = ref(false)

function triggerUpload() {
  fileInput.value?.click()
}

function handleFiles(e) {
  const files = e.target.files || e.dataTransfer?.files
  if (!files) return
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue
    const preview = URL.createObjectURL(file)
    emit('add', { file, preview })
  }
  if (fileInput.value) fileInput.value.value = ''
}

function handleDrop(e) {
  dragover.value = false
  handleFiles(e)
}
</script>

<style scoped>
.image-uploader { width: 100%; }

.upload-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.uploaded-thumb {
  position: relative;
  aspect-ratio: 4/3;
  border-radius: var(--radius-base);
  overflow: hidden;
  background: var(--color-bg-main);
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: rgba(0,0,0,0.5);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-zone {
  aspect-ratio: 4/3;
  border: 2px dashed var(--color-text-secondary);
  border-radius: var(--radius-base);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--color-text-secondary);
  padding: 12px;
}

.upload-zone:hover,
.upload-zone.dragover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.upload-text { font-size: var(--font-sm); font-weight: 500; }
.upload-hint { font-size: var(--font-xs); }

.file-input { display: none; }
.upload-count { font-size: var(--font-xs); color: var(--color-text-secondary); margin-top: 8px; }
</style>
