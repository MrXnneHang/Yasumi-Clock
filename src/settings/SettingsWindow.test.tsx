import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  DesktopBridge,
  SettingsState,
  TimerSnapshot,
} from '../shared/ipc';
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
    updateSettings: vi.fn(async () => snapshot()),
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
  });

  afterEach(() => {
    Reflect.deleteProperty(window, '__TAURI_INTERNALS__');
  });

  it('shows global imported videos in all three dropdowns and previews the selected slot', async () => {
    const desktop = bridge();
    desktop.listImportedMedia = vi.fn(async () => [
      { kind: 'imported' as const, id: '59db2ea1-7f57-4e5d-8704-99d00688ff11' },
    ]);
    render(<SettingsWindow bridge={desktop} />);

    const focus = await screen.findByRole('combobox', { name: '专注视频' });
    expect(focus).toHaveTextContent('已导入 · 59db2ea1');
    await userEvent.selectOptions(
      focus,
      'imported:59db2ea1-7f57-4e5d-8704-99d00688ff11',
    );

    expect(
      screen.getByRole('heading', { name: '专注视频' }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('专注视频预览')).toHaveAttribute(
      'src',
      'http://yasumi-media.localhost/59db2ea1-7f57-4e5d-8704-99d00688ff11',
    );
  });

  it('imports once into the global library and selects it for the active slot', async () => {
    const desktop = bridge();
    desktop.importAnimationMedia = vi.fn(async () => ({
      kind: 'imported' as const,
      id: 'b2cedbd3-89cb-4aad-8a23-5cb9faa23ce7',
    }));
    render(<SettingsWindow bridge={desktop} />);
    await screen.findByRole('button', { name: '导入视频' });

    await userEvent.click(screen.getByRole('button', { name: '导入视频' }));

    expect(desktop.importAnimationMedia).toHaveBeenCalledOnce();
    expect(screen.getByRole('combobox', { name: '空闲视频' })).toHaveValue(
      'imported:b2cedbd3-89cb-4aad-8a23-5cb9faa23ce7',
    );
  });

  it('applies the same rest mode to the bundled Mayi preview and saves current revision', async () => {
    const desktop = bridge();
    render(<SettingsWindow bridge={desktop} />);
    await screen.findByRole('radio', { name: '循环播放' });

    await userEvent.click(screen.getByRole('radio', { name: '循环播放' }));
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: '休息视频' }),
      'builtin:mayi',
    );
    expect(screen.getByLabelText('休息视频预览')).toHaveAttribute('loop');
    await userEvent.click(screen.getByRole('button', { name: '保存设置' }));

    await waitFor(() => {
      expect(desktop.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          animations: expect.objectContaining({ restPlayback: 'loop' }),
        }),
        4,
      );
    });
  });

  it('previews and saves the selected theme mode', async () => {
    const desktop = bridge();
    render(<SettingsWindow bridge={desktop} />);
    await screen.findByRole('radio', { name: '深色' });

    await userEvent.click(screen.getByRole('radio', { name: '深色' }));
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');

    await userEvent.click(screen.getByRole('button', { name: '保存设置' }));
    expect(desktop.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ themeMode: 'dark' }),
      4,
    );
  });
  it('reloads authoritative settings after a stale revision response', async () => {
    const desktop = bridge();
    desktop.updateSettings = vi.fn(async () => {
      throw { code: 'stale_revision', message: '设置版本已过期。' };
    });
    desktop.getSettingsState = vi.fn(async () => ({
      ...settingsState(8),
      settings: {
        ...settingsState(8).settings,
        animations: {
          ...settingsState(8).settings.animations,
          idle: { kind: 'builtin' as const, id: 'play' as const },
          restPlayback: 'loop' as const,
        },
      },
    }));
    render(<SettingsWindow bridge={desktop} />);
    await screen.findByRole('button', { name: '保存设置' });

    await userEvent.click(screen.getByRole('button', { name: '保存设置' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '设置已在其他窗口更新，已载入最新配置。',
    );
    expect(desktop.getSettingsState).toHaveBeenCalledOnce();
  });

  it('surfaces save failures without clearing the current selection', async () => {
    const desktop = bridge();
    desktop.updateSettings = vi.fn(async () => {
      throw { code: 'stale_revision', message: '设置已更新，请重试。' };
    });
    render(<SettingsWindow bridge={desktop} />);
    await screen.findByRole('button', { name: '保存设置' });

    await userEvent.click(screen.getByRole('button', { name: '保存设置' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '设置已在其他窗口更新，已载入最新配置。',
    );
    expect(screen.getByRole('combobox', { name: '空闲视频' })).toHaveValue(
      'builtin:play',
    );
  });
});
