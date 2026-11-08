import { ref, computed, shallowRef } from 'vue'
import type { Ref, ShallowRef } from 'vue'
import { applySceneSnapshot, decodeBufferBase64, type FrameVizCore } from '@frameviz/core'
import { PROTOCOL_VERSION } from '@frameviz/protocol'
import type { ViewerInfo, ConnectionState } from '../types'

type PendingRequest = {
    timer: ReturnType<typeof setTimeout>
    resolve: (value: any) => void
    reject: (error: Error) => void
}

type ClientState = {
    wsUrl: Ref<string>
    ws: ShallowRef<WebSocket | null>
    isConnected: Ref<boolean>
    connectionError: Ref<Error | null>
    viewers: Ref<Map<string, ViewerInfo>>
    messageId: number
    pendingRequests: Map<string, PendingRequest>
    coreInstances: Map<string, FrameVizCore>
    pendingBinaryQueue: Array<{ buffer_id: string; offset_bytes: number }>
    connectPromise: Promise<void> | null
    stopped: boolean
    reconnectTimer: ReturnType<typeof setTimeout> | null
}

type ConnectOptions = {
    viewId?: string
    authToken?: string
}

type UseFrameVizOptions = {
    scope?: string
}

const RECONNECT_DELAY_MS = 2000

const clientStates = new Map<string, ClientState>()

function createClientState(): ClientState {
    return {
        wsUrl: ref<string>('ws://127.0.0.1:9527'),
        ws: shallowRef<WebSocket | null>(null),
        isConnected: ref(false),
        connectionError: ref<Error | null>(null),
        viewers: ref<Map<string, ViewerInfo>>(new Map()),
        messageId: 0,
        pendingRequests: new Map(),
        coreInstances: new Map(),
        pendingBinaryQueue: [],
        connectPromise: null,
        stopped: false,
        reconnectTimer: null,
    }
}

function getClientState(scope: string): ClientState {
    const existing = clientStates.get(scope)
    if (existing) return existing
    const created = createClientState()
    clientStates.set(scope, created)
    return created
}

function resolveViewIdFromWindow(): string | undefined {
    if (typeof window === 'undefined') return undefined
    const injectedViewId = (window as any).__FRAMEVIZ_VIEW_ID__
    if (typeof injectedViewId === 'string' && injectedViewId.length > 0) {
        return injectedViewId
    }
    const params = new URLSearchParams(window.location.search)
    const paramViewId = params.get('view_id')
    if (paramViewId && paramViewId.length > 0) {
        return paramViewId
    }
    return undefined
}

function buildViewerWsUrl(baseUrl: string, viewId?: string): string {
    const url = new URL(baseUrl)
    url.searchParams.set('type', 'viewer')
    if (viewId && !url.searchParams.has('view_id')) {
        url.searchParams.set('view_id', viewId)
    }
    return url.toString()
}

