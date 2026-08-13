import type { UnlistenFn } from '@tauri-apps/api/event';
import { describe, expect, it, vi } from 'vitest';
import {
  createDesktopBridge,
  SETTINGS_CHANGED_EVENT,
  TIMER_SNAPSHOT_EVENT,
  type DesktopTransport,
} from './bridge';
import type { SettingsState, TimerSnapshot } from './types';

const snapshot = (revision: number): TimerSnapshot => ({
  revision,
  status: 'idle',
  phase: null,
  remainingSeconds: 1_200,
  deadlineUtcSeconds: null,
  focusDurationMinutes: 20,
  dailyCompletedFocusCount: 0,
  allowedActions: ['startFocus', 'adjustFocusDuration', 'changeSettings'],
});

const settingsState = (revision: number): SettingsState => ({
  revision,
  settings: {
    focusDurationMinutes: 20,
    themeMode: 'system',
    animations: {
      idle: { kind: 'builtin', id: 'play' },
      focus: { kind: 'builtin', id: 'work' },
      rest: { kind: 'builtin', id: 'mayi' },
      restPlayback: 'once',
    },
  },
});

const unlisten =
  (mock = vi.fn()): UnlistenFn =>
  () =>
    mock();

describe('desktop bridge', () => {
  it('registers the timer listener before requesting the initial snapshot', async () => {
    const calls: string[] = [];
    const transport: DesktopTransport = {
      listen: async <T>(event: string, handler: (payload: T) => void) => {
        calls.push(`listen:${event}`);
        handler(snapshot(2) as T);
        return unlisten();
      },
      invoke: async <T>(command: string) => {
        calls.push(`invoke:${command}`);
        return snapshot(1) as T;
      },
    };
    const received: number[] = [];

    const subscription = await createDesktopBridge(transport).subscribeToTimer(
      (value) => received.push(value.revision),
    );

    expect(calls).toEqual([
      `listen:${TIMER_SNAPSHOT_EVENT}`,
      'invoke:get_timer_snapshot',
    ]);
    expect(received).toEqual([2]);
    subscription.unsubscribe();
  });

  it('delivers settings only at or above the latest revision', async () => {
    let handler: ((value: SettingsState) => void) | undefined;
    const transport: DesktopTransport = {
      listen: async <T>(_event: string, next: (payload: T) => void) => {
        handler = next as (value: SettingsState) => void;
        return unlisten();
      },
      invoke: async <T>() => settingsState(4) as T,
    };
    const received: number[] = [];

    const subscription = await createDesktopBridge(
      transport,
    ).subscribeToSettings((value) => received.push(value.revision));
    handler?.(settingsState(3));
    handler?.(settingsState(5));
    subscription.unsubscribe();
    handler?.(settingsState(6));

    expect(received).toEqual([4, 5]);
  });

  it('cleans up the listener when initial loading fails', async () => {
    const unlistenMock = vi.fn();
    const failure = new Error('snapshot unavailable');
    const transport: DesktopTransport = {
      listen: async () => unlisten(unlistenMock),
      invoke: async () => {
        throw failure;
      },
    };

    await expect(
      createDesktopBridge(transport).subscribeToTimer(vi.fn()),
    ).rejects.toBe(failure);
    expect(unlistenMock).toHaveBeenCalledOnce();
  });

  it('forwards timer, media, and settings-window commands to Tauri', async () => {
    const invokeMock = vi.fn();
    const transport: DesktopTransport = {
      listen: async () => unlisten(),
      invoke: async <T>(command: string, args?: Record<string, unknown>) => {
        invokeMock(command, args);
        return snapshot(1) as T;
      },
    };
    const bridge = createDesktopBridge(transport);

    await bridge.startFocus(25, 'todo-42');
    await bridge.endTimer();
    await bridge.endRest();
    await bridge.adjustFocusDuration(-5);
    await bridge.listImportedMedia();
    await bridge.importAnimationMedia();
    await bridge.openSettings();
    await bridge.setThemeMode('dark');

    expect(invokeMock).toHaveBeenNthCalledWith(1, 'start_focus_session', {
      durationOverrideMinutes: 25,
      workItemId: 'todo-42',
    });
    expect(invokeMock).toHaveBeenNthCalledWith(2, 'end_timer', undefined);
    expect(invokeMock).toHaveBeenNthCalledWith(3, 'end_rest', undefined);
    expect(invokeMock).toHaveBeenNthCalledWith(4, 'adjust_focus_duration', {
      deltaMinutes: -5,
    });
    expect(invokeMock).toHaveBeenNthCalledWith(
      5,
      'list_imported_media',
      undefined,
    );
    expect(invokeMock).toHaveBeenNthCalledWith(
      6,
      'import_animation_media',
      undefined,
    );
    expect(invokeMock).toHaveBeenNthCalledWith(
      7,
      'open_settings_window',
      undefined,
    );
    expect(invokeMock).toHaveBeenNthCalledWith(8, 'set_theme_mode', {
      themeMode: 'dark',
    });
  });

  it('uses the settings event name for settings subscriptions', async () => {
    const listenMock = vi.fn(async () => unlisten());
    const transport: DesktopTransport = {
      listen: listenMock,
      invoke: async <T>() => settingsState(1) as T,
    };

    await createDesktopBridge(transport).subscribeToSettings(vi.fn());

    expect(listenMock).toHaveBeenCalledWith(
      SETTINGS_CHANGED_EVENT,
      expect.any(Function),
    );
  });
});
