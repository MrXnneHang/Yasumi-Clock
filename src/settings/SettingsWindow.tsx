import { useEffect, useMemo, useState } from 'react';
import {
  desktopBridge,
  type AppSettings,
  type DesktopBridge,
  type MediaRef,
  type RestPlaybackMode,
  type ThemeMode,
} from '../shared/ipc';
import { applyThemeMode, useThemeMode } from '../shared/theme/useThemeMode';

const builtins = {
  idle: { kind: 'builtin', id: 'play' },
  focus: { kind: 'builtin', id: 'work' },
  rest: { kind: 'builtin', id: 'mayi' },
} as const satisfies Record<string, MediaRef>;

type Slot = keyof typeof builtins;

const slotCopy: Record<Slot, { detail: string; title: string }> = {
  idle: { title: '空闲视频', detail: '等待开始时播放' },
  focus: { title: '专注视频', detail: '专注计时中播放' },
  rest: { title: '休息视频', detail: '休息时播放' },
};

const builtinSources = {
  play: new URL('../mp4/play.mp4', import.meta.url).href,
  work: new URL('../mp4/work.mp4', import.meta.url).href,
  mayi: new URL('../mp4/mayi.mp4', import.meta.url).href,
} as const;

const focusDurations = Array.from({ length: 61 }, (_, index) => index);

function mediaValue(media: MediaRef): string {
  return `${media.kind}:${media.id}`;
}

function mediaLabel(media: MediaRef): string {
  return media.kind === 'builtin'
    ? '内置视频'
    : `已导入 · ${media.id.slice(0, 8)}`;
}

function decodeMedia(value: string, media: MediaRef[]): MediaRef | undefined {
  return [...Object.values(builtins), ...media].find(
    (candidate) => mediaValue(candidate) === value,
  );
}

interface TauriInternals {
  convertFileSrc(filePath: string, protocol: string): string;
}

function previewSource(media: MediaRef): string {
  if (media.kind === 'builtin') {
    return builtinSources[media.id];
  }
  return (
    (
      window as Window & { __TAURI_INTERNALS__?: TauriInternals }
    ).__TAURI_INTERNALS__?.convertFileSrc(media.id, 'yasumi-media') ?? ''
  );
}

function message(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return String(error.message);
  }
  return '视频设置暂时无法完成。';
}

interface SettingsWindowProps {
  bridge?: DesktopBridge;
}

