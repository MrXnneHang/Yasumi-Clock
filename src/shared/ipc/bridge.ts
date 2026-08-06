import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type { AppSettings, TimerMode, TimerSnapshot } from './types';

export const TIMER_SNAPSHOT_EVENT = 'timer://snapshot';

export interface DesktopTransport {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>;
  listen<T>(event: string, handler: (payload: T) => void): Promise<UnlistenFn>;
}

const tauriTransport: DesktopTransport = {
  invoke,
  listen: async <T>(event: string, handler: (payload: T) => void) =>
    listen<T>(event, ({ payload }) => handler(payload)),
};

export interface TimerSubscription {
  unsubscribe(): void;
}

export interface DesktopBridge {
  subscribeToTimer(
    onSnapshot: (snapshot: TimerSnapshot) => void,
  ): Promise<TimerSubscription>;
  startFocus(classicDurationOverrideMinutes?: number): Promise<TimerSnapshot>;
  pause(): Promise<TimerSnapshot>;
  resume(): Promise<TimerSnapshot>;
  reset(): Promise<TimerSnapshot>;
  dismissBreak(): Promise<TimerSnapshot>;
  adjustClassicDuration(deltaMinutes: number): Promise<TimerSnapshot>;
  selectMode(mode: TimerMode): Promise<TimerSnapshot>;
  getSettings(): Promise<AppSettings>;
  updateSettings(
    settings: AppSettings,
    expectedRevision: number,
  ): Promise<TimerSnapshot>;
}

export function createDesktopBridge(
  transport: DesktopTransport = tauriTransport,
): DesktopBridge {
  return {
    async subscribeToTimer(onSnapshot) {
      let latestRevision = -1;
      let active = true;
      const accept = (snapshot: TimerSnapshot) => {
        if (active && snapshot.revision >= latestRevision) {
          latestRevision = snapshot.revision;
          onSnapshot(snapshot);
        }
      };

      const unlisten = await transport.listen<TimerSnapshot>(
        TIMER_SNAPSHOT_EVENT,
        accept,
      );
      try {
        accept(await transport.invoke<TimerSnapshot>('get_timer_snapshot'));
      } catch (error) {
        active = false;
        unlisten();
        throw error;
      }

      return {
        unsubscribe() {
          active = false;
          unlisten();
        },
      };
    },
    startFocus(classicDurationOverrideMinutes) {
      return transport.invoke('start_focus_session', {
        classicDurationOverrideMinutes,
      });
    },
    pause() {
      return transport.invoke('pause_timer');
    },
    resume() {
      return transport.invoke('resume_timer');
    },
    reset() {
      return transport.invoke('reset_timer');
    },
    dismissBreak() {
      return transport.invoke('dismiss_rest_overlay');
    },
    adjustClassicDuration(deltaMinutes) {
      return transport.invoke('adjust_classic_focus_duration', {
        deltaMinutes,
      });
    },
    selectMode(mode) {
      return transport.invoke('select_timer_mode', { mode });
    },
    getSettings() {
      return transport.invoke('get_settings');
    },
    updateSettings(settings, expectedRevision) {
      return transport.invoke('update_settings', {
        settings,
        expectedRevision,
      });
    },
  };
}

export const desktopBridge = createDesktopBridge();
