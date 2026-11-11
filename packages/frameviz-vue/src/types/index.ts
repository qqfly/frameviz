import type { FrameVizCore } from '@frameviz/core'

export interface FrameVizViewerProps {
  /** Host credential supplied by the embedding application. Never store in source. */
  authToken?: string
    /** Viewer name, used for registration with Host */
    name: string
    /** Optional scene ID to bind to */
    sceneId?: string
    /** Optional view ID to reuse existing view state */
    viewId?: string
    /** Auto-start host when not running (requires host hook support) */
    autoStartHost?: boolean
    /** Background color (hex number, e.g., 0x1a1a2e) */
    background?: number
    /** Show grid helper */
    showGrid?: boolean
    /** Show axes helper */
    showAxes?: boolean
    /** Show the scene controls panel. Defaults to false. */
    showWidgetPanel?: boolean
    /** Enable keyboard shortcuts (space/home/W/ctrl+num) */
    enableKeyboardShortcuts?: boolean
}

export interface FrameVizViewerEmits {
    /** Emitted when FrameVizCore is ready */
    (e: 'ready', core: FrameVizCore): void
    /** Emitted on error */
    (e: 'error', error: Error): void
    /** Emitted when registered with Host */
    (e: 'registered', info: ViewerInfo): void
}

export interface ViewerInfo {
    viewerName: string
    viewId: string
    sceneId: string
}

export interface ConnectionState {
    connected: boolean
    error: Error | null
    wsUrl: string
}
