import type { UnlistenFn } from '@tauri-apps/api/event';
import { describe, expect, it, vi } from 'vitest';
import {
  createDesktopBridge,
  TIMER_SNAPSHOT_EVENT,
  type DesktopTransport,
} from './bridge';
import type { TimerSnapshot } from './types';

const snapshot = (revision: number): TimerSnapshot => ({
  revision,
  status: 'idle',
  phase: null,
  mode: { kind: 'classic' },
  remainingSeconds: 1_200,
  deadlineUtcSeconds: null,
  cycleFocusCount: 0,
  cycleTarget: null,
  dailyCompletedFocusCount: 0,
  nextPhase: 'focus',
  allowedActions: ['startFocus', 'adjustClassicDuration', 'changeSettings'],
});

const unlisten =
  (mock = vi.fn()): UnlistenFn =>
  () =>
    mock();

describe('desktop bridge', () => {
  it('registers the listener before requesting the initial snapshot', async () => {
    const calls: string[] = [];
    const unlistenMock = vi.fn();
    const transport: DesktopTransport = {
      listen: async <T>(event: string, handler: (payload: T) => void) => {
        calls.push(`listen:${event}`);
        handler(snapshot(2) as T);
        return unlisten(unlistenMock);
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
    expect(unlistenMock).toHaveBeenCalledOnce();
  });

  it('rejects stale events and stops delivering after unsubscribe', async () => {
    let eventHandler: ((value: TimerSnapshot) => void) | undefined;
    const transport: DesktopTransport = {
      listen: async <T>(_event: string, handler: (payload: T) => void) => {
        eventHandler = handler as (value: TimerSnapshot) => void;
        return unlisten();
      },
      invoke: async <T>() => snapshot(4) as T,
    };
    const received: number[] = [];
    const subscription = await createDesktopBridge(transport).subscribeToTimer(
      (value) => received.push(value.revision),
    );

    eventHandler?.(snapshot(3));
    eventHandler?.(snapshot(5));
    subscription.unsubscribe();
    eventHandler?.(snapshot(6));

    expect(received).toEqual([4, 5]);
  });

  it('cleans up the listener when initial snapshot loading fails', async () => {
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

  it('forwards typed command arguments to Tauri', async () => {
    const invokeMock = vi.fn();
    const transport: DesktopTransport = {
      listen: async () => unlisten(),
      invoke: async <T>(command: string, args?: Record<string, unknown>) => {
        invokeMock(command, args);
        return snapshot(1) as T;
      },
    };
    const bridge = createDesktopBridge(transport);

    await bridge.startFocus(25);
    await bridge.adjustClassicDuration(-5);
    await bridge.selectMode({ kind: 'preset', presetId: 'student' });

    expect(invokeMock).toHaveBeenNthCalledWith(1, 'start_focus_session', {
      classicDurationOverrideMinutes: 25,
    });
    expect(invokeMock).toHaveBeenNthCalledWith(
      2,
      'adjust_classic_focus_duration',
      { deltaMinutes: -5 },
    );
    expect(invokeMock).toHaveBeenNthCalledWith(3, 'select_timer_mode', {
      mode: { kind: 'preset', presetId: 'student' },
    });
  });
});
