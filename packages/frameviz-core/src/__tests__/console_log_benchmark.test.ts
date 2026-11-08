// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as THREE from 'three';
import { SceneManager } from '../SceneManager';

// Mock WebGL Renderer
vi.mock('three', async () => {
  const actual = await vi.importActual<typeof THREE>('three');
  return {
    ...actual,
    WebGLRenderer: vi.fn().mockImplementation(() => ({
      setSize: vi.fn(),
      setPixelRatio: vi.fn(),
      render: vi.fn(),
      dispose: vi.fn(),
      domElement: document.createElement('canvas'),
      getContext: vi.fn().mockReturnValue({
        getExtension: vi.fn(),
        getParameter: vi.fn().mockReturnValue(16),
      }),
      capabilities: {
        maxTextureSize: 16384,
      },
      info: {
        render: { triangles: 0, points: 0, lines: 0, frame: 0 },
        memory: { geometries: 0, textures: 0 },
      },
    })),
  };
});

// Mock CSS2DRenderer
vi.mock('three/examples/jsm/renderers/CSS2DRenderer.js', () => {
  return {
    CSS2DRenderer: vi.fn().mockImplementation(() => ({
      setSize: vi.fn(),
      render: vi.fn(),
      domElement: document.createElement('div'),
    })),
  };
});

describe('SceneManager Performance Benchmark', () => {
  let container: HTMLElement;
  let sceneManager: SceneManager;
  let originalConsoleLog: any;

  beforeEach(() => {
    container = document.createElement('div');
    container.style.width = '800px';
    container.style.height = '600px';
    document.body.appendChild(container);
    sceneManager = new SceneManager({ container });

    // Silence console.log during benchmark to avoid cluttering output,
    // but we can still measure the overhead of the call mechanism if we want,
    // although silencing it might make it faster.
    // To truly measure the cost of the *logic* leading up to it and the call itself,
    // we should probably keep it or mock it with an empty function.
    // However, the real cost is often serialization and I/O.
    // Let's mock it with a minimal function to measure the overhead of the *check* and the *call*.
    originalConsoleLog = console.log;
    console.log = vi.fn();
  });

  afterEach(() => {
    if (sceneManager) {
      sceneManager.dispose();
    }
    if (container && container.parentNode) {
      document.body.removeChild(container);
    }
    console.log = originalConsoleLog;
  });

  it('measures render loop performance', () => {
    const iterations = 10000; // Enough to trigger the log check many times

    // Simulate frames
    const startTime = performance.now();

    for (let i = 0; i < iterations; i++) {
        // Manually update the frame count on the mock renderer
        sceneManager.renderer.info.render.frame = i;
        sceneManager.render();
    }

    const endTime = performance.now();
    const duration = endTime - startTime;

    console.info(`[Benchmark] ${iterations} frames took ${duration.toFixed(2)}ms`);

    // We expect some overhead if the logging logic is present.
    // The test passes if it runs. Use this to manually verify improvement.
    expect(true).toBe(true);
  });
});
