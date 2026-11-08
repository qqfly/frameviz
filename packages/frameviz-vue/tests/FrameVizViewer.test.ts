import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createApp, nextTick } from 'vue'
import FrameVizViewer from '../src/components/FrameVizViewer.vue'
import { FrameVizCore } from '@frameviz/core'

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const renderMock = vi.fn()
const resizeMock = vi.fn()
const setViewIdMock = vi.fn()
let lastCoreOptions: Record<string, unknown> | undefined
const connectionState = {
  connect: vi.fn().mockResolvedValue(undefined),
  disconnect: vi.fn(),
  sendCommand: vi.fn().mockResolvedValue({}),
  registerViewer: vi.fn(),
  sendEvent: vi.fn(),
  isConnectedValue: false,
  connectionStatusValue: 'disconnected',
}

// Mock FrameVizCore
vi.mock('@frameviz/core', () => {
  return {
    FrameVizCore: vi.fn().mockImplementation((options) => {
      lastCoreOptions = options
      return {
      resize: resizeMock,
      render: renderMock,
      setKeyboardShortcutsEnabled: vi.fn(),
      setViewId: setViewIdMock,
      handleCommand: vi.fn(),
      getCameraPose: vi.fn(),
      dispose: vi.fn(),
    }
    })
  }
})

// Mock useFrameVizConnection
vi.mock('../src/composables/useFrameVizConnection', () => {
  const { computed, ref } = require('vue')
  return {
    useFrameVizConnection: () => ({
      connect: connectionState.connect,
      disconnect: connectionState.disconnect,
      sendCommand: connectionState.sendCommand,
      registerViewer: connectionState.registerViewer,
      sendEvent: connectionState.sendEvent,
      isConnected: computed(() => connectionState.isConnectedValue),
      connectionStatus: ref(connectionState.connectionStatusValue),
      error: ref(null)
    })
  }
})

describe('FrameVizViewer Performance', () => {
  let container: HTMLDivElement
  let app: any

  beforeEach(() => {
    container = document.createElement('div')
    // Give it a size so checks pass
    Object.defineProperty(container, 'getBoundingClientRect', {
      value: vi.fn(() => ({
        width: 800,
        height: 600,
        top: 0,
        left: 0,
        bottom: 600,
        right: 800,
        x: 0,
        y: 0,
        toJSON: () => {}
      })),
      configurable: true
    })
    document.body.appendChild(container)
    renderMock.mockClear()
    resizeMock.mockClear()
    setViewIdMock.mockClear()
    connectionState.connect.mockClear()
    connectionState.registerViewer.mockReset()
    connectionState.sendEvent.mockClear()
    connectionState.isConnectedValue = false
    connectionState.connectionStatusValue = 'disconnected'
    lastCoreOptions = undefined
  })

  afterEach(() => {
    if (app) {
      app.unmount()
      app = null
    }
    document.body.innerHTML = ''
    vi.clearAllMocks()
  })

  it('does NOT call getBoundingClientRect in animation loop (Optimized)', async () => {
    const getBoundingClientRectSpy = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect')

    app = createApp(FrameVizViewer, {
      name: 'test-viewer'
    })
    app.mount(container)

    // Wait for mounted and animation to start
    await nextTick()

    // The loop uses requestAnimationFrame.
    await new Promise(resolve => setTimeout(resolve, 100))

    console.log('Call count:', getBoundingClientRectSpy.mock.calls.length)

    // It should be 0 because we removed the call from the loop,
    // and other initial calls might not happen on HTMLElement.prototype or happen before we spy?
    // Actually we spy before mount.
    // In the optimized code, there are no calls to getBoundingClientRect in the component except maybe inside useFrameVizConnection or other places?
    // The component itself doesn't call it in onMounted either (except indirectly via core maybe).

    expect(getBoundingClientRectSpy.mock.calls.length).toBe(0)

    // Verify render loop is running
    expect(renderMock).toHaveBeenCalled()
    expect(renderMock.mock.calls.length).toBeGreaterThan(2)
    getBoundingClientRectSpy.mockRestore()
  })

  it('forwards core events to the host and stores the registered view id', async () => {
    connectionState.isConnectedValue = true
    connectionState.connectionStatusValue = 'connected'
    connectionState.registerViewer.mockResolvedValue({
      viewerName: 'test-viewer',
      viewId: 'v_test',
      sceneId: 's_test',
    })

    app = createApp(FrameVizViewer, {
      name: 'test-viewer'
    })
    app.mount(container)

    await nextTick()
    await Promise.resolve()
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(connectionState.registerViewer).toHaveBeenCalledWith('test-viewer', expect.anything(), undefined)
    expect(setViewIdMock).toHaveBeenCalledWith('v_test')

    const onEvent = lastCoreOptions?.onEvent as ((name: string, data: Record<string, unknown>) => void) | undefined
    expect(onEvent).toBeTypeOf('function')

    onEvent?.('camera_pose_response', { view_id: 'v_test', eye: [1, 2, 3] })
    expect(connectionState.sendEvent).toHaveBeenCalledWith('camera_pose_response', {
      view_id: 'v_test',
      eye: [1, 2, 3],
    })
  })
})
