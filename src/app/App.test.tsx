import { render, screen } from '@testing-library/react';
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
  remainingSeconds: 20 * 60,
  deadlineUtcSeconds: null,
  focusDurationMinutes: 20,
  dailyCompletedFocusCount: 3,
  allowedActions: ['startFocus', 'adjustFocusDuration', 'changeSettings'],
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
    subscribeToSettings: vi.fn(async (onSettings) => {
      onSettings({
        settings: structuredClone(settings),
        revision: initial.revision,
      });
      return { unsubscribe: vi.fn() };
    }),
    startFocus: vi.fn(async () =>
      snapshot(initial.revision + 1, {
        status: 'running',
        phase: 'focus',
        allowedActions: ['pause', 'end'],
      }),
    ),
    pause: vi.fn(async () => initial),
    resume: vi.fn(async () => initial),
    endTimer: vi.fn(async () => initial),
    endRest: vi.fn(async () => initial),
    adjustFocusDuration: vi.fn(async () => initial),
    getSettings: vi.fn(async () => structuredClone(settings)),
    getSettingsState: vi.fn(async () => ({
      settings: structuredClone(settings),
      revision: initial.revision,
    })),
    listImportedMedia: vi.fn(async () => []),
    importAnimationMedia: vi.fn(async () => null),
    openSettings: vi.fn(async () => undefined),
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

  it('loads the Rust snapshot and opens settings from the main window', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} />);

    expect(await screen.findByLabelText('剩余时间 20:00')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '设置' }));
    expect(desktop.openSettings).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole('slider', { name: '专注时长' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '开始休息' }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '开始专注' }));
    expect(desktop.startFocus).toHaveBeenCalledWith();
    expect(
      await screen.findByRole('button', { name: '暂停' }),
    ).toBeInTheDocument();
  });

  it('does not expose duration settings in the main window', async () => {
    const desktop = bridge();
    render(<App bridge={desktop} />);

    expect(await screen.findByLabelText('剩余时间 20:00')).toBeInTheDocument();
    expect(
      screen.queryByRole('slider', { name: '专注时长' }),
    ).not.toBeInTheDocument();
  });

  it('ignores stale timer events and accepts newer rest updates', async () => {
    const desktop = bridge(snapshot(5));
    render(<App bridge={desktop} />);
    expect(await screen.findByLabelText('剩余时间 20:00')).toBeInTheDocument();

    desktop.emit(snapshot(4, { remainingSeconds: 10 }));
    expect(screen.queryByLabelText('剩余时间 00:10')).not.toBeInTheDocument();

    desktop.emit(
      snapshot(6, {
        status: 'running',
        phase: 'rest',
        remainingSeconds: 5 * 60,
        allowedActions: ['end'],
      }),
    );
    expect(await screen.findByLabelText('剩余时间 05:00')).toBeInTheDocument();
    expect(screen.getByText('休息中')).toBeInTheDocument();
    expect(
      screen.queryByRole('slider', { name: '专注时长' }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '结束休息' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '暂停' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '继续' }),
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
