import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type {
  AppSettings,
  MediaRef,
  SettingsState,
  ThemeMode,
  TimerSnapshot,
} from './types';

export const TIMER_SNAPSHOT_EVENT = 'timer://snapshot';
export const SETTINGS_CHANGED_EVENT = 'settings://changed';
export const MEDIA_LIBRARY_CHANGED_EVENT = 'media://library-changed';

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

export interface MediaLibraryState {
  imported: MediaRef[];
  unavailableIds: string[];
}

export interface DesktopBridge {
  subscribeToTimer(
    onSnapshot: (snapshot: TimerSnapshot) => void,
  ): Promise<TimerSubscription>;
  subscribeToSettings(
    onSettings: (state: SettingsState) => void,
  ): Promise<TimerSubscription>;
  subscribeToMediaLibrary(
    onChange: (state: MediaLibraryState) => void,
  ): Promise<TimerSubscription>;
  startFocus(
    durationOverrideMinutes?: number,
    workItemId?: string,
  ): Promise<TimerSnapshot>;
  pause(): Promise<TimerSnapshot>;
  resume(): Promise<TimerSnapshot>;
  endTimer(): Promise<TimerSnapshot>;
  endRest(): Promise<TimerSnapshot>;
  adjustFocusDuration(deltaMinutes: number): Promise<TimerSnapshot>;
  getSettings(): Promise<AppSettings>;
  getSettingsState(): Promise<SettingsState>;
  listImportedMedia(): Promise<MediaRef[]>;
  openMediaFolder(): Promise<void>;
  importAnimationMedia(): Promise<MediaRef | null>;
  openSettings(): Promise<void>;
  setThemeMode(mode: ThemeMode): Promise<SettingsState>;
  updateSettings(
    settings: AppSettings,
    expectedRevision: number,
  ): Promise<TimerSnapshot>;
}

function subscription<T>(
  event: string,
  getInitial: () => Promise<T>,
  transport: DesktopTransport,
  acceptPayload: (value: T) => void,
): Promise<TimerSubscription> {
  let active = true;
  return transport
    .listen<T>(event, (value) => {
      if (active) {
        acceptPayload(value);
      }
    })
    .then(async (unlisten) => {
      try {
        acceptPayload(await getInitial());
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
    });
}

export function createDesktopBridge(
  transport: DesktopTransport = tauriTransport,
): DesktopBridge {
  return {
    async subscribeToTimer(onSnapshot) {
      let latestRevision = -1;
      return subscription(
        TIMER_SNAPSHOT_EVENT,
        () => transport.invoke<TimerSnapshot>('get_timer_snapshot'),
        transport,
        (snapshot) => {
          if (snapshot.revision >= latestRevision) {
            latestRevision = snapshot.revision;
            onSnapshot(snapshot);
          }
        },
      );
    },
    async subscribeToSettings(onSettings) {
      let latestRevision = -1;
      return subscription(
        SETTINGS_CHANGED_EVENT,
        () => transport.invoke<SettingsState>('get_settings_state'),
        transport,
        (state) => {
          if (state.revision >= latestRevision) {
            latestRevision = state.revision;
            onSettings(state);
          }
        },
      );
    },
    async subscribeToMediaLibrary(onChange) {
      return subscription(
        MEDIA_LIBRARY_CHANGED_EVENT,
        async () => ({
          imported: await transport.invoke<MediaRef[]>('list_imported_media'),
          unavailableIds: [],
        }),
        transport,
        onChange,
      );
    },
    startFocus(durationOverrideMinutes, workItemId) {
      return transport.invoke('start_focus_session', {
        durationOverrideMinutes,
        workItemId,
      });
    },
    pause() {
      return transport.invoke('pause_timer');
    },
    resume() {
      return transport.invoke('resume_timer');
    },
    endTimer() {
      return transport.invoke('end_timer');
    },
    endRest() {
      return transport.invoke('end_rest');
    },
    adjustFocusDuration(deltaMinutes) {
      return transport.invoke('adjust_focus_duration', { deltaMinutes });
    },
    getSettings() {
      return transport.invoke('get_settings');
    },
    getSettingsState() {
      return transport.invoke('get_settings_state');
    },
    listImportedMedia() {
      return transport.invoke('list_imported_media');
    },
    openMediaFolder() {
      return transport.invoke('open_media_folder');
    },
    importAnimationMedia() {
      return transport.invoke('import_animation_media');
    },
    openSettings() {
      return transport.invoke('open_settings_window');
    },
    setThemeMode(themeMode) {
      return transport.invoke('set_theme_mode', { themeMode });
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
