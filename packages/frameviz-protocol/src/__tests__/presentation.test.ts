import { describe, expect, it } from 'vitest';
import { validateCommandArgs } from '../commandValidation';

describe('browser presentation command', () => {
  it('accepts an opaque browser label and destination view', () => {
    expect(validateCommandArgs('present_view', { browser_session: 'sdk_123-ABC', view_id: 'v_2' }).ok).toBe(true);
  });
  it.each(['', 'has spaces', 'x'.repeat(129), '视图'])('rejects invalid labels %s', browser_session => {
    expect(validateCommandArgs('present_view', { browser_session, view_id: 'v_2' }).ok).toBe(false);
  });
  it('rejects a missing or nonstring view and unknown fields', () => {
    for (const args of [{ browser_session: 'sdk' }, { browser_session: 'sdk', view_id: 7 },
      { browser_session: 'sdk', view_id: 'v_2', scene_id: 'other' }]) {
      expect(validateCommandArgs('present_view', args).ok).toBe(false);
    }
  });
});
