import { useEffect, useMemo, useState } from 'react';
import type {
  AnimationSettings,
  SessionPhase,
  TimerStatus,
} from '../../shared/ipc';
import { resolveMediaSource } from '../../shared/media/resolveMediaSource';
import { defaultAnimationSettings } from './useAnimationSettings';

interface SessionAnimationProps {
  animations?: AnimationSettings;
  phase: SessionPhase | null;
  status: TimerStatus;
}

const fallbackImage = new URL('../../img/example.jpeg', import.meta.url).href;

export function SessionAnimation({
  animations = defaultAnimationSettings,
  phase,
  status,
}: SessionAnimationProps) {
  const [failed, setFailed] = useState(false);
  const resting = phase === 'rest';
  const focusing = phase === 'focus';
  const label = resting ? '休息动画' : focusing ? '专注动画' : '空闲动画';
  const media = resting
    ? animations.rest
    : focusing
      ? animations.focus
      : animations.idle;
  const source = useMemo(() => resolveMediaSource(media), [media]);

  useEffect(() => {
    if (source) {
      setFailed(false);
    }
  }, [source]);

  if (failed || !source) {
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
      autoPlay={!focusing || status === 'running'}
      loop={resting ? animations.restPlayback === 'loop' : true}
      muted
      playsInline
      src={source}
      onError={() => setFailed(true)}
    />
  );
}
