export type TimerStatus = 'idle' | 'running' | 'paused';

export type SessionPhase = 'focus' | 'rest';

export type TimerAction =
  | 'startFocus'
  | 'pause'
  | 'resume'
  | 'end'
  | 'adjustFocusDuration'
  | 'changeSettings';

export type BuiltinMediaId = 'play' | 'work' | 'mayi';

export type MediaRef =
  | { kind: 'builtin'; id: BuiltinMediaId }
  | { kind: 'imported'; id: string };

export type RestPlaybackMode = 'once' | 'loop';

export interface AnimationSettings {
  idle: MediaRef;
  focus: MediaRef;
  rest: MediaRef;
  restPlayback: RestPlaybackMode;
}

export interface AppSettings {
  focusDurationMinutes: number;
  animations: AnimationSettings;
}

export interface SettingsState {
  settings: AppSettings;
  revision: number;
}

export interface TimerSnapshot {
  revision: number;
  status: TimerStatus;
  phase: SessionPhase | null;
  remainingSeconds: number;
  deadlineUtcSeconds: number | null;
  focusDurationMinutes: number;
  dailyCompletedFocusCount: number;
  allowedActions: TimerAction[];
}

export interface CommandError {
  code: string;
  message: string;
  retryable: boolean;
}