export function SettingsWindow({
  bridge = desktopBridge,
}: SettingsWindowProps) {
  useThemeMode(bridge);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [media, setMedia] = useState<MediaRef[]>([]);
  const [revision, setRevision] = useState(-1);
  const [slot, setSlot] = useState<Slot>('idle');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let unsubscribe: () => void = () => undefined;
    Promise.all([
      bridge.subscribeToSettings((state) => {
        if (mounted) {
          setSettings(state.settings);
          setRevision(state.revision);
        }
      }),
      bridge.listImportedMedia(),
    ])
      .then(([subscription, imported]) => {
        unsubscribe = subscription.unsubscribe;
        if (mounted) {
          setMedia(imported);
        }
      })
      .catch((cause) => {
        if (mounted) {
          setError(message(cause));
        }
      });

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, [bridge]);

  const selected = settings?.animations[slot];
  const preview = selected ? previewSource(selected) : '';
  const restPlayback = settings?.animations.restPlayback ?? 'once';

  const select = (nextSlot: Slot, value: string) => {
    const nextMedia = decodeMedia(value, media);
    if (!nextMedia) {
      return;
    }
    setSlot(nextSlot);
    setSettings((current) =>
      current
        ? {
            ...current,
            animations: { ...current.animations, [nextSlot]: nextMedia },
          }
        : current,
    );
  };

  const setRestPlayback = (next: RestPlaybackMode) => {
    setSettings((current) =>
      current
        ? {
            ...current,
            animations: { ...current.animations, restPlayback: next },
          }
        : current,
    );
  };

  const setThemeMode = (themeMode: ThemeMode) => {
    applyThemeMode(themeMode);
    setSettings((current) =>
      current
        ? {
            ...current,
            themeMode,
          }
        : current,
    );
  };

  const importVideo = async () => {
    setPending(true);
    setError(null);
    try {
      const imported = await bridge.importAnimationMedia();
      if (!imported) {
        return;
      }
      setMedia((current) => [...current, imported]);
      setSettings((current) =>
        current
          ? {
              ...current,
              animations: { ...current.animations, [slot]: imported },
            }
          : current,
      );
    } catch (cause) {
      setError(message(cause));
    } finally {
      setPending(false);
    }
  };

  const save = async () => {
    if (!settings || revision < 0) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const snapshot = await bridge.updateSettings(settings, revision);
      setRevision(snapshot.revision);
    } catch (cause) {
      if (
        typeof cause === 'object' &&
        cause !== null &&
        'code' in cause &&
        cause.code === 'stale_revision'
      ) {
        try {
          const current = await bridge.getSettingsState();
          applyThemeMode(current.settings.themeMode);
          setSettings(current.settings);
          setRevision(current.revision);
          setError('设置已在其他窗口更新，已载入最新配置。');
        } catch (reloadCause) {
          setError(message(reloadCause));
        }
      } else {
        setError(message(cause));
      }
    } finally {
      setPending(false);
    }
  };

  const options = useMemo(
    () => [...Object.values(builtins), ...media],
    [media],
  );

  if (!settings || !selected) {
    return (
      <main className="settings-window settings-window--loading">
        {error ? (
          <p role="alert">{error}</p>
        ) : (
          <p role="status">正在读取视频库…</p>
        )}
      </main>
    );
  }

  return (
    <main className="settings-window" aria-labelledby="settings-heading">
      <header className="settings-window__header">
        <div>
          <p>Yasumi Clock · 视频库</p>
          <h1 id="settings-heading">选择每个状态的画面</h1>
        </div>
        <button disabled={pending} onClick={importVideo} type="button">
          导入视频
        </button>
      </header>

      <div className="settings-window__layout">
        <section className="video-selectors" aria-label="视频选择">
          <label className="focus-duration-selector">
            <span>
              <strong>专注时长</strong>
              <small>0 分钟将用于 1 秒的快速验证</small>
            </span>
            <select
              aria-label="专注时长"
              value={settings.focusDurationMinutes}
              onChange={(event) =>
                setSettings((current) =>
                  current
                    ? {
                        ...current,
                        focusDurationMinutes: Number(event.currentTarget.value),
                      }
                    : current,
                )
              }
            >
              {focusDurations.map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes} 分钟
                </option>
              ))}
            </select>
          </label>

          {(Object.keys(slotCopy) as Slot[]).map((currentSlot) => (
            <label key={currentSlot} className="video-selector">
              <span>
                <strong>{slotCopy[currentSlot].title}</strong>
                <small>{slotCopy[currentSlot].detail}</small>
              </span>
              <select
                aria-label={slotCopy[currentSlot].title}
                value={mediaValue(settings.animations[currentSlot])}
                onChange={(event) =>
                  select(currentSlot, event.currentTarget.value)
                }
              >
                {options.map((item) => (
                  <option key={mediaValue(item)} value={mediaValue(item)}>
                    {mediaLabel(item)}
                  </option>
                ))}
              </select>
            </label>
          ))}

          <fieldset className="appearance-mode" disabled={pending}>
            <legend>外观</legend>
            {(
              [
                ['system', '跟随系统'],
                ['light', '浅色'],
                ['dark', '深色'],
              ] as const
            ).map(([mode, label]) => (
              <label key={mode}>
                <input
                  checked={settings.themeMode === mode}
                  name="theme-mode"
                  type="radio"
                  onChange={() => setThemeMode(mode)}
                />
                {label}
              </label>
            ))}
          </fieldset>

          <fieldset className="rest-mode" disabled={pending}>
            <legend>休息视频播放</legend>
            <label>
              <input
                checked={restPlayback === 'once'}
                name="rest-playback"
                type="radio"
                onChange={() => setRestPlayback('once')}
              />
              播放一次
            </label>
            <label>
              <input
                checked={restPlayback === 'loop'}
                name="rest-playback"
                type="radio"
                onChange={() => setRestPlayback('loop')}
              />
              循环播放
            </label>
          </fieldset>
        </section>

        <section className="video-preview" aria-labelledby="preview-heading">
          <div className="video-preview__heading">
            <span>预览</span>
            <h2 id="preview-heading">{slotCopy[slot].title}</h2>
          </div>
          <video
            aria-label={`${slotCopy[slot].title}预览`}
            controls
            key={preview}
            loop={slot === 'rest' && restPlayback === 'loop'}
            muted
            playsInline
            src={preview}
          />
          <p>{mediaLabel(selected)}</p>
        </section>
      </div>

      {error && (
        <p className="settings-window__error" role="alert">
          {error}
        </p>
      )}
      <footer className="settings-window__footer">
        <span>导入的视频可用于空闲、专注和休息。</span>
        <button disabled={pending} onClick={save} type="button">
          保存设置
        </button>
      </footer>
    </main>
  );
}
