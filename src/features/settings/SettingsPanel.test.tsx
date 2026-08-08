import { render, screen, waitFor, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi } from 'vitest';
import type { AppSettings, DesktopBridge, TimerSnapshot } from '../../shared/ipc';
import { SettingsPanel } from './SettingsPanel';

const snapshot = (patch: Partial<TimerSnapshot> = {}): TimerSnapshot => ({
  revision: 4,
  status: 'idle',
  phase: null,
  remainingSeconds: 1_200,
  deadlineUtcSeconds: null,
  focusDurationMinutes: 20,
  dailyCompletedFocusCount: 0,
  allowedActions: ['changeSettings'],
  ...patch,
});

const settings: AppSettings = {
  focusDurationMinutes: 20,
  animations: {
    idle: { kind: 'builtin', id: 'play' },
    focus: { kind: 'builtin', id: 'work' },
    rest: { kind: 'builtin', id: 'mayi' },
    restPlayback: 'once',
  },
};

function bridge(): DesktopBridge {
  return {
    subscribeToTimer: vi.fn(),
    startFocus: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    endTimer: vi.fn(),
    endRest: vi.fn(),
    adjustFocusDuration: vi.fn(),
    getSettings: vi.fn(async () => structuredClone(settings)),
    listImportedMedia: vi.fn(async () => []),
    importAnimationMedia: vi.fn(async () => null),
    updateSettings: vi.fn(async () => snapshot({ revision: 5 })),
  };
}

describe('SettingsPanel', () => {
  it('only exposes settings while the timer allows a settings change', () => {
    render(
      <SettingsPanel
        bridge={bridge()}
        onSaved={vi.fn()}
        snapshot={snapshot({ allowedActions: [] })}
      />,
    );

    expect(screen.queryByRole('button', { name: '设置' })).not.toBeInTheDocument();
  });

  it('loads compatible imported media and saves the complete settings at the current revision', async () => {
    const desktop = bridge();
    const imported = {
      kind: 'imported' as const,
      id: 'c2365491-5244-4e7e-b21f-d7b55e01d79b',
      format: 'mp4' as const,
    };
    desktop.listImportedMedia = vi.fn(async () => [imported]);
    const saved = vi.fn();
    const user = userEvent.setup();
    render(<SettingsPanel bridge={desktop} onSaved={saved} snapshot={snapshot()} />);

    await user.click(screen.getByRole('button', { name: '设置' }));
    const focusGroup = await screen.findByRole('radiogroup', {
      name: '专注动画来源',
    });
    const focusOption = within(focusGroup).getByRole('radio', {
      name: '已导入 MP4 · c2365491',
    });
    await user.click(focusOption);
    await user.click(screen.getByRole('button', { name: '保存设置' }));

    await waitFor(() => {
      expect(desktop.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          animations: expect.objectContaining({ focus: imported }),
        }),
        4,
      );
    });
    expect(saved).toHaveBeenCalledWith(
      expect.objectContaining({ focus: imported }),
    );
  });

  it('imports the compatible selected slot and chooses the returned media', async () => {
    const desktop = bridge();
    const imported = {
      kind: 'imported' as const,
      id: '0c9b2d96-c0f4-495a-8446-5f58b9f6536d',
      format: 'mp4' as const,
    };
    desktop.importAnimationMedia = vi.fn(async () => imported);
    const user = userEvent.setup();
    render(<SettingsPanel bridge={desktop} onSaved={vi.fn()} snapshot={snapshot()} />);

    await user.click(screen.getByRole('button', { name: '设置' }));
    await screen.findByText('空闲');
    await user.click(screen.getAllByRole('button', { name: '导入 MP4' })[0]);

    expect(desktop.importAnimationMedia).toHaveBeenCalledWith('idle');
    const idleGroup = screen.getByRole('radiogroup', { name: '空闲动画来源' });
    expect(
      within(idleGroup).getByRole('radio', { name: '已导入 MP4 · 0c9b2d96' }),
    ).toBeChecked();
  });

  it('only offers GIF selections for rest and disables playback mode for GIF', async () => {
    const desktop = bridge();
    const gif = {
      kind: 'imported' as const,
      id: '01f9c521-c688-49c6-8edc-20ce1a77bde8',
      format: 'gif' as const,
    };
    desktop.listImportedMedia = vi.fn(async () => [gif]);
    const user = userEvent.setup();
    render(<SettingsPanel bridge={desktop} onSaved={vi.fn()} snapshot={snapshot()} />);

    await user.click(screen.getByRole('button', { name: '设置' }));
    await screen.findByText('空闲');
    const idleGroup = screen.getByRole('radiogroup', { name: '空闲动画来源' });
    expect(
      within(idleGroup).queryByRole('radio', { name: '已导入 GIF · 01f9c521' }),
    ).not.toBeInTheDocument();

    const restGroup = screen.getByRole('radiogroup', { name: '休息动画来源' });
    await user.click(
      within(restGroup).getByRole('radio', { name: '已导入 GIF · 01f9c521' }),
    );

    expect(screen.getByText('GIF 使用文件自带的播放方式。')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: '播放一次' })).toBeDisabled();
  });

  it('uses the command-returned revision for a subsequent save', async () => {
    const desktop = bridge();
    desktop.updateSettings = vi
      .fn()
      .mockResolvedValueOnce(snapshot({ revision: 5 }))
      .mockResolvedValueOnce(snapshot({ revision: 6 }));
    const user = userEvent.setup();
    render(<SettingsPanel bridge={desktop} onSaved={vi.fn()} snapshot={snapshot()} />);

    await user.click(screen.getByRole('button', { name: '设置' }));
    await screen.findByText('空闲');
    await user.click(screen.getByRole('button', { name: '保存设置' }));
    await user.click(await screen.findByRole('button', { name: '设置' }));
    await screen.findByText('空闲');
    await user.click(screen.getByRole('button', { name: '保存设置' }));

    expect(desktop.updateSettings).toHaveBeenNthCalledWith(1, expect.anything(), 4);
    expect(desktop.updateSettings).toHaveBeenNthCalledWith(2, expect.anything(), 5);
  });

  it('reports an initial settings loading error', async () => {
    const desktop = bridge();
    desktop.getSettings = vi.fn(async () => {
      throw { code: 'settings_unavailable', message: '无法读取动画设置。', retryable: true };
    });
    const user = userEvent.setup();
    render(<SettingsPanel bridge={desktop} onSaved={vi.fn()} snapshot={snapshot()} />);

    await user.click(screen.getByRole('button', { name: '设置' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('无法读取动画设置。');
  });

  it('retains the panel and reports a save error', async () => {
    const desktop = bridge();
    desktop.updateSettings = vi.fn(async () => {
      throw { code: 'stale_revision', message: '设置已更新，请重试。', retryable: true };
    });
    const user = userEvent.setup();
    render(<SettingsPanel bridge={desktop} onSaved={vi.fn()} snapshot={snapshot()} />);

    await user.click(screen.getByRole('button', { name: '设置' }));
    await screen.findByText('空闲');
    await user.click(screen.getByRole('button', { name: '保存设置' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('设置已更新，请重试。');
    expect(screen.getByRole('button', { name: '保存设置' })).toBeInTheDocument();
  });
});
