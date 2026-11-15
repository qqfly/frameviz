export interface ViewMount {
  kind: "dom";
  element_id: string;
}

export interface CreateViewArgs {
  title?: string;
  width?: number;
  height?: number;
  scene_id?: string;
  view_id?: string;  // Optional: client-specified view_id
  mount?: ViewMount;
}

export interface CreateViewResult {
  view_id: string;
  scene_id: string;
}

export interface FrameVizCoreOptions {
  container?: HTMLElement;
  canvas?: HTMLCanvasElement;
  overlay?: HTMLElement;
  viewId?: string;
  performanceMode?: 'performance' | 'balanced' | 'quality';
  background?: number;  // Initial background color (hex, e.g., 0x1e1e2a)
  keyboardShortcuts?: boolean;
  onKeyboardShortcutsChange?: (enabled: boolean) => void;
  showWidgetPanel?: boolean;
  debug?: boolean;
  onEvent?: (name: string, data: Record<string, unknown>) => void;
  onCommand?: (name: string, args: Record<string, unknown>) => void;
}
