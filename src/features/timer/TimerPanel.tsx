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
  shortBreak: '短休息',
  longBreak: '长休息',
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
  const classic = snapshot.mode.kind === 'classic';
  const phaseLabel = snapshot.phase
    ? phaseLabels[snapshot.phase]
    : snapshot.status === 'idle'
      ? '准备专注'
      : '计时器';

  return (
    <section className="timer-panel" aria-labelledby="timer-heading">
      <div className="timer-panel__visual">
        <SessionAnimation phase={snapshot.phase} status={snapshot.status} />
        <div className="phase-badge">{phaseLabel}</div>
      </div>

      <div className="timer-panel__content">
        <p className="eyebrow">{classic ? 'CLASSIC FOCUS' : 'FOCUS PRESET'}</p>
        <h1 id="timer-heading">Yasumi Clock</h1>
        <output
          className="timer-display"
          aria-label={`剩余时间 ${formatTime(snapshot.remainingSeconds)}`}
        >
          {formatTime(snapshot.remainingSeconds)}
        </output>

        <dl className="timer-stats">
          <div>
            <dt>本轮进度</dt>
            <dd>
              {snapshot.cycleFocusCount}
              {snapshot.cycleTarget ? ` / ${snapshot.cycleTarget}` : ''}
            </dd>
          </div>
          <div>
            <dt>今日完成</dt>
            <dd>{snapshot.dailyCompletedFocusCount}</dd>
          </div>
          <div>
            <dt>下一阶段</dt>
            <dd>
              {snapshot.nextPhase ? phaseLabels[snapshot.nextPhase] : '待命'}
            </dd>
          </div>
        </dl>

        {classic && hasAction(snapshot, 'adjustClassicDuration') && (
          <fieldset className="duration-controls">
            <legend className="sr-only">经典模式时长</legend>
            <ActionButton
              aria-label="减少五分钟"
              disabled={pending || snapshot.remainingSeconds <= 5 * 60}
              onClick={() => run(() => bridge.adjustClassicDuration(-5))}
            >
              −5
            </ActionButton>
            <span>{snapshot.remainingSeconds / 60} 分钟</span>
            <ActionButton
              aria-label="增加五分钟"
              disabled={pending || snapshot.remainingSeconds >= 40 * 60}
              onClick={() => run(() => bridge.adjustClassicDuration(5))}
            >
              +5
            </ActionButton>
          </fieldset>
        )}

        <div className="timer-actions">
          {hasAction(snapshot, 'startFocus') && (
            <ActionButton
              tone="primary"
              disabled={pending}
              onClick={() => run(() => bridge.startFocus())}
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
          {hasAction(snapshot, 'dismissBreak') && (
            <ActionButton
              disabled={pending}
              onClick={() => run(() => bridge.dismissBreak())}
            >
              结束休息
            </ActionButton>
          )}
          {hasAction(snapshot, 'reset') && (
            <ActionButton
              tone="danger"
              disabled={pending}
              onClick={() => run(() => bridge.reset())}
            >
              重置
            </ActionButton>
          )}
        </div>
      </div>
    </section>
  );
}
