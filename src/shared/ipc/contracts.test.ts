import { describe, expect, it } from 'vitest';
import settingsFixture from '../../../contracts/app-settings.json';
import errorFixture from '../../../contracts/command-error.json';
import snapshotFixture from '../../../contracts/timer-snapshot.json';
import type { AppSettings, CommandError, TimerSnapshot } from './types';

describe('Rust IPC contract fixtures', () => {
  it('conforms to the mirrored TypeScript wire types', () => {
    const snapshot: TimerSnapshot = snapshotFixture as TimerSnapshot;
    const settings: AppSettings = settingsFixture as AppSettings;
    const error: CommandError = errorFixture;

    expect(snapshot.phase).toBe('focus');
    expect(snapshot.allowedActions).toEqual(['pause', 'end']);
    expect(snapshot.focusDurationMinutes).toBe(20);
    expect(settings).toEqual({
      focusDurationMinutes: 20,
      themeMode: 'system',
      animations: {
        idle: { kind: 'builtin', id: 'play' },
        focus: { kind: 'builtin', id: 'work' },
        rest: { kind: 'builtin', id: 'mayi' },
        restPlayback: 'once',
      },
    });
    expect(error.code).toBe('action_not_allowed');
  });
});
