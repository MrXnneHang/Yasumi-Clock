import { useEffect, useMemo, useRef, useState } from 'react';
import type { MediaRef } from '../shared/ipc';
import { resolveMediaSource } from '../shared/media/resolveMediaSource';
import type { MediaSlot } from './AnimationSettingsSection';

interface VideoPreviewPopoverProps {
  media: MediaRef;
  slot: MediaSlot;
  title: string;
  onClose(): void;
  onMouseLeave(): void;
}

function releaseVideo(video: HTMLVideoElement | null) {
  if (!video) return;
  video.pause();
  video.removeAttribute('src');
  video.load();
}

export function VideoPreviewPopover({
  media,
  onClose,
  onMouseLeave,
  slot,
  title,
}: VideoPreviewPopoverProps) {
  const source = useMemo(() => resolveMediaSource(media), [media]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [aspectRatio, setAspectRatio] = useState('16 / 9');
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const failed = failedSource === source;

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !source) return;
    video.src = source;
    video.load();
    void video.play().catch(() => undefined);
    return () => releaseVideo(video);
  }, [source]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);

  return (
    <div
      aria-label={`${title}视频预览`}
      className="video-preview-popover"
      data-slot={slot}
      role="dialog"
      style={{ aspectRatio }}
      onMouseLeave={onMouseLeave}
    >
      {failed || !source ? (
        <div className="video-preview-popover__fallback" role="status">
          视频暂不可用
        </div>
      ) : (
        <video
          aria-label={`${title}视频预览`}
          controls
          muted
          playsInline
          preload="metadata"
          ref={videoRef}
          onLoadedMetadata={(event) => {
            const { videoHeight, videoWidth } = event.currentTarget;
            if (videoHeight > 0 && videoWidth > 0) {
              setAspectRatio(`${videoWidth} / ${videoHeight}`);
            }
          }}
          onError={() => setFailedSource(source)}
        />
      )}
    </div>
  );
}
