export type TimerStatus = 'idle' | 'running' | 'paused';

export type SessionPhase = 'focus' | 'rest';

export type TimerAction =
  | 'startFocus'
  | 'pause'
  | 'resume'
  | 'end'
  | 'adjustFocusDuration'
  | 'changeSettings';

export interface AppSettings {
  focusDurationMinutes: number;
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
