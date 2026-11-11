<template>
  <div ref="containerRef" class="frameviz-viewer">
    <!-- SceneManager will append its own canvas here -->
    <div v-if="connectionStatus === 'connecting'" class="frameviz-overlay">
      <div class="frameviz-overlay__card">
        <div class="frameviz-spinner" />
        <p>Connecting to FrameViz host...</p>
      </div>
    </div>
    <div v-else-if="connectionStatus === 'error'" class="frameviz-overlay">
      <div class="frameviz-overlay__card">
        <p>Failed to connect to FrameViz host.</p>
        <button type="button" class="frameviz-button" @click="() => connect()">
          Retry
        </button>
        <details v-if="connectionError?.message" class="frameviz-error-details">
          <summary>Details</summary>
          <pre>{{ connectionError.message }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useResizeObserver } from '@vueuse/core'
import { FrameVizCore } from '@frameviz/core'
import { useFrameVizConnection } from '../composables/useFrameVizConnection'
import type { FrameVizViewerProps, ViewerInfo } from '../types'

const props = withDefaults(defineProps<FrameVizViewerProps>(), {
  background: 0x1a1a2e,
  showGrid: true,
  showAxes: true,
  enableKeyboardShortcuts: true,
  autoStartHost: true,
})

const emit = defineEmits<{
  (e: 'ready', core: FrameVizCore): void
  (e: 'error', error: Error): void
  (e: 'registered', info: ViewerInfo): void
}>()

const containerRef = ref<HTMLDivElement>()
const coreRef = shallowRef<FrameVizCore>()
const isRegistered = ref(false)
const connectionScope = props.viewId || props.name
const { connect, disconnect, sendCommand, registerViewer, sendEvent, isConnected, connectionStatus, error: connectionError } = useFrameVizConnection({
  scope: connectionScope,
  viewId: props.viewId,
  authToken: props.authToken,
  autoStartHost: props.autoStartHost,
  onError: (err) => {
    console.warn('[FrameViz] Connection error:', err)
    emit('error', err)
  },
})
let unmounted = false
let keyboardFocusCleanup: (() => void) | null = null
let cameraPoseCleanup: (() => void) | null = null
let lastBufferSize: { width: number; height: number } | null = null
const CAMERA_PERSIST_INTERVAL_MS = 1000

watch(() => props.showWidgetPanel, enabled => {
  coreRef.value?.setWidgetPanelEnabled(enabled === true)
})

onMounted(async () => {
  if (!containerRef.value) return
  
  try {
    // Create FrameVizCore instance - let it manage the canvas
    const core = new FrameVizCore({
      container: containerRef.value,
      keyboardShortcuts: props.enableKeyboardShortcuts,
      showWidgetPanel: props.showWidgetPanel,
      background: props.background,
      onEvent: (name, data) => sendEvent(name, data),
      onCommand: (name, data) => { sendCommand(name, data).catch(err => emit('error', err)) },
      // We don't pass canvas anymore, let SceneManager create it
    })
    
    coreRef.value = core
    // Explicitly set initial size after a tick to ensure DOM is ready
    await nextTick()
    if (unmounted) { core.dispose(); return }
    core.resize()

    // Start animation loop immediately so the viewer renders without a host.
    startAnimation()
    restoreCameraPose(core)
    cameraPoseCleanup = bindCameraPosePersistence(core)
    emit('ready', core)

    if (props.enableKeyboardShortcuts) {
      core.setKeyboardShortcutsEnabled(false)
      keyboardFocusCleanup = enableKeyboardOnHover(containerRef.value, core)
    }

    // Connect to Host if not already connected, but do not block rendering.
    if (!isConnected.value) {
      connect().catch((err) => {
        console.warn('[FrameViz] Host connection failed:', err)
      })
    }

    // Attempt initial registration if already connected.
    await tryRegister()
  } catch (err) {
    console.error('[FrameViz] Viewer initialization failed:', err)
    emit('error', err as Error)
  }
})

let animationFrameId: number | null = null
function startAnimation() {
  const animate = () => {
    if (coreRef.value) {
      coreRef.value.render()
      animationFrameId = requestAnimationFrame(animate)
    }
  }
  animate()
}

async function tryRegister() {
  if (isRegistered.value || !coreRef.value || !isConnected.value) return
  try {
    const info = await registerViewer(props.name, coreRef.value, props.sceneId)
    if (unmounted || !coreRef.value) return
    coreRef.value.setViewId(info.viewId)
    isRegistered.value = true
    emit('registered', info)
    restoreCameraPose(coreRef.value)
    coreRef.value.resize()
  } catch (err) {
    console.warn('[FrameViz] Viewer registration failed:', err)
    emit('error', err as Error)
  }
}

