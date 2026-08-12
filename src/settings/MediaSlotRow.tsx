import type { AnimationSettings, MediaRef, RestPlaybackMode } from '../shared/ipc';

export type MediaSlot = 'idle' | 'focus' | 'rest';

interface MediaSlotRowProps {
  media: MediaRef;
  options: MediaRef[];
  pending: boolean;
  slot: MediaSlot;
  title: string;
  restPlayback?: RestPlaybackMode;
  mediaLabel(media: MediaRef): string;
  mediaValue(media: MediaRef): string;
  onPreview(slot: MediaSlot, trigger: HTMLButtonElement): void;
  onPreviewIntent(slot: MediaSlot): void;
  onPreviewLeave(): void;
  onRestPlaybackChange?(mode: RestPlaybackMode): void;
  onSelect(slot: MediaSlot, value: string): void;
}

function PreviewIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M8 5.5v13L18.5 12 8 5.5Z" />
    </svg>
  );
}

export function MediaSlotRow({
  media,
  mediaLabel,
  mediaValue,
  onPreview,
  onPreviewIntent,
  onPreviewLeave,
  onRestPlaybackChange,
  onSelect,
  options,
  pending,
  restPlayback,
  slot,
  title,
}: MediaSlotRowProps) {
  return (
    <fieldset
      className="media-slot-row"
      data-slot={slot}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          onPreviewLeave();
        }
      }}
      onFocus={() => onPreviewIntent(slot)}
      onMouseEnter={() => onPreviewIntent(slot)}
      onMouseLeave={onPreviewLeave}
    >
      <label className="media-slot-row__field">
        <strong>{title}</strong>
        <select
          aria-label={`${title}视频`}
          disabled={pending}
          value={mediaValue(media)}
          onChange={(event) => onSelect(slot, event.currentTarget.value)}
        >
          {options.map((item) => (
            <option key={mediaValue(item)} value={mediaValue(item)}>
              {mediaLabel(item)}
            </option>
          ))}
        </select>
      </label>
      <button
        aria-label={`预览${title}视频`}
        className="media-slot-row__preview"
        disabled={pending}
        type="button"
        onClick={(event) => onPreview(slot, event.currentTarget)}
      >
        <PreviewIcon />
      </button>
      {slot === 'rest' && restPlayback && onRestPlaybackChange && (
        <fieldset
          className="media-slot-row__mode"
          aria-label="休息视频播放"
        >
          {(['once', 'loop'] as const).map((mode) => (
            <button
              aria-pressed={restPlayback === mode}
              className="media-slot-row__mode-option"
              disabled={pending}
              key={mode}
              type="button"
              onClick={() => onRestPlaybackChange(mode)}
            >
              {mode === 'once' ? '单次' : '循环'}
            </button>
          ))}
        </fieldset>
      )}
    </fieldset>
  );
}

export function animationDraftEquals(
  first: AnimationSettings,
  second: AnimationSettings,
) {
  return JSON.stringify(first) === JSON.stringify(second);
}
