<template>
  <div class="control-panel">
    <h2>Controls</h2>
    
    <div class="section">
      <h3>Joint Control</h3>
      <div class="slider-group" v-for="i in 6" :key="i">
        <label>J{{ i }}</label>
        <input 
          type="range" 
          :min="-180" 
          :max="180" 
          v-model.number="joints[i-1]"
          @input="onJointChange"
        />
        <span>{{ joints[i-1].toFixed(1) }}°</span>
      </div>
    </div>
    
    <div class="section">
      <h3>Actions</h3>
      <button @click="emit('command', { name: 'home', args: {} })">
        🏠 Home
      </button>
      <button @click="emit('command', { name: 'start_welding', args: {} })">
        ⚡ Start Welding
      </button>
      <button @click="emit('command', { name: 'stop', args: {} })">
        ⏹ Stop
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  jointPositions?: number[] // in degrees
}>()

const emit = defineEmits<{
  (e: 'command', cmd: { name: string; args: Record<string, any> }): void
}>()

const joints = ref([0, 0, 0, 0, 0, 0])

// Watch for external joint position updates (e.g., from backend)
watch(
  () => props.jointPositions,
  (newPositions) => {
    if (newPositions && newPositions.length === 6) {
      joints.value = [...newPositions]
    }
  },
  { immediate: true }
)

function onJointChange() {
  emit('command', {
    name: 'set_joints',
    args: { positions: joints.value.map(j => j * Math.PI / 180) }
  })
}
</script>

<style scoped>
.control-panel {
  padding: 16px;
}

.control-panel h2 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 500;
}

.section {
  margin-bottom: 24px;
}

.section h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 400;
  color: #888;
}

.slider-group {
  display: grid;
  grid-template-columns: 30px 1fr 50px;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.slider-group label {
  font-size: 12px;
  color: #888;
}

.slider-group input[type="range"] {
  width: 100%;
  accent-color: #e94560;
}

.slider-group span {
  font-size: 12px;
  text-align: right;
}

button {
  display: block;
  width: 100%;
  padding: 10px;
  margin-bottom: 8px;
  background: #0f3460;
  border: 1px solid #16213e;
  border-radius: 6px;
  color: #eee;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

button:hover {
  background: #1a4f8b;
}
</style>
