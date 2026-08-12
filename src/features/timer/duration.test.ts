import { describe, expect, it } from 'vitest';
import {
  deriveRestDurationMinutes,
  focusDurationSeconds,
  formatDuration,
} from './duration';

describe('duration helpers', () => {
  it.each([
    [0, 5],
    [25, 5],
    [26, 6],
    [30, 6],
    [31, 7],
    [60, 12],
  ])('derives %i focus minutes into %i rest minutes', (focus, rest) => {
    expect(deriveRestDurationMinutes(focus)).toBe(rest);
  });

  it('maps zero minutes to a one-second focus session', () => {
    expect(focusDurationSeconds(0)).toBe(1);
    expect(formatDuration(focusDurationSeconds(0))).toBe('00:01');
  });

  it('rejects unsupported focus durations', () => {
    expect(() => focusDurationSeconds(-1)).toThrow(RangeError);
    expect(() => deriveRestDurationMinutes(61)).toThrow(RangeError);
    expect(() => deriveRestDurationMinutes(2.5)).toThrow(RangeError);
  });
});
