<template>
  <div class="app">
    <header class="header">
      <h1>FrameViz External App Template</h1>
      <div class="status">
        <span :class="['status-dot', isConnected ? 'connected' : 'disconnected']"></span>
        FrameViz {{ isConnected ? 'Connected' : 'Disconnected' }}
      </div>
    </header>

    <main class="main">
      <aside class="sidebar">
        <ControlPanel
          :box-handle="boxHandle"
          @update-transform="handleUpdateTransform"
          @update-color="handleUpdateColor"
          @reset="handleReset"
        />
      </aside>

      <section class="viewer-container">
        <FrameVizViewer
          name="main_viewer"
          :view-id="viewId"
          @error="onViewerError"
          @registered="onViewerRegistered"
        />
      </section>
    </main>

    <footer class="footer">
      <span>Data flow: UI to Backend to FrameViz</span>
      <span v-if="viewerInfo.viewId">View: {{ viewerInfo.viewId }}</span>
      <span v-if="viewerInfo.sceneId">Scene: {{ viewerInfo.sceneId }}</span>
      <span :class="backendConnected ? 'status-online' : 'status-offline'">
        Backend: {{ backendConnected ? 'Connected' : 'Disconnected' }}
      </span>
      <span v-if="boxHandle">Box: {{ boxHandle }}</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { FrameVizViewer, useFrameViz } from '@frameviz/vue'
import ControlPanel from './components/ControlPanel.vue'

const VIEWER_NAME = 'main_viewer'
const DEFAULT_BACKEND_WS_URL = 'ws://127.0.0.1:9621'
const BACKEND_RECONNECT_DELAY_MS = 2000

const viewId = ref<string | undefined>(resolveViewId(VIEWER_NAME))
const { isConnected } = useFrameViz({ scope: viewId.value || VIEWER_NAME })

const viewerInfo = ref<{ viewerName: string; viewId: string; sceneId: string }>({
  viewerName: '',
  viewId: '',
  sceneId: ''
})
const boxHandle = ref<string>('')
const backendConnected = ref(false)
let backendSocket: WebSocket | null = null
let shouldReconnect = true

const BACKEND_WS_URL = import.meta.env.VITE_BACKEND_WS_URL || DEFAULT_BACKEND_WS_URL

type StateUpdate = {
  type: 'state_update'
  box_handle?: string
}

type BackendError = {
  type: 'error'
  message?: string
}

function resolveViewId(viewerName: string): string | undefined {
  if (typeof window === 'undefined') return undefined
  const injectedViewId = (window as any).__FRAMEVIZ_VIEW_ID__
  const params = new URLSearchParams(window.location.search)
  const paramViewId = params.get('view_id')
  const explicitViewId =
    typeof injectedViewId === 'string' && injectedViewId.length > 0
      ? injectedViewId
      : (paramViewId && paramViewId.length > 0 ? paramViewId : undefined)
  const storageKey = `frameviz_view_id:${viewerName}`
  try {
    const storage = getStorage()
    const existing = storage?.getItem(storageKey)
    if (existing) return existing
    const generated = explicitViewId ? explicitViewId : `v_${Math.random().toString(36).slice(2, 10)}`
    storage?.setItem(storageKey, generated)
    return generated
  } catch {
    return explicitViewId
  }
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

function connectBackend() {
  if (backendSocket && backendSocket.readyState === WebSocket.OPEN) return

  const businessToken = new URLSearchParams(window.location.hash.slice(1)).get('business_token')
  if (!businessToken) { console.error('[App] business_token is required in the URL fragment'); return }
  backendSocket = new WebSocket(BACKEND_WS_URL, ['frameviz-business', `token.${businessToken}`])

  backendSocket.onopen = () => {
    backendConnected.value = true
    sendViewerBinding()
  }

  backendSocket.onclose = () => {
    backendConnected.value = false
    backendSocket = null
    if (shouldReconnect) {
      setTimeout(connectBackend, BACKEND_RECONNECT_DELAY_MS)
    }
  }

  backendSocket.onerror = () => {
    backendSocket?.close()
  }

  backendSocket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as StateUpdate | BackendError
      if (msg.type === 'state_update') {
        boxHandle.value = msg.box_handle || ''
      } else if (msg.type === 'error') {
        console.error('[App] Backend error:', msg.message || 'unknown error')
      }
    } catch (err) {
      console.error('[App] Failed to parse backend message:', err)
    }
  }
}

function sendBackendCommand(name: string, args: Record<string, unknown> = {}) {
  if (!backendSocket || backendSocket.readyState !== WebSocket.OPEN) return
  backendSocket.send(JSON.stringify({ name, args }))
}

function sendViewerBinding() {
  if (!viewerInfo.value.viewerName || !viewerInfo.value.viewId || !viewerInfo.value.sceneId) return
  sendBackendCommand('bind_viewer', {
    viewer_name: viewerInfo.value.viewerName,
    view_id: viewerInfo.value.viewId,
    scene_id: viewerInfo.value.sceneId,
  })
}

function onViewerError(error: Error) {
  console.error('Viewer error:', error)
}

function onViewerRegistered(info: { viewerName: string; viewId: string; sceneId: string }) {
  viewerInfo.value = info
  sendViewerBinding()
}

function handleUpdateTransform(pose: { pos: number[]; quat: number[] }) {
  sendBackendCommand('set_box_pose', { pos: pose.pos, quat: pose.quat })
}

function handleUpdateColor(rgba: number[]) {
  sendBackendCommand('set_box_color', { rgba })
}

function handleReset() {
  sendBackendCommand('reset_box')
}

onMounted(() => {
  connectBackend()
})

onUnmounted(() => {
  shouldReconnect = false
  backendSocket?.close()
})
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #1a1a2e;
  color: #eee;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #16213e;
  border-bottom: 1px solid #0f3460;
}

.header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}

.status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot.connected {
  background: #4ade80;
}

.status-dot.disconnected {
  background: #f87171;
}

.main {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.sidebar {
  width: 300px;
  background: #16213e;
  border-right: 1px solid #0f3460;
  overflow-y: auto;
  padding: 20px;
}

.viewer-container {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.viewer-container :deep(.frameviz-viewer) {
  flex: 1;
  min-height: 0;
}

.footer {
  display: flex;
  justify-content: space-between;
  padding: 8px 24px;
  background: #16213e;
  border-top: 1px solid #0f3460;
  font-size: 12px;
  color: #888;
  gap: 12px;
}

.status-online {
  color: #4ade80;
}

.status-offline {
  color: #f87171;
}
</style>
