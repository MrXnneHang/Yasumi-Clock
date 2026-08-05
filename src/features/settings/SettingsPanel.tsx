import { useEffect, useState } from 'react';
import type {
  AppSettings,
  DesktopBridge,
  FocusDurationPlan,
  TimerMode,
  TimerSnapshot,
} from '../../shared/ipc';
import { ActionButton } from '../../shared/ui/ActionButton';

interface SettingsPanelProps {
  bridge: DesktopBridge;
  snapshot: TimerSnapshot;
  pending: boolean;
  run(command: () => Promise<TimerSnapshot>): Promise<void>;
}

const CUSTOM_PRESET_ID = 'custom';

function fixedMinutes(plan: FocusDurationPlan) {
  return plan.kind === 'fixed' ? plan.minutes : (plan.minutes[0] ?? 25);
}

export function SettingsPanel({
  bridge,
  snapshot,
  pending,
  run,
}: SettingsPanelProps) {
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState<AppSettings | null>(null);
  const [draft, setDraft] = useState<AppSettings | null>(null);
  const [mode, setMode] = useState<TimerMode>(snapshot.mode);
  const [loadError, setLoadError] = useState<string | null>(null);
  const canChange = snapshot.allowedActions.includes('changeSettings');

  useEffect(() => {
    if (!open || saved) {
      return;
    }
    bridge
      .getSettings()
      .then((settings) => {
        setSaved(settings);
        setDraft(structuredClone(settings));
      })
      .catch((error) =>
        setLoadError(error instanceof Error ? error.message : String(error)),
      );
  }, [bridge, open, saved]);

  useEffect(() => setMode(snapshot.mode), [snapshot.mode]);

  const custom = draft?.presets[CUSTOM_PRESET_ID];
  const updateCustom = (patch: Partial<typeof custom>) => {
    if (!draft || !custom) {
      return;
    }
    setDraft({
      ...draft,
      presets: {
        ...draft.presets,
        [CUSTOM_PRESET_ID]: { ...custom, ...patch },
      },
    });
  };

  const cancel = () => {
    setDraft(saved ? structuredClone(saved) : null);
    setMode(snapshot.mode);
    setOpen(false);
  };

  const save = async () => {
    if (!draft) {
      return;
    }
    await run(async () => {
      const selected = await bridge.selectMode(mode);
      const updated = await bridge.updateSettings(draft, selected.revision);
      setSaved(structuredClone(draft));
      setOpen(false);
      return updated;
    });
  };

  return (
    <aside className="settings-panel" aria-labelledby="settings-heading">
      <div className="settings-panel__header">
        <div>
          <p className="eyebrow">TIMER SETTINGS</p>
          <h2 id="settings-heading">专注设置</h2>
        </div>
        <ActionButton onClick={() => setOpen((value) => !value)}>
          {open ? '收起' : '设置'}
        </ActionButton>
      </div>

      {!open ? (
        <p className="settings-summary">
          当前模式：
          {snapshot.mode.kind === 'classic'
            ? '经典模式'
            : snapshot.mode.presetId}
        </p>
      ) : loadError ? (
        <p className="error-banner" role="alert">
          {loadError}
        </p>
      ) : !draft || !custom ? (
        <p role="status">正在读取设置…</p>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <fieldset disabled={!canChange || pending}>
            <legend className="sr-only">专注模式与预设</legend>
            <label>
              计时模式
              <select
                value={mode.kind === 'classic' ? 'classic' : mode.presetId}
                onChange={(event) =>
                  setMode(
                    event.target.value === 'classic'
                      ? { kind: 'classic' }
                      : { kind: 'preset', presetId: event.target.value },
                  )
                }
              >
                <option value="classic">经典模式</option>
                {Object.values(draft.presets).map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="settings-grid">
              <label>
                专注分钟
                <input
                  type="number"
                  min="1"
                  max="240"
                  value={fixedMinutes(custom.focusDuration)}
                  onChange={(event) =>
                    updateCustom({
                      focusDuration: {
                        kind: 'fixed',
                        minutes: Number(event.target.value),
                      },
                    })
                  }
                />
              </label>
              <label>
                短休息
                <input
                  type="number"
                  min="1"
                  max="240"
                  value={custom.shortBreakMinutes}
                  onChange={(event) =>
                    updateCustom({
                      shortBreakMinutes: Number(event.target.value),
                    })
                  }
                />
              </label>
              <label>
                长休息
                <input
                  type="number"
                  min="1"
                  max="240"
                  value={custom.longBreakMinutes}
                  onChange={(event) =>
                    updateCustom({
                      longBreakMinutes: Number(event.target.value),
                    })
                  }
                />
              </label>
              <label>
                长休息前轮次
                <input
                  type="number"
                  min="1"
                  max="12"
                  value={custom.cyclesBeforeLongBreak}
                  onChange={(event) =>
                    updateCustom({
                      cyclesBeforeLongBreak: Number(event.target.value),
                    })
                  }
                />
              </label>
            </div>

            <label className="check-field">
              <input
                type="checkbox"
                checked={custom.forceRest}
                onChange={(event) =>
                  updateCustom({ forceRest: event.target.checked })
                }
              />
              强制完成休息
            </label>
          </fieldset>

          {!canChange && (
            <p className="settings-lock" role="note">
              计时进行中，结束或重置后才能保存计时设置。
            </p>
          )}
          <div className="settings-actions">
            <ActionButton onClick={cancel}>取消</ActionButton>
            <ActionButton
              tone="primary"
              type="submit"
              disabled={!canChange || pending}
            >
              保存
            </ActionButton>
          </div>
        </form>
      )}
    </aside>
  );
}
