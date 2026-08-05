export type TimerStatus = 'idle' | 'running' | 'paused';

export type SessionPhase = 'focus' | 'shortBreak' | 'longBreak';

export type TimerMode =
  | { kind: 'classic' }
  | { kind: 'preset'; presetId: string };

export type TimerAction =
  | 'startFocus'
  | 'pause'
  | 'resume'
  | 'reset'
  | 'dismissBreak'
  | 'adjustClassicDuration'
  | 'changeSettings';

export type FocusDurationPlan =
  | { kind: 'fixed'; minutes: number }
  | { kind: 'sequence'; minutes: number[] };

export interface Preset {
  id: string;
  name: string;
  focusDuration: FocusDurationPlan;
  shortBreakMinutes: number;
  longBreakMinutes: number;
  cyclesBeforeLongBreak: number;
  forceRest: boolean;
}

export interface AppSettings {
  presets: Record<string, Preset>;
}

export interface TimerSnapshot {
  revision: number;
  status: TimerStatus;
  phase: SessionPhase | null;
  mode: TimerMode;
  remainingSeconds: number;
  deadlineUtcSeconds: number | null;
  cycleFocusCount: number;
  cycleTarget: number | null;
  dailyCompletedFocusCount: number;
  nextPhase: SessionPhase | null;
  allowedActions: TimerAction[];
}

export interface CommandError {
  code: string;
  message: string;
  retryable: boolean;
}
