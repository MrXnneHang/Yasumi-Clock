import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  DesktopBridge,
  SettingsState,
  TimerSnapshot,
} from '../shared/ipc';
import type { WindowControls } from '../shared/window/windowControls';
import { SettingsWindow } from './SettingsWindow';

const settingsState = (revision = 4): SettingsState => ({
  revision,
  settings: {
    focusDurationMinutes: 20,
    themeMode: 'system',
    animations: {
      idle: { kind: 'builtin', id: 'play' },
      focus: { kind: 'builtin', id: 'work' },
      rest: { kind: 'builtin', id: 'mayi' },
      restPlayback: 'once',
    },
  },
});

const snapshot = (revision = 5): TimerSnapshot => ({
  revision,
  status: 'idle',
  phase: null,
  remainingSeconds: 1_200,
  deadlineUtcSeconds: null,
  focusDurationMinutes: 20,
  dailyCompletedFocusCount: 0,
  allowedActions: ['changeSettings'],
});

function bridge(): DesktopBridge {
  return {
    subscribeToTimer: vi.fn(),
    subscribeToSettings: vi.fn(async (onSettings) => {
      onSettings(settingsState());
      return { unsubscribe: vi.fn() };
    }),
    startFocus: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    endTimer: vi.fn(),
    endRest: vi.fn(),
    adjustFocusDuration: vi.fn(),
    getSettings: vi.fn(async () => settingsState().settings),
    getSettingsState: vi.fn(async () => settingsState()),
    listImportedMedia: vi.fn(async () => []),
    importAnimationMedia: vi.fn(async () => null),
    openSettings: vi.fn(async () => undefined),
    setThemeMode: vi.fn(),
    updateSettings: vi.fn(async () => snapshot()),
  };
}

const controls: WindowControls = {
  close: vi.fn(async () => undefined),
  isMaximized: vi.fn(async () => false),
  minimize: vi.fn(async () => undefined),
  onResized: vi.fn(async () => () => undefined),
  startDragging: vi.fn(async () => undefined),
  toggleMaximize: vi.fn(async () => undefined),
};

const imported = {
  kind: 'imported' as const,
  id: '59db2ea1-7f57-4e5d-8704-99d00688ff11',
};

function renderSettings(desktop = bridge()) {
  return {
    desktop,
    ...render(<SettingsWindow bridge={desktop} controls={controls} />),
  };
}

describe('SettingsWindow', () => {
  beforeEach(() => {
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: {
        convertFileSrc: vi.fn(
          (id: string, protocol: string) =>
            `http://${protocol}.localhost/${id}`,
        ),
      },
    });
    vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(
      () => undefined,
    );
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(
      () => undefined,
    );
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  });

  afterEach(() => {
    Reflect.deleteProperty(window, '__TAURI_INTERNALS__');
    vi.restoreAllMocks();
  });

  it('shows one page title and no redundant scene prompt', async () => {
    renderSettings();

    expect(
      await screen.findByRole('heading', { name: '设置', level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('设置')).toHaveLength(1);
    expect(screen.queryByText('选择要配置的计时状态')).not.toBeInTheDocument();
    expect(screen.getByRole('group', { name: '计时状态' })).toBeInTheDocument();
  });

  it('uses one compact editor to configure all three states', async () => {
    const desktop = bridge();
    desktop.listImportedMedia = vi.fn(async () => [imported]);
    const user = userEvent.setup();
    renderSettings(desktop);

    expect(
      await screen.findByRole('combobox', { name: '等待视频' }),
    ).toHaveTextContent('已导入 · 59db2ea1');
    await user.click(screen.getByRole('radio', { name: /专注/ }));
    expect(screen.getByRole('combobox', { name: '专注视频' })).toHaveValue(
      'builtin:work',
    );
    await user.click(screen.getByRole('radio', { name: /休息/ }));
    expect(screen.getByRole('combobox', { name: '休息视频' })).toHaveValue(
      'builtin:mayi',
    );
    expect(screen.getByRole('button', { name: '单次' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('keeps Save enabled and persists an unchanged draft', async () => {
    const { desktop } = renderSettings();
    const user = userEvent.setup();
    const save = await screen.findByRole('button', { name: '保存设置' });

    expect(save).toBeEnabled();
    await user.click(save);

    expect(desktop.updateSettings).toHaveBeenCalledWith(
      settingsState().settings,
      4,
    );
  });

  it('opens a controlled preview and closes immediately when the canvas is left', async () => {
    const user = userEvent.setup();
    renderSettings();

    await user.click(
      await screen.findByRole('button', { name: '预览等待动画' }),
    );
    const dialog = screen.getByRole('dialog');
    const video = screen.getByLabelText('等待视频预览', { selector: 'video' });
    expect(video).toHaveAttribute('controls');

    fireEvent.mouseLeave(dialog);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('uses video metadata for a complete intrinsic-ratio preview', async () => {
    const user = userEvent.setup();
    renderSettings();

    await user.click(
      await screen.findByRole('button', { name: '预览等待动画' }),
    );
    const video = screen.getByLabelText('等待视频预览', { selector: 'video' });
    Object.defineProperties(video, {
      videoWidth: { configurable: true, value: 720 },
      videoHeight: { configurable: true, value: 720 },
    });
    fireEvent.loadedMetadata(video);

    expect(screen.getByRole('dialog')).toHaveStyle({
      aspectRatio: '720 / 720',
    });
  });

  it('closes with Escape, restores focus, and stays closed', async () => {
    const user = userEvent.setup();
    renderSettings();

    const trigger = await screen.findByRole('button', { name: '预览等待动画' });
    await user.click(trigger);
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('merges the animation draft into fresh settings after a stale revision', async () => {
    const desktop = bridge();
    desktop.updateSettings = vi
      .fn()
      .mockRejectedValueOnce({ code: 'stale_revision', message: 'stale' })
      .mockResolvedValueOnce(snapshot(9));
    desktop.getSettingsState = vi.fn(async () => ({
      ...settingsState(8),
      settings: { ...settingsState(8).settings, themeMode: 'dark' as const },
    }));
    const user = userEvent.setup();
    renderSettings(desktop);

    await user.click(await screen.findByRole('radio', { name: /休息/ }));
    await user.click(screen.getByRole('button', { name: '循环' }));
    await user.click(screen.getByRole('button', { name: '保存设置' }));

    await waitFor(() =>
      expect(desktop.updateSettings).toHaveBeenCalledTimes(2),
    );
    expect(desktop.updateSettings).toHaveBeenLastCalledWith(
      expect.objectContaining({
        themeMode: 'dark',
        animations: expect.objectContaining({ restPlayback: 'loop' }),
      }),
      8,
    );
  });
});
