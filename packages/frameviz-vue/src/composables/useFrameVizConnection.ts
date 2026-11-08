import { computed, ref, watch } from 'vue'
import { useFrameViz } from './useFrameViz'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

type ConnectionInfo = {
    wsUrl?: string
}

type UseFrameVizConnectionOptions = {
    scope?: string
    viewId?: string
    authToken?: string
    autoStartHost?: boolean
    autoRetry?: boolean
    onConnected?: (info: ConnectionInfo) => void
    onError?: (error: Error) => void
}

async function tryStartHost(): Promise<boolean> {
    if (typeof window === 'undefined') return false
    const starter = (window as any).__FRAMEVIZ_START_HOST__
    if (typeof starter !== 'function') {
        return false
    }
    try {
        await starter()
        return true
    } catch (err) {
        console.warn('[FrameViz] Host auto-start failed:', err)
        return false
    }
}

export function useFrameVizConnection(options: UseFrameVizConnectionOptions = {}) {
    const connectionStatus = ref<ConnectionStatus>('disconnected')
    const error = ref<Error | null>(null)
    const frameviz = useFrameViz({ scope: options.scope })
    const isConnected = computed(() => frameviz.isConnected.value)
    let stopped = false
    let retryTimer: number | null = null
    let retryDelayMs = 2000

    watch(isConnected, (connected) => {
        if (!connected && connectionStatus.value === 'connected') {
            connectionStatus.value = 'disconnected'
        }
        if (connected) {
            connectionStatus.value = 'connected'
            error.value = null
        }
        if (connected && retryTimer !== null) {
            window.clearTimeout(retryTimer)
            retryTimer = null
            retryDelayMs = 2000
        }
    })

    function scheduleRetry(): void {
        if (stopped) return
        if (typeof window === 'undefined') return
        if (retryTimer !== null) return
        retryTimer = window.setTimeout(async () => {
            retryTimer = null
            retryDelayMs = Math.min(retryDelayMs * 1.5, 10000)
            // Pass silent=true so connectionStatus stays 'error' during retry —
            // prevents the overlay from jumping between connecting/error states.
            await connect(true)
        }, retryDelayMs)
    }

    async function connect(silent = false): Promise<void> {
        if (stopped) return
        if (frameviz.isConnected.value) {
            connectionStatus.value = 'connected'
            return
        }
        if (!silent) {
            connectionStatus.value = 'connecting'
        }
        error.value = null

        try {
            await frameviz.connect(undefined, { viewId: options.viewId, authToken: options.authToken })
            connectionStatus.value = 'connected'
            options.onConnected?.({ wsUrl: frameviz.connectionState.value.wsUrl })
        } catch (err) {
            const errorObj = err instanceof Error ? err : new Error('Failed to connect')
            if (options.autoStartHost) {
                const started = await tryStartHost()
                if (started) {
                    try {
                        await frameviz.connect(undefined, { viewId: options.viewId, authToken: options.authToken })
                        connectionStatus.value = 'connected'
                        options.onConnected?.({ wsUrl: frameviz.connectionState.value.wsUrl })
                        return
                    } catch (retryErr) {
                        const retryObj = retryErr instanceof Error
                            ? retryErr
                            : new Error('Failed to connect after auto-start')
                        error.value = retryObj
                        connectionStatus.value = 'error'
                        options.onError?.(retryObj)
                        return
                    }
                }
            }

            error.value = errorObj
            connectionStatus.value = 'error'
            options.onError?.(errorObj)
            if (options.autoRetry ?? options.autoStartHost) {
                scheduleRetry()
            }
        }
    }

    function disconnect() {
        stopped = true
        if (retryTimer !== null) window.clearTimeout(retryTimer)
        retryTimer = null
        frameviz.disconnect()
    }
    return {
        disconnect,
        sendCommand: frameviz.sendCommand,
        connect,
        retry: connect,
        isConnected,
        connectionStatus,
        error,
        registerViewer: frameviz.registerViewer,
        sendEvent: frameviz.sendEvent,
    }
}
