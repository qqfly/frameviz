import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useFrameVizConnection } from '../src/composables/useFrameVizConnection'

vi.mock('../src/composables/useFrameViz', async () => {
    const { ref } = await import('vue')
    const state = {
        connectImpl: async () => {},
    }
    return {
        useFrameViz: () => ({
            isConnected: ref(false),
            connectionState: ref({ wsUrl: 'ws://127.0.0.1:9527' }),
            connect: (...args: any[]) => state.connectImpl(...args),
            registerViewer: vi.fn(),
        }),
        __setConnectImpl: (fn: (...args: any[]) => Promise<void>) => {
            state.connectImpl = fn
        },
    }
})

describe('useFrameVizConnection', () => {
    beforeEach(async () => {
        const mockModule = (await import('../src/composables/useFrameViz')) as {
            __setConnectImpl: (fn: (...args: any[]) => Promise<void>) => void
        }
        mockModule.__setConnectImpl(async () => {})
        ;(window as any).__FRAMEVIZ_START_HOST__ = undefined
    })

    it('connects successfully', async () => {
        const { connect, connectionStatus, error } = useFrameVizConnection()
        await connect()
        expect(connectionStatus.value).toBe('connected')
        expect(error.value).toBeNull()
    })

    it('auto-starts host on failure', async () => {
        const attempts = { count: 0 }
        const mockModule = (await import('../src/composables/useFrameViz')) as {
            __setConnectImpl: (fn: (...args: any[]) => Promise<void>) => void
        }
        mockModule.__setConnectImpl(async () => {
            attempts.count += 1
            if (attempts.count === 1) {
                throw new Error('first fail')
            }
        })
        ;(window as any).__FRAMEVIZ_START_HOST__ = vi.fn(async () => {})
        const { connect, connectionStatus } = useFrameVizConnection({
            autoStartHost: true,
        })
        await connect()
        expect(connectionStatus.value).toBe('connected')
        expect((window as any).__FRAMEVIZ_START_HOST__).toHaveBeenCalled()
    })

    it('reports error when auto-start disabled', async () => {
        const mockModule = (await import('../src/composables/useFrameViz')) as {
            __setConnectImpl: (fn: (...args: any[]) => Promise<void>) => void
        }
        mockModule.__setConnectImpl(async () => {
            throw new Error('no host')
        })
        const onError = vi.fn()
        const { connect, connectionStatus, error } = useFrameVizConnection({
            autoStartHost: false,
            onError,
        })
        await connect()
        expect(connectionStatus.value).toBe('error')
        expect(error.value?.message).toBe('no host')
        expect(onError).toHaveBeenCalled()
    })

    it('auto-retries after failure when enabled', async () => {
        vi.useFakeTimers()
        const mockModule = (await import('../src/composables/useFrameViz')) as {
            __setConnectImpl: (fn: (...args: any[]) => Promise<void>) => void
        }
        mockModule.__setConnectImpl(async () => {
            throw new Error('no host')
        })
        const { connect, connectionStatus } = useFrameVizConnection({
            autoStartHost: false,
            autoRetry: true,
        })
        await connect()
        expect(connectionStatus.value).toBe('error')
        await vi.advanceTimersByTimeAsync(2000)
        expect(connectionStatus.value).toBe('error')
        vi.useRealTimers()
    })
})
