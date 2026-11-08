<template>
  <div class="control-panel">
    <h2>控制面板</h2>
    <p class="description">
      使用滑块控制 3D 立方体的位置、旋转和颜色。
    </p>

    <div class="control-group">
      <div class="control-label">
        <span>位置 X</span>
        <span class="control-value">{{ posX.toFixed(1) }}</span>
      </div>
      <input type="range" v-model.number="posX" min="-3" max="3" step="0.1" @input="updateTransform">
    </div>

    <div class="control-group">
      <div class="control-label">
        <span>位置 Y</span>
        <span class="control-value">{{ posY.toFixed(1) }}</span>
      </div>
      <input type="range" v-model.number="posY" min="-3" max="3" step="0.1" @input="updateTransform">
    </div>

    <div class="control-group">
      <div class="control-label">
        <span>位置 Z</span>
        <span class="control-value">{{ posZ.toFixed(1) }}</span>
      </div>
      <input type="range" v-model.number="posZ" min="0" max="3" step="0.1" @input="updateTransform">
    </div>

    <div class="control-group">
      <div class="control-label">
        <span>旋转 (Z轴)</span>
        <span class="control-value">{{ rotZ }}°</span>
      </div>
      <input type="range" v-model.number="rotZ" min="-180" max="180" step="5" @input="updateTransform">
    </div>

    <div class="control-group">
      <div class="control-label">
        <span>颜色</span>
      </div>
      <input type="color" v-model="colorHex" @input="updateColor">
    </div>

    <button @click="reset" class="reset-btn">重置</button>

    <div class="info" v-if="boxHandle">
      <div class="info-label">物体 Handle:</div>
      <div class="info-value">{{ boxHandle }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  boxHandle: string
}>()

const emit = defineEmits<{
  updateTransform: [pose: { pos: number[], quat: number[] }]
  updateColor: [rgba: number[]]
  reset: []
}>()

const posX = ref(0)
const posY = ref(0)
const posZ = ref(0.5)
const rotZ = ref(0)
const colorHex = ref('#ff6b6b')

function updateTransform() {
  const angle = rotZ.value * Math.PI / 180
  const quat = [0, 0, Math.sin(angle / 2), Math.cos(angle / 2)]

  emit('updateTransform', {
    pos: [posX.value, posY.value, posZ.value],
    quat: quat
  })
}

function updateColor() {
  const rgb = hexToRgb(colorHex.value)
  emit('updateColor', [...rgb, 1])
}

function hexToRgb(hex: string): number[] {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  return [r, g, b]
}

function reset() {
  posX.value = 0
  posY.value = 0
  posZ.value = 0.5
  rotZ.value = 0
  colorHex.value = '#ff6b6b'
  emit('reset')
}
</script>

<style scoped>
.control-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

h2 {
  font-size: 18px;
  margin: 0;
  color: #4cc9f0;
}

.description {
  font-size: 12px;
  color: #888;
  line-height: 1.5;
  margin: 0;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.control-label {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.control-value {
  color: #4cc9f0;
  font-family: monospace;
}

input[type="range"] {
  width: 100%;
  height: 6px;
  -webkit-appearance: none;
  background: #333;
  border-radius: 3px;
  outline: none;
}

input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: #4cc9f0;
  border-radius: 50%;
  cursor: pointer;
}

input[type="range"]::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: #4cc9f0;
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

input[type="color"] {
  width: 100%;
  height: 40px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background: transparent;
}

.reset-btn {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 4px;
  background: #4cc9f0;
  color: #000;
  font-size: 14px;
  cursor: pointer;
  font-weight: 500;
}

.reset-btn:hover {
  background: #7dd8f5;
}

.info {
  padding: 10px;
  background: #0d1b2a;
  border-radius: 4px;
  font-size: 12px;
}

.info-label {
  color: #888;
  margin-bottom: 4px;
}

.info-value {
  color: #4cc9f0;
  font-family: monospace;
  word-break: break-all;
}
</style>
