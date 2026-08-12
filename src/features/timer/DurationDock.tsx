import type { CSSProperties } from 'react';
import {
  deriveRestDurationMinutes,
  focusDurationSeconds,
  formatDuration,
} from './duration';

interface DurationDockProps {
  minutes: number;
  pending: boolean;
  onChange(minutes: number): void;
}

export function DurationDock({
  minutes,
  pending,
  onChange,
}: DurationDockProps) {
  const duration = formatDuration(focusDurationSeconds(minutes));
  const restMinutes = deriveRestDurationMinutes(minutes);
  const progress = `${(minutes / 60) * 100}%`;

  return (
    <section
      className="duration-dock timer-console__display"
      aria-label="本次专注时长"
    >
      <div className="duration-dock__meta">
        <span className="duration-dock__label">本次专注</span>
        <span>预计休息 {restMinutes} 分钟</span>
      </div>
      <output
        aria-label={`剩余时间 ${duration}`}
        className="timer-console__time"
      >
        {duration}
      </output>
      <input
        aria-label="本次专注时长"
        aria-valuetext={
          minutes === 0 ? '0 分钟，实际计时 1 秒' : `${minutes} 分钟`
        }
        disabled={pending}
        max="60"
        min="0"
        step="1"
        style={{ '--duration-progress': progress } as CSSProperties}
        type="range"
        value={minutes}
        onChange={(event) => onChange(Number(event.currentTarget.value))}
      />
      <div className="duration-dock__scale" aria-hidden="true">
        <span>{minutes === 0 ? '实际计时 1 秒' : '0'}</span>
        <span>30</span>
        <span>60</span>
      </div>
    </section>
  );
}
