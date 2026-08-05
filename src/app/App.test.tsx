import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi } from 'vitest';
import type { AppSettings, DesktopBridge, TimerSnapshot } from '../shared/ipc';
import { App } from './App';

const snapshot = (
  revision = 1,
  patch: Partial<TimerSnapshot> = {},
): TimerSnapshot => ({
  revision,
  status: 'idle',
  phase: null,
  mode: { kind: 'classic' },
  remainingSeconds: 20 * 60,
  deadlineUtcSeconds: null,
  cycleFocusCount: 0,
  cycleTarget: null,
  dailyCompletedFocusCount: 3,
  nextPhase: 'focus',
  allowedActions: ['startFocus', 'adjustClassicDuration', 'changeSettings'],
  ...patch,
});

const settings: AppSettings = {
  presets: {
    custom: {
      id: 'custom',
      name: '自定义模式',
      focusDuration: { kind: 'fixed', minutes: 25 },
      shortBreakMinutes: 5,
      longBreakMinutes: 15,
      cyclesBeforeLongBreak: 4,
      forceRest: false,
    },
  },
};

function bridge(initial = snapshot()) {
  let handler: ((value: TimerSnapshot) => void) | undefined;
  const mock: DesktopBridge & { emit(value: TimerSnapshot): void } = {
    emit(value) {
      handler?.(value);
    },
    subscribeToTimer: vi.fn(async (onSnapshot) => {
      handler = onSnapshot;
      onSnapshot(initial);
      return { unsubscribe: vi.fn() };
    }),
    startFocus: vi.fn(async () =>
      snapshot(initial.revision + 1, {
        status: 'running',
        phase: 'focus',
        allowedActions: ['pause', 'reset'],
      }),
    ),
    pause: vi.fn(async () => initial),
    resume: vi.fn(async () => initial),
    reset: vi.fn(async () => initial),
    dismissBreak: vi.fn(async () => initial),
    adjustClassicDuration: vi.fn(async () => initial),
    selectMode: vi.fn(async () => initial),
    getSettings: vi.fn(async () => structuredClone(settings)),
    updateSettings: vi.fn(async () => initial),
  };
  return mock;
}

describe('App', () => {
  it('shows a loading state until the first snapshot arrives', async () => {
    let resolveSubscription:
      | ((subscription: { unsubscribe(): void }) => void)
      | undefined;
    const desktop = bridge();
    desktop.subscribeToTimer = vi.fn(
      () =>
        new Promise<{ unsubscribe(): void }>((resolve) => {
          resolveSubscription = resolve;
        }),
    );
    render(<App bridge={desktop} />);

    expect(screen.getByRole('status')).toHaveTextContent('正在连接计时核心');
    resolveSubscription?.({ unsubscribe: vi.fn() });
  });

  it('loads the Rust snapshot and invokes timer actions', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    expect(await screen.findByLabelText('剩余时间 20:00')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '开始专注' }));
    expect(desktop.startFocus).toHaveBeenCalledOnce();
    expect(
      await screen.findByRole('button', { name: '暂停' }),
    ).toBeInTheDocument();
  });

  it('ignores stale timer events and accepts newer phase updates', async () => {
    const desktop = bridge(snapshot(5));
    render(<App bridge={desktop} />);
    expect(await screen.findByLabelText('剩余时间 20:00')).toBeInTheDocument();

    desktop.emit(snapshot(4, { remainingSeconds: 10 }));
    expect(screen.queryByLabelText('剩余时间 00:10')).not.toBeInTheDocument();

    desktop.emit(
      snapshot(6, {
        status: 'running',
        phase: 'shortBreak',
        remainingSeconds: 5 * 60,
        nextPhase: null,
        allowedActions: ['pause', 'reset', 'dismissBreak'],
      }),
    );
    expect(await screen.findByLabelText('剩余时间 05:00')).toBeInTheDocument();
    expect(screen.getByText('短休息')).toBeInTheDocument();
  });

  it('enforces classic adjustment boundaries', async () => {
    const desktop = bridge(snapshot(1, { remainingSeconds: 5 * 60 }));
    render(<App bridge={desktop} />);

    expect(
      await screen.findByRole('button', { name: '减少五分钟' }),
    ).toBeDisabled();
    expect(screen.getByRole('button', { name: '增加五分钟' })).toBeEnabled();
  });

  it('surfaces structured command errors without inventing state', async () => {
    const desktop = bridge();
    desktop.startFocus = vi.fn(async () => {
      throw {
        code: 'action_not_allowed',
        message: 'Timer is already running.',
        retryable: false,
      };
    });
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    await user.click(await screen.findByRole('button', { name: '开始专注' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Timer is already running.',
    );
    expect(screen.getByLabelText('剩余时间 20:00')).toBeInTheDocument();
  });

  it('stages settings and restores them on cancel', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    await user.click(await screen.findByRole('button', { name: '设置' }));
    const focus = await screen.findByRole('spinbutton', { name: '专注分钟' });
    await user.clear(focus);
    await user.type(focus, '40');
    await user.click(screen.getByRole('button', { name: '取消' }));
    await user.click(screen.getByRole('button', { name: '设置' }));
    expect(
      await screen.findByRole('spinbutton', { name: '专注分钟' }),
    ).toHaveValue(25);
    expect(desktop.updateSettings).not.toHaveBeenCalled();
  });

  it('saves staged mode and custom settings with the selected revision', async () => {
    const desktop = bridge();
    desktop.selectMode = vi.fn(async () =>
      snapshot(2, { mode: { kind: 'preset', presetId: 'custom' } }),
    );
    desktop.updateSettings = vi.fn(async (_settings, _revision) =>
      snapshot(3, { mode: { kind: 'preset', presetId: 'custom' } }),
    );
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    await user.click(await screen.findByRole('button', { name: '设置' }));
    await user.selectOptions(
      await screen.findByRole('combobox', { name: '计时模式' }),
      'custom',
    );
    const focus = screen.getByRole('spinbutton', { name: '专注分钟' });
    await user.clear(focus);
    await user.type(focus, '30');
    await user.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() =>
      expect(desktop.selectMode).toHaveBeenCalledWith({
        kind: 'preset',
        presetId: 'custom',
      }),
    );
    expect(desktop.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        presets: expect.objectContaining({
          custom: expect.objectContaining({
            focusDuration: { kind: 'fixed', minutes: 30 },
          }),
        }),
      }),
      2,
    );
  });

  it('disables timing settings while active', async () => {
    const desktop = bridge(
      snapshot(2, {
        status: 'running',
        phase: 'focus',
        allowedActions: ['pause', 'reset'],
      }),
    );
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    await user.click(await screen.findByRole('button', { name: '设置' }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '保存' })).toBeDisabled(),
    );
    expect(screen.getByRole('note')).toHaveTextContent('计时进行中');
  });
});
