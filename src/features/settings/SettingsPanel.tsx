import { useEffect, useState } from 'react';
import type {
  AnimationSettings,
  AnimationSlot,
  AppSettings,
  CommandError,
  DesktopBridge,
  MediaRef,
  TimerSnapshot,
} from '../../shared/ipc';
import { ActionButton } from '../../shared/ui/ActionButton';

interface SettingsPanelProps {
  bridge: DesktopBridge;
  onSaved(animations: AnimationSettings): void;
  snapshot: TimerSnapshot;
}

const builtinMedia: Record<AnimationSlot, MediaRef> = {
  idle: { kind: 'builtin', id: 'play' },
  focus: { kind: 'builtin', id: 'work' },
  rest: { kind: 'builtin', id: 'mayi' },
};

const slotDetails: Record<
  AnimationSlot,
  { description: string; title: string }
> = {
  idle: { title: '空闲', description: '未开始专注时播放' },
  focus: { title: '专注', description: '专注计时中播放' },
  rest: { title: '休息', description: '休息遮罩中播放' },
};

function compatibleMedia(slot: AnimationSlot, media: MediaRef): boolean {
  return media.kind === 'imported' && (slot === 'rest' || media.format === 'mp4');
}

function sameMedia(left: MediaRef, right: MediaRef): boolean {
  return left.kind === right.kind && left.id === right.id;
}

function isGifMedia(media: MediaRef): boolean {
  return (
    (media.kind === 'builtin' && media.id === 'mayi') ||
    (media.kind === 'imported' && media.format === 'gif')
  );
}

function mediaLabel(media: MediaRef): string {
  if (media.kind === 'builtin') {
    return '内置动画';
  }
  return `已导入 ${media.format.toUpperCase()} · ${media.id.slice(0, 8)}`;
}

function errorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return (error as CommandError).message;
  }
  return '动画设置暂时无法保存。';
}

export function SettingsPanel({
  bridge,
  onSaved,
  snapshot,
}: SettingsPanelProps) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [media, setMedia] = useState<MediaRef[]>([]);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expectedRevision, setExpectedRevision] = useState(snapshot.revision);

  useEffect(() => {
    setExpectedRevision(snapshot.revision);
  }, [snapshot.revision]);

  useEffect(() => {
    if (!open) {
      return;
    }
    let mounted = true;
    Promise.all([bridge.getSettings(), bridge.listImportedMedia()])
      .then(([nextSettings, nextMedia]) => {
        if (mounted) {
          setSettings(nextSettings);
          setMedia(nextMedia);
          setError(null);
        }
      })
      .catch((cause) => {
        if (mounted) {
          setError(errorMessage(cause));
        }
      });

    return () => {
      mounted = false;
    };
  }, [bridge, open]);

  if (!snapshot.allowedActions.includes('changeSettings')) {
    return null;
  }

  const selectMedia = (slot: AnimationSlot, next: MediaRef) => {
    setSettings((current) =>
      current
        ? {
            ...current,
            animations: { ...current.animations, [slot]: next },
          }
        : current,
    );
  };

  const importMedia = async (slot: AnimationSlot) => {
    setPending(true);
    setError(null);
    try {
      const imported = await bridge.importAnimationMedia(slot);
      if (!imported) {
        return;
      }
      setMedia((current) => [...current, imported]);
      selectMedia(slot, imported);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };

  const save = async () => {
    if (!settings) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const nextSnapshot = await bridge.updateSettings(settings, expectedRevision);
      setExpectedRevision(nextSnapshot.revision);
      onSaved(settings.animations);
      setOpen(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };

  const restIsGif = settings ? isGifMedia(settings.animations.rest) : false;

  return (
    <section className="settings-panel" aria-labelledby="settings-heading">
      <div className="settings-panel__bar">
        <div>
          <p className="settings-panel__eyebrow">动画媒体</p>
          <h2 id="settings-heading">播放设置</h2>
        </div>
        <ActionButton
          aria-expanded={open}
          aria-controls="animation-settings"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? '收起设置' : '设置'}
        </ActionButton>
      </div>

      {open && (
        <div id="animation-settings" className="settings-panel__body">
          {settings ? (
            <>
              <div className="media-slots">
                {(Object.keys(slotDetails) as AnimationSlot[]).map((slot) => {
                  const selected = settings.animations[slot];
                  const candidates = media.filter((item) =>
                    compatibleMedia(slot, item),
                  );
                  return (
                    <section
                      key={slot}
                      className="media-slot"
                      aria-labelledby={`${slot}-media-heading`}
                    >
                      <div className="media-slot__heading">
                        <div>
                          <h3 id={`${slot}-media-heading`}>
                            {slotDetails[slot].title}
                          </h3>
                          <p>{slotDetails[slot].description}</p>
                        </div>
                        <span>{mediaLabel(selected)}</span>
                      </div>
                      <div
                        className="media-slot__options"
                        role="radiogroup"
                        aria-label={`${slotDetails[slot].title}动画来源`}
                      >
                        <label className="media-choice">
                          <input
                            checked={sameMedia(selected, builtinMedia[slot])}
                            name={`${slot}-media`}
                            type="radio"
                            value="builtin"
                            onChange={() => selectMedia(slot, builtinMedia[slot])}
                          />
                          <span>内置动画</span>
                        </label>
                        {candidates.map((item) => (
                          <label key={item.id} className="media-choice">
                            <input
                              checked={sameMedia(selected, item)}
                              name={`${slot}-media`}
                              type="radio"
                              value={item.id}
                              onChange={() => selectMedia(slot, item)}
                            />
                            <span>{mediaLabel(item)}</span>
                          </label>
                        ))}
                        <ActionButton
                          disabled={pending}
                          onClick={() => importMedia(slot)}
                        >
                          导入{slot === 'rest' ? ' MP4 或 GIF' : ' MP4'}
                        </ActionButton>
                      </div>
                    </section>
                  );
                })}
              </div>

              <fieldset className="rest-playback" disabled={restIsGif || pending}>
                <legend>休息视频播放</legend>
                <p>
                  {restIsGif
                    ? 'GIF 使用文件自带的播放方式。'
                    : '仅对休息 MP4 生效。'}
                </p>
                <label>
                  <input
                    checked={settings.animations.restPlayback === 'once'}
                    name="rest-playback"
                    type="radio"
                    value="once"
                    onChange={() =>
                      setSettings((current) =>
                        current
                          ? {
                              ...current,
                              animations: {
                                ...current.animations,
                                restPlayback: 'once',
                              },
                            }
                          : current,
                      )
                    }
                  />
                  播放一次
                </label>
                <label>
                  <input
                    checked={settings.animations.restPlayback === 'loop'}
                    name="rest-playback"
                    type="radio"
                    value="loop"
                    onChange={() =>
                      setSettings((current) =>
                        current
                          ? {
                              ...current,
                              animations: {
                                ...current.animations,
                                restPlayback: 'loop',
                              },
                            }
                          : current,
                      )
                    }
                  />
                  循环播放
                </label>
              </fieldset>

              {error && <p className="settings-panel__error" role="alert">{error}</p>}
              <div className="settings-panel__actions">
                <ActionButton disabled={pending} onClick={() => setOpen(false)}>
                  取消
                </ActionButton>
                <ActionButton tone="primary" disabled={pending} onClick={save}>
                  保存设置
                </ActionButton>
              </div>
            </>
          ) : error ? (
            <p className="settings-panel__error" role="alert">
              {error}
            </p>
          ) : (
            <p className="settings-panel__loading" role="status">
              正在读取动画设置…
            </p>
          )}
        </div>
      )}
    </section>
  );
}
