import { useEffect, useMemo, useState } from 'react';
import type {
  AnimationSettings,
  MediaRef,
  SessionPhase,
  TimerStatus,
} from '../../shared/ipc';
import { defaultAnimationSettings } from './useAnimationSettings';

interface SessionAnimationProps {
  animations?: AnimationSettings;
  phase: SessionPhase | null;
  status: TimerStatus;
}

const fallbackImage = new URL('../../img/example.jpeg', import.meta.url).href;
const builtinMedia = {
  play: new URL('../../mp4/play.mp4', import.meta.url).href,
  work: new URL('../../mp4/work.mp4', import.meta.url).href,
  mayi: new URL('../../mp4/mayi.mp4', import.meta.url).href,
} as const;

interface TauriInternals {
  convertFileSrc(filePath: string, protocol: string): string;
}

function resolveMedia(media: MediaRef): string {
  if (media.kind === 'builtin') {
    return builtinMedia[media.id];
  }
  return (
    (
      window as Window & { __TAURI_INTERNALS__?: TauriInternals }
    ).__TAURI_INTERNALS__?.convertFileSrc(media.id, 'yasumi-media') ?? ''
  );
}

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
  const source = useMemo(() => resolveMedia(media), [media]);

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
