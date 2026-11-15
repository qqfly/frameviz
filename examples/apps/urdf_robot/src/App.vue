<template>
  <div class="app">
    <header class="header">
      <h1>🤖 URDF Robot Viewer</h1>
      <div class="status">
        <span :class="['status-dot', isConnected ? 'connected' : 'disconnected']"></span>
        {{ isConnected ? 'Connected' : 'Disconnected' }}
      </div>
    </header>
    
    <main class="main">
      <aside class="sidebar">
        <ControlPanel 
          :joint-positions="jointPositions"
          @command="handleCommand" 
        />
      </aside>
      
      <section class="viewer-container">
        <div class="viewer-stack">
          <div class="viewer-panel">
            <div class="viewer-title">Visual</div>
            <FrameVizViewer 
              name="main_viewer"
              :view-id="mainViewId"
              @ready="onMainViewerReady"
              @error="onViewerError"
              @registered="onViewerRegistered"
            />
          </div>
          <div class="viewer-panel">
            <div class="viewer-title">Collision</div>
            <FrameVizViewer 
              name="collision_viewer"
              :view-id="collisionViewId"
              @ready="onCollisionViewerReady"
              @error="onViewerError"
              @registered="onViewerRegistered"
            />
          </div>
        </div>
      </section>
    </main>
    
    <footer class="footer">
      <span>FrameViz Embedded UI Demo</span>
      <span v-if="viewerInfo.main_viewer">View: {{ viewerInfo.main_viewer.viewId }}</span>
      <span v-if="viewerInfo.collision_viewer">Collision: {{ viewerInfo.collision_viewer.viewId }}</span>
      <span :class="backendConnected ? 'status-online' : 'status-offline'">
        Backend: {{ backendConnected ? 'Connected' : 'Disconnected' }}
      </span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { FrameVizViewer, useFrameViz } from '@frameviz/vue'
import type { FrameVizCore } from '@frameviz/core'
import ControlPanel from './components/ControlPanel.vue'

const MAIN_VIEWER_NAME = 'main_viewer'
const COLLISION_VIEWER_NAME = 'collision_viewer'

const mainViewId = ref<string | undefined>(resolveViewId(MAIN_VIEWER_NAME))
const collisionViewId = ref<string | undefined>(resolveViewId(COLLISION_VIEWER_NAME))

const { isConnected } = useFrameViz({ scope: mainViewId.value || MAIN_VIEWER_NAME })

const coreRef = ref<FrameVizCore>()
const viewerInfo = ref<Record<string, { viewerName: string; viewId: string; sceneId: string }>>({})
const backendConnected = ref(false)
const jointPositions = ref([0, 0, 0, 0, 0, 0]) // in degrees
let backendSocket: WebSocket | null = null

const BACKEND_WS_URL = import.meta.env.VITE_URDF_ROBOT_BACKEND_WS_URL || 'ws://127.0.0.1:9620'
const BACKEND_RECONNECT_DELAY_MS = 2000
function resolveViewId(viewerName: string): string | undefined {
  if (typeof window === 'undefined') return undefined
  const injectedViewId = (window as any).__FRAMEVIZ_VIEW_ID__
  const params = new URLSearchParams(window.location.search)
  const paramViewId = params.get('view_id')
  const explicitViewId =
    viewerName === MAIN_VIEWER_NAME
      ? (typeof injectedViewId === 'string' && injectedViewId.length > 0
        ? injectedViewId
        : (paramViewId && paramViewId.length > 0 ? paramViewId : undefined))
      : undefined
  const storageKey = `frameviz_view_id:${viewerName}`
  try {
    const storage = getStorage()
    const existing = storage?.getItem(storageKey)
    if (existing) return existing
    const generated =
      explicitViewId
        ? explicitViewId
        : `v_${Math.random().toString(36).slice(2, 10)}`
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
  backendSocket = new WebSocket(BACKEND_WS_URL)

  backendSocket.onopen = () => {
    backendSocket?.send(JSON.stringify({ type: 'auth', token: businessToken }))
  }

  backendSocket.onclose = () => {
    backendConnected.value = false
    backendSocket = null
    setTimeout(connectBackend, BACKEND_RECONNECT_DELAY_MS)
  }

  backendSocket.onerror = () => {
    backendSocket?.close()
  }
  
  backendSocket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'auth_ok') {
        backendConnected.value = true
        syncViewIdsToBackend()
        return
      }
      // Handle state updates from backend
      if (msg.type === 'state_update' && msg.joint_positions) {
        // Convert radians to degrees
        jointPositions.value = msg.joint_positions.map((rad: number) => rad * 180 / Math.PI)
      }
    } catch (err) {
    }
  }
}

function sendBackendCommand(cmd: { name: string; args: Record<string, any> }) {
  if (!backendConnected.value || !backendSocket || backendSocket.readyState !== WebSocket.OPEN) {
    return
  }
  backendSocket.send(JSON.stringify(cmd))
}

function syncViewIdsToBackend() {
  const main = viewerInfo.value[MAIN_VIEWER_NAME]?.viewId
  const collision = viewerInfo.value[COLLISION_VIEWER_NAME]?.viewId
  sendBackendCommand({
    name: 'set_view_ids',
    args: {
      main_view_id: main || null,
      collision_view_id: collision || null,
    },
  })
}

onMounted(() => {
  connectBackend()
})

onUnmounted(() => {
  backendSocket?.close()
})

function onMainViewerReady(core: FrameVizCore) {
  coreRef.value = core
}

function onCollisionViewerReady(core: FrameVizCore) {
}

function onViewerError(error: Error) {
  console.error('Viewer error:', error)
}

function onViewerRegistered(info: { viewerName: string; viewId: string; sceneId: string }) {
  viewerInfo.value = { ...viewerInfo.value, [info.viewerName]: info }
  syncViewIdsToBackend()
}

function handleCommand(cmd: { name: string; args: Record<string, any> }) {
  sendBackendCommand(cmd)
}
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
  min-height: 0; /* Important: allows flex children to shrink below content size */
}

.sidebar {
  width: 280px;
  background: #16213e;
  border-right: 1px solid #0f3460;
  overflow-y: auto;
}

.viewer-container {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.viewer-stack {
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: 12px;
  padding: 12px;
  flex: 1;
  min-height: 0;
  min-width: 0;
}

.viewer-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  border: 1px solid #0f3460;
  background: #121826;
}

.viewer-title {
  padding: 6px 10px;
  font-size: 12px;
  color: #9aa0b5;
  border-bottom: 1px solid #0f3460;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.viewer-panel :deep(.frameviz-viewer) {
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
