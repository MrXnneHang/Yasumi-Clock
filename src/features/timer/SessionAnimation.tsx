import { useState } from 'react';
import type { SessionPhase, TimerStatus } from '../../shared/ipc';

interface SessionAnimationProps {
  phase: SessionPhase | null;
  status: TimerStatus;
}

const fallbackImage = new URL('../../img/example.jpeg', import.meta.url).href;
const idleMedia = new URL('../../mp4/play.mp4', import.meta.url).href;
const focusMedia = new URL('../../mp4/work.mp4', import.meta.url).href;
const restMedia = new URL('../../img/mayi.gif', import.meta.url).href;

export function SessionAnimation({ phase, status }: SessionAnimationProps) {
  const [failed, setFailed] = useState(false);
  const resting = phase === 'rest';
  const focusing = phase === 'focus';
  const label = resting ? '休息动画' : focusing ? '专注动画' : '空闲动画';

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

  if (resting) {
    return (
      <img
        className="session-animation"
        src={restMedia}
        alt=""
        aria-label={label}
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <video
      className="session-animation"
      aria-label={label}
      autoPlay={!focusing || status === 'running'}
      loop
      muted
      playsInline
      src={focusing ? focusMedia : idleMedia}
      onError={() => setFailed(true)}
    />
  );
}
