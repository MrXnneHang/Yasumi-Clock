import { fireEvent, render, screen } from '@testing-library/react';
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

  it('loads the Rust snapshot and starts with the selected duration', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    expect(await screen.findByLabelText('剩余时间 20:00')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '设置' }),
    ).not.toBeInTheDocument();

    const duration = screen.getByRole('slider', { name: '专注时长' });
    fireEvent.change(duration, { target: { value: '23' } });
    expect(duration).toHaveValue('23');
    expect(screen.getByLabelText('剩余时间 23:00')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '开始专注' }));
    expect(desktop.startFocus).toHaveBeenCalledWith(23);
    expect(
      await screen.findByRole('button', { name: '暂停' }),
    ).toBeInTheDocument();
  });

  it('maps a zero-minute slider selection to a one-second display and command', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    const duration = await screen.findByRole('slider', { name: '专注时长' });
    fireEvent.change(duration, { target: { value: '0' } });

    expect(duration).toHaveValue('0');
    expect(duration).toHaveAttribute('aria-valuetext', '0 分钟，实际计时 1 秒');
    expect(screen.getByLabelText('剩余时间 00:01')).toBeInTheDocument();
    expect(screen.getByText('0 分钟 · 实际计时 1 秒')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '开始专注' }));
    expect(desktop.startFocus).toHaveBeenCalledWith(0);
  });

  it('allows the sixty-minute upper boundary', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    const duration = await screen.findByRole('slider', { name: '专注时长' });
    fireEvent.change(duration, { target: { value: '60' } });

    expect(duration).toHaveValue('60');
    expect(screen.getByLabelText('剩余时间 60:00')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '开始专注' }));
    expect(desktop.startFocus).toHaveBeenCalledWith(60);
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
    expect(
      screen.queryByRole('slider', { name: '专注时长' }),
    ).not.toBeInTheDocument();
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
});
