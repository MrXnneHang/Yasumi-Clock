import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  desktopBridge,
  type AnimationSettings,
  type AppSettings,
  type DesktopBridge,
  type MediaRef,
  type RestPlaybackMode,
} from '../shared/ipc';
import { useThemeMode } from '../shared/theme/useThemeMode';
import { WindowTitlebar } from '../shared/window/WindowTitlebar';
import type { WindowControls } from '../shared/window/windowControls';
import {
  AnimationSettingsSection,
  type MediaSlot,
} from './AnimationSettingsSection';
import { animationDraftEquals } from './MediaSlotRow';
import { VideoPreviewPopover } from './VideoPreviewPopover';

const builtins = {
  idle: { kind: 'builtin', id: 'play' },
  focus: { kind: 'builtin', id: 'work' },
  rest: { kind: 'builtin', id: 'mayi' },
} as const satisfies Record<MediaSlot, MediaRef>;

const slotCopy: Record<MediaSlot, string> = {
  idle: '等待',
  focus: '专注',
  rest: '休息',
};

function mediaValue(media: MediaRef): string {
  return `${media.kind}:${media.id}`;
}

function mediaLabel(media: MediaRef): string {
  return media.kind === 'builtin'
    ? '内置视频'
    : `已导入 · ${media.id.slice(0, 8)}`;
}

function decodeMedia(
  slot: MediaSlot,
  value: string,
  media: MediaRef[],
): MediaRef | undefined {
  return [builtins[slot], ...media].find(
    (candidate) => mediaValue(candidate) === value,
  );
}

function message(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return String(error.message);
  }
  return '设置暂时无法完成。';
}

interface SettingsWindowProps {
  bridge?: DesktopBridge;
  controls?: WindowControls;
}

export function SettingsWindow({
  bridge = desktopBridge,
  controls,
}: SettingsWindowProps) {
  useThemeMode(bridge);
  const [authoritative, setAuthoritative] = useState<AppSettings | null>(null);
  const [draft, setDraft] = useState<AnimationSettings | null>(null);
  const [baseline, setBaseline] = useState<AnimationSettings | null>(null);
  const [media, setMedia] = useState<MediaRef[]>([]);
  const [revision, setRevision] = useState(-1);
  const [activeSlot, setActiveSlot] = useState<MediaSlot>('idle');
  const [previewOpen, setPreviewOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previewTrigger = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    let mounted = true;
    let unsubscribe: () => void = () => undefined;
    Promise.all([
      bridge.subscribeToSettings((state) => {
        if (!mounted) return;
        setAuthoritative(state.settings);
        setRevision(state.revision);
        setDraft((current) => current ?? state.settings.animations);
        setBaseline((current) => current ?? state.settings.animations);
      }),
      bridge.listImportedMedia(),
    ])
      .then(([subscription, imported]) => {
        if (!mounted) {
          subscription.unsubscribe();
          return;
        }
        unsubscribe = subscription.unsubscribe;
        setMedia(imported);
      })
      .catch((cause) => {
        if (mounted) setError(message(cause));
      });

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, [bridge]);

  const importedOptions = useMemo(() => media, [media]);
  const dirty = Boolean(
    draft && baseline && !animationDraftEquals(draft, baseline),
  );

  const closePreview = useCallback((restoreFocus = false) => {
    setPreviewOpen(false);
    if (restoreFocus) {
      requestAnimationFrame(() => previewTrigger.current?.focus());
    }
  }, []);

  const changeActiveSlot = (slot: MediaSlot) => {
    if (slot !== activeSlot) closePreview(false);
    setActiveSlot(slot);
  };

  const select = (value: string) => {
    const nextMedia = decodeMedia(activeSlot, value, media);
    if (!nextMedia) return;
    closePreview(false);
    setDraft((current) =>
      current ? { ...current, [activeSlot]: nextMedia } : current,
    );
  };

  const setRestPlayback = (restPlayback: RestPlaybackMode) => {
    setDraft((current) => (current ? { ...current, restPlayback } : current));
  };

  const importVideo = async () => {
    setPending(true);
    setError(null);
    try {
      const imported = await bridge.importAnimationMedia();
      if (imported) setMedia((current) => [...current, imported]);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setPending(false);
    }
  };

  const persistDraft = (
    currentSettings: AppSettings,
    currentRevision: number,
    animations: AnimationSettings,
  ) =>
    bridge.updateSettings({ ...currentSettings, animations }, currentRevision);

  const save = async () => {
    if (!authoritative || !draft || revision < 0 || pending) return;
    setPending(true);
    setError(null);
    try {
      const snapshot = await persistDraft(authoritative, revision, draft);
      setRevision(snapshot.revision);
      setBaseline(draft);
    } catch (cause) {
      if (
        typeof cause === 'object' &&
        cause !== null &&
        'code' in cause &&
        cause.code === 'stale_revision'
      ) {
        try {
          const current = await bridge.getSettingsState();
          const snapshot = await persistDraft(
            current.settings,
            current.revision,
            draft,
          );
          setAuthoritative({ ...current.settings, animations: draft });
          setRevision(snapshot.revision);
          setBaseline(draft);
        } catch (retryCause) {
          setError(message(retryCause));
        }
      } else {
        setError(message(cause));
      }
    } finally {
      setPending(false);
    }
  };

  const openPreview = (trigger: HTMLButtonElement) => {
    previewTrigger.current = trigger;
    setPreviewOpen(true);
  };

  return (
    <main className="settings-shell">
      <WindowTitlebar
        controls={controls}
        title="设置"
        variant="settings"
        showTitle={false}
      />
      {!authoritative || !draft || !baseline ? (
        <section className="settings-window settings-window--loading">
          {error ? (
            <p role="alert">{error}</p>
          ) : (
            <p role="status">正在读取设置…</p>
          )}
        </section>
      ) : (
        <section className="settings-window" aria-labelledby="settings-heading">
          <header className="settings-window__header">
            <h1 id="settings-heading">设置</h1>
          </header>

          <AnimationSettingsSection
            activeSlot={activeSlot}
            media={draft[activeSlot]}
            mediaLabel={mediaLabel}
            mediaValue={mediaValue}
            options={[builtins[activeSlot], ...importedOptions]}
            pending={pending}
            restPlayback={draft.restPlayback}
            onActiveSlotChange={changeActiveSlot}
            onImport={() => void importVideo()}
            onPreview={openPreview}
            onRestPlaybackChange={setRestPlayback}
            onSelect={select}
          />

          {error && (
            <p className="settings-window__error" role="alert">
              {error}
            </p>
          )}
          <footer className="settings-window__footer">
            <span>{dirty ? '有未保存的更改' : '设置已保存'}</span>
            <button
              disabled={pending}
              onClick={() => void save()}
              type="button"
            >
              保存设置
            </button>
          </footer>

          {previewOpen && (
            <VideoPreviewPopover
              media={draft[activeSlot]}
              slot={activeSlot}
              title={slotCopy[activeSlot]}
              onClose={() => closePreview(true)}
              onMouseLeave={() => closePreview()}
            />
          )}
        </section>
      )}
    </main>
  );
}
