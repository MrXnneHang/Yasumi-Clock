import { useState } from 'react';
import type { SessionPhase, TimerStatus } from '../../shared/ipc';

interface SessionAnimationProps {
  phase: SessionPhase | null;
  status: TimerStatus;
}

const fallbackImage = new URL('../../img/example.jpeg', import.meta.url).href;
const focusMedia = new URL('../../mp4/work.mp4', import.meta.url).href;
const breakMedia = new URL('../../mp4/play.mp4', import.meta.url).href;

export function SessionAnimation({ phase, status }: SessionAnimationProps) {
  const [failed, setFailed] = useState(false);
  const resting = phase === 'shortBreak' || phase === 'longBreak';
  const label = resting ? '休息动画' : '专注动画';

  if (failed) {
    return (
      <div
        className="session-animation__fallback"
        role="img"
        aria-label={`${label}不可用`}
      >
        <img src={fallbackImage} alt="Yasumi Clock 媒体回退" />
        <span>动画暂不可用，计时仍在继续。</span>
      </div>
    );
  }

  return (
    <video
      className="session-animation"
      aria-label={label}
      autoPlay={status === 'running'}
      loop
      muted
      playsInline
      poster={fallbackImage}
      src={resting ? breakMedia : focusMedia}
      onError={() => setFailed(true)}
    />
  );
}
