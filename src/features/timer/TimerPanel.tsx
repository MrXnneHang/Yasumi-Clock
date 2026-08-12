import { useEffect, useState } from 'react';
import type {
  AnimationSettings,
  DesktopBridge,
  TimerAction,
  TimerSnapshot,
} from '../../shared/ipc';
import { ActionButton } from '../../shared/ui/ActionButton';
import { DurationDock } from './DurationDock';
import { formatDuration } from './duration';
import { SessionAnimation } from './SessionAnimation';
import { TimerActionIcon } from './TimerActionIcon';

interface TimerPanelProps {
  animations: AnimationSettings;
  bridge: DesktopBridge;
  error?: string;
  onClearError(): void;
  snapshot: TimerSnapshot;
  pending: boolean;
  run(
    command: () => Promise<TimerSnapshot>,
    options?: { transition?: boolean },
  ): Promise<void>;
}

const phaseLabels = {
  focus: '专注中',
  rest: '休息中',
} as const;

function hasAction(snapshot: TimerSnapshot, action: TimerAction) {
  return snapshot.allowedActions.includes(action);
}

export function TimerPanel({
  animations,
  bridge,
  error,
  onClearError,
  snapshot,
  pending,
  run,
}: TimerPanelProps) {
  const focusAdjustable = hasAction(snapshot, 'adjustFocusDuration');
  const [selectedFocusMinutes, setSelectedFocusMinutes] = useState(
    snapshot.focusDurationMinutes,
  );

  useEffect(() => {
    if (focusAdjustable) {
      setSelectedFocusMinutes(snapshot.focusDurationMinutes);
    }
  }, [focusAdjustable, snapshot.focusDurationMinutes]);

  const phaseLabel = snapshot.phase
    ? phaseLabels[snapshot.phase]
    : snapshot.status === 'idle'
      ? '准备专注'
      : '计时器';
  const endLabel = snapshot.phase === 'rest' ? '结束休息' : '结束专注';

  return (
    <section className="timer-panel" aria-label="专注计时器">
      <div className="timer-panel__visual">
        <SessionAnimation
          animations={animations}
          phase={snapshot.phase}
          status={snapshot.status}
        />
        <div className="phase-badge">{phaseLabel}</div>
      </div>

      <div className="timer-panel__content">
        <div className="timer-console">
          {focusAdjustable ? (
            <DurationDock
              minutes={selectedFocusMinutes}
              pending={pending}
              onChange={setSelectedFocusMinutes}
            />
          ) : (
            <div className="timer-console__display">
              <output
                aria-label={`剩余时间 ${formatDuration(snapshot.remainingSeconds)}`}
                className="timer-console__time"
              >
                {formatDuration(snapshot.remainingSeconds)}
              </output>
            </div>
          )}

          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button type="button" onClick={onClearError}>
                关闭
              </button>
            </div>
          )}

          <div className="timer-actions">
            {hasAction(snapshot, 'startFocus') && (
              <ActionButton
                aria-label="开始专注"
                className="timer-action-button"
                disabled={pending}
                title="开始专注"
                onClick={() =>
                  run(() => bridge.startFocus(selectedFocusMinutes), {
                    transition: true,
                  })
                }
              >
                <TimerActionIcon name="play" />
              </ActionButton>
            )}
            {hasAction(snapshot, 'pause') && (
              <ActionButton
                aria-label="暂停"
                className="timer-action-button"
                disabled={pending}
                title="暂停"
                onClick={() => run(() => bridge.pause(), { transition: true })}
              >
                <TimerActionIcon name="pause" />
              </ActionButton>
            )}
            {hasAction(snapshot, 'resume') && (
              <ActionButton
                aria-label="继续"
                className="timer-action-button"
                disabled={pending}
                title="继续"
                onClick={() => run(() => bridge.resume(), { transition: true })}
              >
                <TimerActionIcon name="play" />
              </ActionButton>
            )}
            {hasAction(snapshot, 'end') && (
              <ActionButton
                aria-label={endLabel}
                className="timer-action-button"
                disabled={pending}
                title={endLabel}
                onClick={() => run(() => bridge.endTimer(), { transition: true })}
              >
                <TimerActionIcon name="stop" />
              </ActionButton>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