export function useFrameViz(options: UseFrameVizOptions = {}) {
    const scope = options.scope ?? 'default'
    const state = getClientState(scope)

    function resolveWsUrl(input?: string): string {
        if (input) return input
        if (typeof window === 'undefined') {
            return state.wsUrl.value
        }
        const params = new URLSearchParams(window.location.search)
        const injectedPort = (window as any).__FRAMEVIZ_WS_PORT__
        const paramPort = params.get('ws_port')
        const port = Number(injectedPort || paramPort)
        if (Number.isFinite(port) && port > 0) {
            return `ws://127.0.0.1:${port}`
        }
        return state.wsUrl.value
    }

    async function connect(url?: string, options: ConnectOptions = {}): Promise<void> {
        if (state.ws.value?.readyState === WebSocket.OPEN) {
            return
        }
        if (state.ws.value?.readyState === WebSocket.CONNECTING) {
            if (state.connectPromise) {
                return state.connectPromise
            }
            return
        }

        state.stopped = false
        const targetUrl = resolveWsUrl(url)
        state.wsUrl.value = targetUrl
        const resolvedViewId = options.viewId ?? resolveViewIdFromWindow()
        const connectUrl = buildViewerWsUrl(targetUrl, resolvedViewId)

        state.connectPromise = new Promise((resolve, reject) => {
            const socket = new WebSocket(connectUrl)
            socket.binaryType = 'arraybuffer'

            state.ws.value = socket
            const authTimer = setTimeout(() => { reject(new Error('Authentication timed out')); socket.close() }, 10000)
            socket.onopen = () => {
                const token = options.authToken || (window as any).__FRAMEVIZ_AUTH_TOKEN__ || new URLSearchParams(window.location.hash.slice(1)).get('token')
                if (!token) { clearTimeout(authTimer); reject(new Error('Authentication token required')); socket.close(); return }
                socket.send(JSON.stringify({ type: 'auth', token }))
            }

            socket.onerror = () => {
                clearTimeout(authTimer)
                const error = new Error('WebSocket connection failed')
                state.connectionError.value = error
                state.connectPromise = null
                reject(error)
            }

            socket.onclose = () => {
                clearTimeout(authTimer)
                state.isConnected.value = false
                state.ws.value = null
                state.connectPromise = null
                state.pendingBinaryQueue = []
                reject(new Error('Connection closed'))
                for (const pending of state.pendingRequests.values()) {
                    clearTimeout(pending.timer)
                    pending.reject(new Error('Connection closed'))
                }
                state.pendingRequests.clear()
                if (!state.stopped) state.reconnectTimer = setTimeout(() => {
                    if (!state.stopped && !state.isConnected.value) connect(targetUrl, { ...options, viewId: resolvedViewId }).catch(() => {})
                }, RECONNECT_DELAY_MS)
            }

            socket.onmessage = (event) => {
                if (typeof event.data === 'string') {
                    const message = JSON.parse(event.data)
                    if (message.type === 'auth_resp') {
                        clearTimeout(authTimer)
                        if (message.protocol_version !== PROTOCOL_VERSION) { state.stopped = true; reject(new Error('Host protocol version mismatch')); socket.close(); return }
                        if (!message.ok) { state.stopped = true; reject(new Error('Authentication failed')); socket.close(); return }
                        state.isConnected.value = true
                        state.connectionError.value = null
                        state.connectPromise = null
                        resolve()
                        return
                    }
                    handleTextMessage(event.data)
                } else {
                    handleBinaryMessage(event.data)
                }
            }
        })
        return state.connectPromise
    }

    function handleTextMessage(data: string) {
        try {
            const msg = JSON.parse(data)

            if (msg.type === 'cmd') {
                if (msg.name === 'upload_buffer_chunk') {
                    if (msg.args.data_base64 !== undefined) {
                        for (const core of state.coreInstances.values()) core.storeBufferData(msg.args.buffer_id, msg.args.offset_bytes || 0, decodeBufferBase64(msg.args.data_base64))
                        return
                    }
                    state.pendingBinaryQueue.push({
                        buffer_id: msg.args.buffer_id,
                        offset_bytes: msg.args.offset_bytes || 0
                    })
                }

                for (const core of state.coreInstances.values()) {
                    core.handleCommand(msg.name, msg.args)
                }
                return
            }

            if (msg.type === 'sync') {
                for (const core of state.coreInstances.values()) {
                    if (core.acceptRevision(msg.revision)) core.handleCommand(msg.command, msg.args, msg.result || {})
                }
                return
            }

            if (msg.type === 'scene_snapshot') {
                for (const core of state.coreInstances.values()) applySceneSnapshot(core, msg)
                return
            }

            if (msg.type === 'init') {
                if (msg.scene_id) {
                    for (const core of state.coreInstances.values()) {
                        if (typeof msg.view_id === 'string' && msg.view_id.length > 0) {
                            core.setViewId(msg.view_id)
                        }
                        core.sceneRevision = 0
                        core.createScene(msg.scene_id)
                    }
                }
                return
            }

            if (msg.type === 'resp' && msg.id && state.pendingRequests.has(msg.id)) {
                const { resolve, reject, timer } = state.pendingRequests.get(msg.id)!
                clearTimeout(timer)
                state.pendingRequests.delete(msg.id)

                if (msg.ok) {
                    resolve(msg.result)
                } else {
                    reject(new Error(msg.error?.message || 'Unknown error'))
                }
            }
        } catch (e) {
            console.error('[FrameViz] Failed to parse message:', e)
        }
    }

    function handleBinaryMessage(data: ArrayBuffer) {
        const pending = state.pendingBinaryQueue.shift()
        if (!pending) return

        const bytes = new Uint8Array(data)
        for (const core of state.coreInstances.values()) {
            core.storeBufferData(pending.buffer_id, pending.offset_bytes, bytes)
        }
    }

    async function sendCommand(name: string, args: Record<string, any>): Promise<any> {
        if (!state.ws.value || state.ws.value.readyState !== WebSocket.OPEN) {
            throw new Error('Not connected to Host')
        }

        const id = String(++state.messageId)

        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                state.pendingRequests.delete(id)
                reject(new Error(`Command '${name}' timed out`))
            }, 10000)
            state.pendingRequests.set(id, { resolve, reject, timer })
            try {
                state.ws.value!.send(JSON.stringify({ protocol_version: PROTOCOL_VERSION, type: 'cmd', id, name, args }))
            } catch (error) {
                clearTimeout(timer)
                state.pendingRequests.delete(id)
                reject(error)
            }
        })
    }

    function sendEvent(name: string, data: Record<string, any>): void {
        if (!state.ws.value || state.ws.value.readyState !== WebSocket.OPEN) {
            return
        }

        state.ws.value.send(JSON.stringify({
            protocol_version: PROTOCOL_VERSION,
            type: 'event',
            name,
            data,
        }))
    }

    async function registerViewer(
        name: string,
        core: FrameVizCore,
        sceneId?: string
    ): Promise<ViewerInfo> {
        state.coreInstances.set(name, core)
        const result = await sendCommand('register_viewer', {
            viewer_name: name,
            scene_id: sceneId,
        })

        if (state.stopped) throw new Error('Viewer was unmounted during registration')
        const info: ViewerInfo = {
            viewerName: result.viewer_name,
            viewId: result.view_id,
            sceneId: result.scene_id,
        }

        core.setViewId(info.viewId)
        state.viewers.value.set(name, info)
        state.coreInstances.set(name, core)
        return info
    }

    function disconnect(): void {
        state.stopped = true
        if (state.reconnectTimer) clearTimeout(state.reconnectTimer)
        state.reconnectTimer = null
        const socket = state.ws.value
        state.ws.value = null
        state.isConnected.value = false
        for (const pending of state.pendingRequests.values()) {
            clearTimeout(pending.timer)
            pending.reject(new Error('Connection closed'))
        }
        state.pendingRequests.clear()
        socket?.close()
        state.coreInstances.clear()
        state.viewers.value.clear()
        clientStates.delete(scope)
    }

    const connectionState = computed<ConnectionState>(() => ({
        connected: state.isConnected.value,
        error: state.connectionError.value,
        wsUrl: state.wsUrl.value,
    }))

    return {
        connect,
        disconnect,
        sendCommand,
        sendEvent,
        registerViewer,
        isConnected: computed(() => state.isConnected.value),
        connectionState,
        viewers: computed(() => state.viewers.value),
    }
}
