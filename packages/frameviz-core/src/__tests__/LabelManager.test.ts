import { describe, it, expect, beforeEach, vi } from 'vitest';
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import { LabelManager } from '../LabelManager';

// Mock CSS2DObject
vi.mock('three/examples/jsm/renderers/CSS2DRenderer.js', () => {
  return {
    CSS2DObject: vi.fn().mockImplementation((element) => {
      const obj = {
        element,
        position: { x: 0, y: 0, z: 0, set: vi.fn() },
        userData: {},
        parent: null,
      };
      return obj;
    }),
  };
});

describe('LabelManager', () => {
  let manager: LabelManager;

  beforeEach(() => {
    manager = new LabelManager();
  });

  describe('createLabel', () => {
    it('should create a label with default styling', () => {
      const label = manager.createLabel('Hello World');

      expect(label).toBeDefined();
      expect(label.userData.div).toBeDefined();
      const div = label.userData.div as HTMLDivElement;
      expect(div.textContent).toBe('Hello World');
      expect(div.style.color).toBe('white');
      expect(div.style.fontSize).toBe('14px');
    });

    it('should apply custom color', () => {
      const label = manager.createLabel('Test', { color: 'red' });

      const div = label.userData.div as HTMLDivElement;
      expect(div.style.color).toBe('red');
    });

    it('should apply custom font size', () => {
      const label = manager.createLabel('Test', { fontSize: 20 });

      const div = label.userData.div as HTMLDivElement;
      expect(div.style.fontSize).toBe('20px');
    });

    it('should apply custom font family', () => {
      const label = manager.createLabel('Test', { fontFamily: 'Comic Sans' });

      const div = label.userData.div as HTMLDivElement;
      expect(div.style.fontFamily).toBe('Comic Sans');
    });

    it('should apply custom background color', () => {
      const label = manager.createLabel('Test', { backgroundColor: 'rgba(255, 0, 0, 0.5)' });

      const div = label.userData.div as HTMLDivElement;
      expect(div.style.backgroundColor).toBe('rgba(255, 0, 0, 0.5)');
    });

    it('should set label class', () => {
      const label = manager.createLabel('Test');

      const div = label.userData.div as HTMLDivElement;
      expect(div.className).toBe('label');
    });

    it('should set default styling', () => {
      const label = manager.createLabel('Test');

      const div = label.userData.div as HTMLDivElement;
      expect(div.style.padding).toBe('2px 6px');
      expect(div.style.borderRadius).toBe('4px');
      expect(div.style.whiteSpace).toBe('nowrap');
    });
  });

  describe('create3DText', () => {
    it('should create label at specified position', () => {
      const label = manager.create3DText('Hello', [1, 2, 3]);

      expect(label.position.set).toHaveBeenCalledWith(1, 2, 3);
      const div = label.userData.div as HTMLDivElement;
      expect(div.textContent).toBe('Hello');
    });

    it('should apply options to 3D text', () => {
      const label = manager.create3DText('Test', [0, 0, 0], {
        color: 'blue',
        fontSize: 18,
      });

      const div = label.userData.div as HTMLDivElement;
      expect(div.style.color).toBe('blue');
      expect(div.style.fontSize).toBe('18px');
    });
  });

  describe('updateLabel', () => {
    it('should update text content', () => {
      const label = manager.createLabel('Old Text');
      manager.updateLabel(label, { text: 'New Text' });

      const div = label.userData.div as HTMLDivElement;
      expect(div.textContent).toBe('New Text');
    });

    it('should update position', () => {
      const label = manager.createLabel('Test');
      manager.updateLabel(label, { pos: [5, 6, 7] });

      expect(label.position.set).toHaveBeenCalledWith(5, 6, 7);
    });

    it('should update color from RGB values', () => {
      const label = manager.createLabel('Test');
      manager.updateLabel(label, { color: [1.0, 0.5, 0.25] });

      const div = label.userData.div as HTMLDivElement;
      // jsdom normalizes rgb format with spaces
      expect(div.style.color).toMatch(/rgb\(255,\s*128,\s*64\)/);
    });

    it('should update font size', () => {
      const label = manager.createLabel('Test');
      manager.updateLabel(label, { fontSize: 24 });

      const div = label.userData.div as HTMLDivElement;
      expect(div.style.fontSize).toBe('24px');
    });

    it('should update multiple properties at once', () => {
      const label = manager.createLabel('Test');
      manager.updateLabel(label, {
        text: 'Updated',
        pos: [1, 2, 3],
        color: [0, 1, 0],
        fontSize: 16,
      });

      const div = label.userData.div as HTMLDivElement;
      expect(div.textContent).toBe('Updated');
      expect(label.position.set).toHaveBeenCalledWith(1, 2, 3);
      // jsdom normalizes rgb format with spaces
      expect(div.style.color).toMatch(/rgb\(0,\s*255,\s*0\)/);
      expect(div.style.fontSize).toBe('16px');
    });

    it('should handle missing div gracefully', () => {
      const label = {
        userData: {},
        position: { set: vi.fn() },
      } as any;

      expect(() => manager.updateLabel(label, { text: 'Test' })).not.toThrow();
    });

    it('should handle partial updates', () => {
      const label = manager.createLabel('Test');
      const div = label.userData.div as HTMLDivElement;
      const originalText = div.textContent;

      manager.updateLabel(label, { fontSize: 20 });

      expect(div.textContent).toBe(originalText);
      expect(div.style.fontSize).toBe('20px');
    });
  });

  describe('getLabelElement', () => {
    it('should return the label div element', () => {
      const label = manager.createLabel('Test');
      const div = manager.getLabelElement(label);

      expect(div).toBeDefined();
      expect(div?.textContent).toBe('Test');
    });

    it('should return undefined for label without div', () => {
      const label = {
        userData: {},
      } as any;

      const div = manager.getLabelElement(label);
      expect(div).toBeUndefined();
    });
  });

  describe('removeLabel', () => {
    it('should remove label from parent', () => {
      const label = manager.createLabel('Test');
      label.parent = {
        remove: vi.fn(),
      } as any;

      manager.removeLabel(label);

      expect(label.parent.remove).toHaveBeenCalledWith(label);
    });

    it('should handle label without parent', () => {
      const label = manager.createLabel('Test');
      label.parent = null;

      expect(() => manager.removeLabel(label)).not.toThrow();
    });

    it('should remove div from DOM', () => {
      const label = manager.createLabel('Test');
      const div = label.userData.div as HTMLDivElement;
      const parent = document.createElement('div');
      parent.appendChild(div);

      manager.removeLabel(label);

      expect(parent.contains(div)).toBe(false);
    });

    it('should handle div without parent node', () => {
      const label = manager.createLabel('Test');

      expect(() => manager.removeLabel(label)).not.toThrow();
    });
  });
});
