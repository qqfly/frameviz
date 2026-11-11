export interface WidgetDefinition {
  id: string;
  kind: 'number' | 'checkbox' | 'select' | 'text_input' | 'button' | 'text' | 'group';
  label: string;
  parent: string | null;
  value: number | boolean | string | null;
  minimum?: number;
  maximum?: number;
  step?: number;
  choices?: string[];
  update_mode: 'continuous' | 'commit';
}

type Phase = 'input' | 'commit';
type Submit = (id: string, value: WidgetDefinition['value'], phase: Phase) => void;

interface Row {
  element: HTMLElement;
  setValue: (value: WidgetDefinition['value']) => void;
  dispose?: () => void;
}

export class WidgetPanel {
  private readonly panel = document.createElement('aside');
  private readonly rows = new Map<string, Row>();

  constructor(container: HTMLElement, private submit: Submit) {
    this.panel.setAttribute('aria-label', 'Scene controls');
    this.panel.className = 'frameviz-widget-panel';
    Object.assign(this.panel.style, {
      position: 'absolute', top: '12px', right: '12px', zIndex: '5',
      maxHeight: 'calc(100% - 24px)', width: 'min(260px, calc(100% - 24px))',
      overflow: 'auto', padding: '10px', borderRadius: '8px', boxSizing: 'border-box',
      background: '#202630', color: '#fff', colorScheme: 'dark',
      font: '13px/1.4 system-ui, sans-serif',
    });
    // Viewer shortcuts and camera controls should not consume widget interactions.
    for (const type of ['pointerdown', 'wheel', 'keydown']) {
      this.panel.addEventListener(type, event => event.stopPropagation());
    }
    container.append(this.panel);
    this.updateVisibility();
  }

  private enabled = true;

  setVisible(enabled: boolean): void {
    this.enabled = enabled;
    this.updateVisibility();
  }

  private updateVisibility(): void {
    this.panel.hidden = !this.enabled || this.rows.size === 0;
  }

  reset(widgets: WidgetDefinition[]): void {
    this.remove([...this.rows.keys()]);
    for (const widget of widgets) this.add(widget);
  }

  add(widget: WidgetDefinition): void {
    if (this.rows.has(widget.id)) return;
    let row: Row;
    if (widget.kind === 'group') {
      const element = document.createElement('details');
      const summary = document.createElement('summary');
      element.open = true;
      summary.textContent = widget.label;
      element.append(summary);
      row = { element, setValue: () => {} };
    } else if (widget.kind === 'number') {
      row = this.number(widget);
    } else {
      row = this.control(widget);
    }
    row.element.dataset.widgetId = widget.id;
    Object.assign(row.element.style, { margin: '4px 0', padding: '2px' });
    (this.rows.get(widget.parent ?? '')?.element ?? this.panel).append(row.element);
    this.rows.set(widget.id, row);
    this.updateVisibility();
  }

  update(widget: WidgetDefinition): void {
    this.rows.get(widget.id)?.setValue(widget.value);
  }

  remove(ids: string[]): void {
    for (const id of ids) {
      const row = this.rows.get(id);
      row?.dispose?.();
      row?.element.remove();
      this.rows.delete(id);
    }
    this.updateVisibility();
  }

  dispose(): void {
    this.reset([]);
    this.panel.remove();
  }

  private number(widget: WidgetDefinition): Row {
    const element = document.createElement('div');
    const number = document.createElement('input');
    number.type = 'number';
    number.step = 'any';
    number.setAttribute('aria-label', widget.label);
    number.style.width = '7ch';
    number.value = String(widget.value);
    const label = document.createElement('label');
    label.append(document.createTextNode(widget.label + ' '), number);
    element.append(label);
    const range = document.createElement('input');
    range.type = 'range';
    range.setAttribute('aria-label', widget.label + ' slider');
    range.style.width = '100%';

    if (widget.minimum !== undefined) number.min = String(widget.minimum);
    if (widget.maximum !== undefined) number.max = String(widget.maximum);
    let frame: number | undefined;
    const cancelInput = () => {
      if (frame !== undefined) cancelAnimationFrame(frame);
      frame = undefined;
    };
    let committedValue = Number(widget.value);
    let dragging = false;
    if (widget.minimum !== undefined && widget.maximum !== undefined) {
      range.min = number.min;
      range.max = number.max;
      range.step = widget.step === undefined ? 'any' : String(widget.step);
      range.value = number.value;
      element.append(range);
      range.addEventListener('pointerdown', () => { dragging = true; });
      range.addEventListener('pointercancel', () => {
        dragging = false;
        cancelInput();
        number.value = range.value = String(committedValue);
      });
      range.addEventListener('lostpointercapture', () => { dragging = false; });
      range.addEventListener('input', () => {
        number.value = range.value;
        if (widget.update_mode === 'continuous' && dragging && frame === undefined) {
          frame = requestAnimationFrame(() => {
            frame = undefined;
            this.submit(widget.id, range.valueAsNumber, 'input');
          });
        }
      });
      range.addEventListener('change', () => {
        dragging = false;
        cancelInput();
        this.submit(widget.id, range.valueAsNumber, 'commit');
      });
    }
    number.addEventListener('change', () => {
      if (!number.value || !number.validity.valid) {
        number.value = String(committedValue);
        return;
      }
      range.value = number.value;
      this.submit(widget.id, number.valueAsNumber, 'commit');
    });
    number.addEventListener('keydown', event => {
      if (event.key === 'Enter') number.blur();
      if (event.key === 'Escape') {
        number.value = String(committedValue);
        number.blur();
      }
    });
    return {
      element,
      setValue: value => {
        committedValue = Number(value);
        if (!dragging) number.value = String(value);
        if (!dragging) range.value = String(value);
      },
      dispose: cancelInput,
    };
  }

  private control(widget: WidgetDefinition): Row {
    const element = document.createElement('label');
    element.style.display = 'block';
    element.append(document.createTextNode(widget.label + ' '));
    const commit = (value: WidgetDefinition['value']) => this.submit(widget.id, value, 'commit');
    if (widget.kind === 'text') {
      const text = document.createElement('span');
      text.textContent = String(widget.value);
      element.append(text);
      return { element, setValue: value => { text.textContent = String(value); } };
    }
    if (widget.kind === 'button') {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = widget.label;
      button.addEventListener('click', () => commit(null));
      return { element: button, setValue: () => {} };
    }
    if (widget.kind === 'select') {
      const select = document.createElement('select');
      for (const choice of widget.choices ?? []) {
        const option = document.createElement('option');
        option.textContent = option.value = choice;
        select.append(option);
      }
      select.value = String(widget.value);
      select.addEventListener('change', () => commit(select.value));
      element.append(select);
      return { element, setValue: value => { select.value = String(value); } };
    }
    const input = document.createElement('input');
    const checkbox = widget.kind === 'checkbox';
    input.type = checkbox ? 'checkbox' : 'text';
    const setValue = (value: WidgetDefinition['value']) => {
      if (checkbox) input.checked = value === true;
      else input.value = String(value);
    };
    setValue(widget.value);
    input.addEventListener('change', () => commit(checkbox ? input.checked : input.value));
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') input.blur();
    });
    element.append(input);
    return { element, setValue };
  }
}
