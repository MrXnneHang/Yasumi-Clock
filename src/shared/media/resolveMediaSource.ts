import type { MediaRef } from '../ipc';

const builtinMedia = {
  play: new URL('../../mp4/play.mp4', import.meta.url).href,
  work: new URL('../../mp4/work.mp4', import.meta.url).href,
  mayi: new URL('../../mp4/mayi.mp4', import.meta.url).href,
} as const;

interface TauriInternals {
  convertFileSrc(filePath: string, protocol: string): string;
}

export function resolveMediaSource(media: MediaRef): string {
  if (media.kind === 'builtin') {
    return builtinMedia[media.id];
  }
  return (
    (
      window as Window & { __TAURI_INTERNALS__?: TauriInternals }
    ).__TAURI_INTERNALS__?.convertFileSrc(media.id, 'yasumi-media') ?? ''
  );
}
