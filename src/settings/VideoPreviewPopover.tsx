import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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

interface PreviewSize {
  height: number;
  width: number;
}

function releaseVideo(video: HTMLVideoElement | null) {
  if (!video) return;
  video.pause();
  video.removeAttribute('src');
  video.load();
}

function fitPreview(
  sourceWidth: number,
  sourceHeight: number,
): PreviewSize | null {
  if (sourceWidth <= 0 || sourceHeight <= 0) return null;

  const mobile = window.innerWidth <= 560;
  const maxWidth = Math.max(
    1,
    mobile ? window.innerWidth - 32 : Math.min(420, window.innerWidth - 72),
  );
  const maxHeight = Math.max(1, window.innerHeight - (mobile ? 32 : 112));
  const scale = Math.min(maxWidth / sourceWidth, maxHeight / sourceHeight, 1);

  return {
    width: Math.floor(sourceWidth * scale),
    height: Math.floor(sourceHeight * scale),
  };
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
  const sourceSize = useRef<PreviewSize | null>(null);
  const [previewSize, setPreviewSize] = useState<PreviewSize | null>(null);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const failed = failedSource === source;

  const resizePreview = useCallback(() => {
    const size = sourceSize.current;
    if (!size) return;
    setPreviewSize(fitPreview(size.width, size.height));
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !source) return;
    setPreviewSize(null);
    sourceSize.current = null;
    video.src = source;
    video.load();
    void video.play().catch(() => undefined);
    return () => releaseVideo(video);
  }, [source]);

  useEffect(() => {
    window.addEventListener('resize', resizePreview);
    return () => window.removeEventListener('resize', resizePreview);
  }, [resizePreview]);

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
      style={previewSize ?? undefined}
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
            const size = fitPreview(videoWidth, videoHeight);
            if (!size) return;
            sourceSize.current = { width: videoWidth, height: videoHeight };
            setPreviewSize(size);
          }}
          onError={() => setFailedSource(source)}
        />
      )}
    </div>
  );
}
