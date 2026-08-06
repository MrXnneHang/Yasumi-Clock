import { useEffect, useState } from 'react';
import type {
  DesktopBridge,
  TimerAction,
  TimerSnapshot,
} from '../../shared/ipc';
import { ActionButton } from '../../shared/ui/ActionButton';
import { SessionAnimation } from './SessionAnimation';

interface TimerPanelProps {
  snapshot: TimerSnapshot;
  bridge: DesktopBridge;
  pending: boolean;
  run(command: () => Promise<TimerSnapshot>): Promise<void>;
}

const phaseLabels = {
  focus: '专注中',
  rest: '休息中',
} as const;

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${remainder
    .toString()
    .padStart(2, '0')}`;
}

function hasAction(snapshot: TimerSnapshot, action: TimerAction) {
  return snapshot.allowedActions.includes(action);
}

export function TimerPanel({
  snapshot,
  bridge,
  pending,
  run,
}: TimerPanelProps) {
  const adjustable = hasAction(snapshot, 'adjustFocusDuration');
  const [selectedMinutes, setSelectedMinutes] = useState(
    snapshot.focusDurationMinutes,
  );

  useEffect(() => {
    if (adjustable) {
      setSelectedMinutes(snapshot.focusDurationMinutes);
    }
  }, [adjustable, snapshot.focusDurationMinutes]);

  const phaseLabel = snapshot.phase
    ? phaseLabels[snapshot.phase]
    : snapshot.status === 'idle'
      ? '准备专注'
      : '计时器';
  const displayedSeconds = adjustable
    ? selectedMinutes * 60
    : snapshot.remainingSeconds;

  return (
    <section className="timer-panel" aria-labelledby="timer-heading">
      <div className="timer-panel__visual">
        <SessionAnimation phase={snapshot.phase} status={snapshot.status} />
        <div className="phase-badge">{phaseLabel}</div>
      </div>

      <div className="timer-panel__content">
        <h1 id="timer-heading">Yasumi Clock</h1>
        <output
          className="timer-display"
          aria-label={`剩余时间 ${formatTime(displayedSeconds)}`}
        >
          {formatTime(displayedSeconds)}
        </output>

        {adjustable && (
          <fieldset className="duration-control">
            <div className="duration-control__heading">
              <legend>专注时长</legend>
              <output htmlFor="focus-duration">{selectedMinutes} 分钟</output>
            </div>
            <input
              id="focus-duration"
              type="range"
              min="1"
              max="60"
              step="1"
              value={selectedMinutes}
              disabled={pending}
              aria-label="专注时长"
              aria-valuetext={`${selectedMinutes} 分钟`}
              onChange={(event) =>
                setSelectedMinutes(Number(event.currentTarget.value))
              }
            />
            <div className="duration-control__scale" aria-hidden="true">
              <span>1</span>
              <span>30</span>
              <span>60 分钟</span>
            </div>
          </fieldset>
        )}

        <div className="timer-actions">
          {hasAction(snapshot, 'startFocus') && (
            <ActionButton
              tone="primary"
              disabled={pending}
              onClick={() => run(() => bridge.startFocus(selectedMinutes))}
            >
              开始专注
            </ActionButton>
          )}
          {hasAction(snapshot, 'pause') && (
            <ActionButton
              disabled={pending}
              onClick={() => run(() => bridge.pause())}
            >
              暂停
            </ActionButton>
          )}
          {hasAction(snapshot, 'resume') && (
            <ActionButton
              tone="primary"
              disabled={pending}
              onClick={() => run(() => bridge.resume())}
            >
              继续
            </ActionButton>
          )}
          {hasAction(snapshot, 'end') && (
            <ActionButton
              tone="danger"
              disabled={pending}
              onClick={() => run(() => bridge.endTimer())}
            >
              {snapshot.phase === 'rest' ? '结束休息' : '结束专注'}
            </ActionButton>
          )}
        </div>
      </div>
    </section>
  );
}
