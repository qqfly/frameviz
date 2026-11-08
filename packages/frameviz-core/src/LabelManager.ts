import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

export interface LabelOptions {
  color?: string;
  fontSize?: number;
  fontFamily?: string;
  backgroundColor?: string;
}

export interface LabelUpdateOptions {
  text?: string;
  pos?: [number, number, number];
  color?: [number, number, number]; // RGB 0-1
  fontSize?: number;
}

/**
 * Manages 2D text labels in 3D space using CSS2DRenderer.
 * Labels are HTML elements positioned in 3D space that always face the camera.
 */
export class LabelManager {
  /**
   * Create a CSS2D label with text and styling options.
   * @param text - The text content of the label
   * @param options - Styling options for the label
   * @returns CSS2DObject containing the label
   */
  createLabel(text: string, options: LabelOptions = {}): CSS2DObject {
    const div = document.createElement('div');
    div.className = 'label';
    div.textContent = text;
    div.style.color = options.color || 'white';
    div.style.fontSize = (options.fontSize || 14) + 'px';
    div.style.fontFamily = options.fontFamily || 'Arial, sans-serif';
    div.style.padding = '2px 6px';
    div.style.backgroundColor = options.backgroundColor || 'rgba(0, 0, 0, 0.6)';
    div.style.borderRadius = '4px';
    div.style.whiteSpace = 'nowrap';

    const label = new CSS2DObject(div);
    label.userData.div = div; // Store reference for updates

    return label;
  }

  /**
   * Create a 3D text label at a specific position.
   * @param text - The text content
   * @param pos - Position in 3D space [x, y, z]
   * @param options - Styling options for the label
   * @returns CSS2DObject positioned in 3D space
   */
  create3DText(
    text: string,
    pos: [number, number, number],
    options: LabelOptions = {}
  ): CSS2DObject {
    const label = this.createLabel(text, options);
    label.position.set(pos[0], pos[1], pos[2]);
    return label;
  }

  /**
   * Update an existing label's properties.
   * @param label - The CSS2DObject label to update
   * @param updates - Properties to update
   */
  updateLabel(label: CSS2DObject, updates: LabelUpdateOptions): void {
    const div = label.userData.div as HTMLDivElement;
    if (!div) return;

    if (updates.text !== undefined) {
      div.textContent = updates.text;
    }

    if (updates.pos !== undefined) {
      label.position.set(updates.pos[0], updates.pos[1], updates.pos[2]);
    }

    if (updates.color !== undefined) {
      const r = Math.round(updates.color[0] * 255);
      const g = Math.round(updates.color[1] * 255);
      const b = Math.round(updates.color[2] * 255);
      div.style.color = `rgb(${r},${g},${b})`;
    }

    if (updates.fontSize !== undefined) {
      div.style.fontSize = updates.fontSize + 'px';
    }
  }

  /**
   * Get the underlying DOM element of a label.
   * @param label - The CSS2DObject label
   * @returns The HTMLDivElement or undefined
   */
  getLabelElement(label: CSS2DObject): HTMLDivElement | undefined {
    return label.userData.div as HTMLDivElement;
  }

  /**
   * Remove a label and clean up its DOM element.
   * @param label - The label to remove
   */
  removeLabel(label: CSS2DObject): void {
    const div = label.userData.div as HTMLDivElement;
    if (div && div.parentNode) {
      div.parentNode.removeChild(div);
    }

    if (label.parent) {
      label.parent.remove(label);
    }
  }
}