watch(isConnected, (connected) => {
  if (!connected) {
    isRegistered.value = false
    return
  }
  coreRef.value?.resize()
  void tryRegister()
})

// Handle resize — pass observed dimensions directly for accuracy
useResizeObserver(containerRef, (entries) => {
  if (coreRef.value && entries.length > 0) {
    const { width, height } = entries[0].contentRect
    if (width > 0 && height > 0) {
      coreRef.value.resize(width, height)
      lastBufferSize = { width: Math.round(width), height: Math.round(height) }
    }
  }
})

// Cleanup on unmount
onUnmounted(() => {
  unmounted = true
  disconnect()
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }
  if (keyboardFocusCleanup) {
    keyboardFocusCleanup()
    keyboardFocusCleanup = null
  }
  if (cameraPoseCleanup) {
    cameraPoseCleanup()
    cameraPoseCleanup = null
  }
  coreRef.value?.dispose()
  coreRef.value = undefined
})

function enableKeyboardOnHover(container: HTMLDivElement, core: FrameVizCore) {
  const onEnter = () => core.setKeyboardShortcutsEnabled(true)
  const onLeave = () => core.setKeyboardShortcutsEnabled(false)
  container.addEventListener('mouseenter', onEnter)
  container.addEventListener('mouseleave', onLeave)
  return () => {
    container.removeEventListener('mouseenter', onEnter)
    container.removeEventListener('mouseleave', onLeave)
  }
}

function getCameraStorageKeys(): string[] {
  const keys: string[] = []
  if (props.viewId) {
    keys.push(`frameviz_camera_pose:${props.viewId}`)
  }
  keys.push(`frameviz_camera_pose:${props.name}`)
  return keys
}

function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    try {
      return window.localStorage
    } catch {
      return null
    }
  }
}

function restoreCameraPose(core: FrameVizCore) {
  if (typeof window === 'undefined') return
  try {
    const storage = getStorage()
    if (!storage) return
    for (const key of getCameraStorageKeys()) {
      const raw = storage.getItem(key)
      if (!raw) continue
      const data = JSON.parse(raw)
      if (!data || !Array.isArray(data.eye) || !Array.isArray(data.target) || !Array.isArray(data.up)) {
        continue
      }
      core.handleCommand('set_camera_pose', {
        eye: data.eye,
        target: data.target,
        up: data.up,
      }, {})
      return
    }
  } catch (err) {
    console.warn('[FrameViz] Failed to restore camera pose:', err)
  }
}

function bindCameraPosePersistence(core: FrameVizCore) {
  if (typeof window === 'undefined') return null
  const storage = getStorage()
  if (!storage) return null
  let lastSaved = ''
  let intervalId: number | null = null
  const savePose = () => {
    if (typeof (core as any).getCameraPose !== 'function') {
      return
    }
    const pose = core.getCameraPose()
    if (!pose) return
    try {
      const serialized = JSON.stringify(pose)
      if (serialized !== lastSaved) {
        for (const key of getCameraStorageKeys()) {
          storage.setItem(key, serialized)
        }
        lastSaved = serialized
      }
    } catch (err) {
      console.warn('[FrameViz] Failed to persist camera pose:', err)
    }
  }
  intervalId = window.setInterval(savePose, CAMERA_PERSIST_INTERVAL_MS)
  window.addEventListener('pagehide', savePose)
  window.addEventListener('beforeunload', savePose)
  return () => {
    window.removeEventListener('pagehide', savePose)
    window.removeEventListener('beforeunload', savePose)
    if (intervalId !== null) {
      window.clearInterval(intervalId)
      intervalId = null
    }
    savePose()
  }
}
</script>

<style scoped>
.frameviz-viewer {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
  background: #1a1a2e; /* Match default background */
}

.frameviz-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 12, 18, 0.6);
  color: #f0f4ff;
  z-index: 2;
}

.frameviz-overlay__card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  padding: 16px 20px;
  background: rgba(20, 24, 36, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.frameviz-spinner {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.2);
  border-top-color: #7dd3fc;
  animation: frameviz-spin 1s linear infinite;
}

.frameviz-button {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: #1e2a44;
  color: #f0f4ff;
  cursor: pointer;
}

.frameviz-button:hover {
  background: #27365a;
}

.frameviz-error-details {
  max-width: 320px;
  font-size: 12px;
  color: #cbd5f5;
}

.frameviz-error-details pre {
  white-space: pre-wrap;
}

@keyframes frameviz-spin {
  to {
    transform: rotate(360deg);
  }
}

/* Canvas styles are set inline by SceneManager for reliability
   (Vue scoped :deep() doesn't always apply to dynamically-created elements) */
</style>
