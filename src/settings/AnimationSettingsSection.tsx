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

export function AnimationSettingsSection({
  activeSlot,
  media,
  mediaLabel,
  mediaValue,
  onActiveSlotChange,
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
        <button
          className="settings-section__import"
          disabled={pending}
          type="button"
          onClick={onImport}
        >
          ＋ 导入视频
        </button>
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
