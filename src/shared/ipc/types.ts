export type TimerStatus = 'idle' | 'running' | 'paused';

export type SessionPhase = 'focus' | 'rest';

export type TimerAction =
  | 'startFocus'
  | 'startRest'
  | 'pause'
  | 'resume'
  | 'end'
  | 'adjustFocusDuration'
  | 'adjustRestDuration'
  | 'changeSettings';

export interface AppSettings {
  focusDurationMinutes: number;
  restDurationMinutes: number;
}

export interface TimerSnapshot {
  revision: number;
  status: TimerStatus;
  phase: SessionPhase | null;
  remainingSeconds: number;
  deadlineUtcSeconds: number | null;
  focusDurationMinutes: number;
  restDurationMinutes: number;
  dailyCompletedFocusCount: number;
  allowedActions: TimerAction[];
}

export interface CommandError {
  code: string;
  message: string;
  retryable: boolean;
}
