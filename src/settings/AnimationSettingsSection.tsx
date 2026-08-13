import type { MediaRef, RestPlaybackMode } from '../shared/ipc';

export type MediaSlot = 'idle' | 'focus' | 'rest';

const sceneCopy: Record<
  MediaSlot,
  { detail: string; label: string; symbol: string }
> = {
  idle: { label: '等待', detail: '开始专注前显示', symbol: '○' },
  focus: { label: '专注', detail: '专注计时中显示', symbol: '●' },
  rest: { label: '休息', detail: '休息计时中显示', symbol: '☾' },
};

interface AnimationSettingsSectionProps {
  activeSlot: MediaSlot;
  media: MediaRef;
  options: MediaRef[];
  pending: boolean;
  restPlayback: RestPlaybackMode;
  mediaLabel(media: MediaRef): string;
  mediaValue(media: MediaRef): string;
  onActiveSlotChange(slot: MediaSlot): void;
  onOpenFolder(): void;
  onImport(): void;
  onPreview(trigger: HTMLButtonElement): void;
  onRestPlaybackChange(mode: RestPlaybackMode): void;
  onSelect(value: string): void;
}

function EyeIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M2.8 12s3.3-5.7 9.2-5.7S21.2 12 21.2 12 17.9 17.7 12 17.7 2.8 12 2.8 12Zm9.2 3.8a3.8 3.8 0 1 0 0-7.6 3.8 3.8 0 0 0 0 7.6Zm0-1.8a2 2 0 1 1 0-4 2 2 0 0 1 0 4Z" />
    </svg>
  );
}

function FolderIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M3.5 6.8A2.3 2.3 0 0 1 5.8 4.5h4l1.8 2h6.6a2.3 2.3 0 0 1 2.3 2.3v8.9a2.3 2.3 0 0 1-2.3 2.3H5.8a2.3 2.3 0 0 1-2.3-2.3V6.8Zm2.3-.5a.5.5 0 0 0-.5.5v1h13.4v-1a.5.5 0 0 0-.5-.5h-7.1l-1.8-2H5.8Zm-.5 3.3v8.1a.5.5 0 0 0 .5.5h12.4a.5.5 0 0 0 .5-.5V9.6H5.3Z" />
    </svg>
  );
}

function ImportIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M11 3.5h2v9.1l2.8-2.8 1.4 1.4-5.2 5.2-5.2-5.2 1.4-1.4 2.8 2.8V3.5ZM4.5 17h2v1.5h11V17h2v3.5H4.5V17Z" />
    </svg>
  );
}

export function AnimationSettingsSection({
  activeSlot,
  media,
  mediaLabel,
  mediaValue,
  onActiveSlotChange,
  onOpenFolder,
  onImport,
  onPreview,
  onRestPlaybackChange,
  onSelect,
  options,
  pending,
  restPlayback,
}: AnimationSettingsSectionProps) {
  const copy = sceneCopy[activeSlot];
  return (
    <section className="settings-section" aria-labelledby="animation-heading">
      <header className="settings-section__header">
        <div>
          <h2 id="animation-heading">动画</h2>
          <p>不同计时状态下显示的画面</p>
        </div>
        <div className="settings-section__actions">
          <button
            aria-label="打开媒体文件夹"
            className="settings-section__action"
            disabled={pending}
            title="打开媒体文件夹"
            type="button"
            onClick={onOpenFolder}
          >
            <FolderIcon />
          </button>
          <button
            aria-label="导入视频"
            className="settings-section__action settings-section__import"
            disabled={pending}
            title="导入视频"
            type="button"
            onClick={onImport}
          >
            <ImportIcon />
          </button>
        </div>
      </header>

      <fieldset aria-label="计时状态" className="scene-selector">
        {(Object.keys(sceneCopy) as MediaSlot[]).map((slot) => (
          <label className="scene-selector__option" key={slot}>
            <input
              checked={activeSlot === slot}
              name="animation-scene"
              type="radio"
              value={slot}
              onChange={() => onActiveSlotChange(slot)}
            />
            <span aria-hidden="true">{sceneCopy[slot].symbol}</span>
            {sceneCopy[slot].label}
          </label>
        ))}
      </fieldset>

      <div className="scene-editor" data-slot={activeSlot}>
        <div className="scene-editor__copy">
          <strong>{copy.label}</strong>
          <span>{copy.detail}</span>
        </div>
        <div className="scene-editor__control">
          <select
            aria-label={`${copy.label}视频`}
            disabled={pending}
            key={activeSlot}
            value={mediaValue(media)}
            onChange={(event) => onSelect(event.currentTarget.value)}
          >
            {options.map((item) => (
              <option key={mediaValue(item)} value={mediaValue(item)}>
                {mediaLabel(item)}
              </option>
            ))}
          </select>
          <button
            aria-label={`预览${copy.label}动画`}
            className="scene-editor__preview"
            disabled={pending}
            type="button"
            onClick={(event) => onPreview(event.currentTarget)}
          >
            <EyeIcon />
          </button>
        </div>
        {activeSlot === 'rest' && (
          <fieldset className="scene-editor__mode" aria-label="休息视频播放">
            {(['once', 'loop'] as const).map((mode) => (
              <button
                aria-pressed={restPlayback === mode}
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
      </div>
    </section>
  );
}
