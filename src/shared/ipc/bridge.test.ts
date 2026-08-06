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
  remainingSeconds: 1_200,
  deadlineUtcSeconds: null,
  focusDurationMinutes: 20,
  restDurationMinutes: 5,
  dailyCompletedFocusCount: 0,
  allowedActions: [
    'startFocus',
    'startRest',
    'adjustFocusDuration',
    'adjustRestDuration',
    'changeSettings',
  ],
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

  it('forwards on-demand timer command arguments to Tauri', async () => {
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
    await bridge.startRest(15);
    await bridge.endTimer();
    await bridge.adjustFocusDuration(-5);
    await bridge.adjustRestDuration(5);

    expect(invokeMock).toHaveBeenNthCalledWith(1, 'start_focus_session', {
      durationOverrideMinutes: 25,
    });
    expect(invokeMock).toHaveBeenNthCalledWith(2, 'start_rest_session', {
      durationOverrideMinutes: 15,
    });
    expect(invokeMock).toHaveBeenNthCalledWith(3, 'end_timer', undefined);
    expect(invokeMock).toHaveBeenNthCalledWith(4, 'adjust_focus_duration', {
      deltaMinutes: -5,
    });
    expect(invokeMock).toHaveBeenNthCalledWith(5, 'adjust_rest_duration', {
      deltaMinutes: 5,
    });
  });
});
