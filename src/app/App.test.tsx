import { fireEvent, render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi } from 'vitest';
import type { AppSettings, DesktopBridge, TimerSnapshot } from '../shared/ipc';
import { App } from './App';
import type { MainWindowControls } from './windowControls';

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
  themeMode: 'system',
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
    subscribeToMediaLibrary: vi.fn(async () => ({ unsubscribe: vi.fn() })),
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
    openMediaFolder: vi.fn(async () => undefined),
    importAnimationMedia: vi.fn(async () => null),
    openSettings: vi.fn(async () => undefined),
    setThemeMode: vi.fn(async (themeMode) => ({
      settings: { ...structuredClone(settings), themeMode },
      revision: initial.revision + 1,
    })),
    updateSettings: vi.fn(async () => initial),
  };
  return mock;
}

function controls(): MainWindowControls {
  return {
    close: vi.fn(async () => undefined),
    isMaximized: vi.fn(async () => false),
    minimize: vi.fn(async () => undefined),
    onResized: vi.fn(async () => () => undefined),
    startDragging: vi.fn(async () => undefined),
    toggleMaximize: vi.fn(async () => undefined),
  };
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
    render(<App bridge={desktop} controls={controls()} />);

    expect(screen.getByRole('status')).toHaveTextContent('正在连接计时核心');
    resolveSubscription?.({ unsubscribe: vi.fn() });
  });

  it('loads the Rust snapshot and opens settings from the main window', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} controls={controls()} />);

    expect(await screen.findByLabelText('剩余时间 20:00')).toBeInTheDocument();
    expect(document.querySelector('.app-shell')).not.toBeInTheDocument();
    expect(document.querySelector('.app-layout')).not.toBeInTheDocument();
    expect(
      document.querySelector('.main-window > .timer-panel'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '关闭窗口' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('slider', { name: '本次专注时长' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '打开设置' }));
    expect(desktop.openSettings).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole('slider', { name: '专注时长' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '开始休息' }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '开始专注' }));
    expect(desktop.startFocus).toHaveBeenCalledWith(20);
    const pause = await screen.findByRole('button', { name: '暂停' });
    const end = screen.getByRole('button', { name: '结束专注' });
    expect(pause).toHaveClass('timer-action-button');
    expect(end).toHaveClass('timer-action-button');
    expect(pause.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(end.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByLabelText('剩余时间 20:00')).toBeInTheDocument();
  });

  it('uses the idle slider as a one-session focus override', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<App bridge={desktop} controls={controls()} />);

    const duration = await screen.findByRole('slider', {
      name: '本次专注时长',
    });
    fireEvent.change(duration, { target: { value: '0' } });

    expect(screen.getByLabelText('剩余时间 00:01')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '开始专注' }));

    expect(desktop.startFocus).toHaveBeenCalledWith(0);
    expect(desktop.updateSettings).not.toHaveBeenCalled();
  });

  it('commits successful timer state changes through a view transition', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    const startViewTransition = vi.fn((update: () => void) => {
      update();
      return {
        finished: Promise.resolve(),
        ready: Promise.resolve(),
        skipTransition: vi.fn(),
        types: new Set<string>(),
        updateCallbackDone: Promise.resolve(),
      };
    });
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: startViewTransition,
    });

    try {
      render(<App bridge={desktop} controls={controls()} />);
      await user.click(await screen.findByRole('button', { name: '开始专注' }));

      expect(startViewTransition).toHaveBeenCalledOnce();
      expect(
        await screen.findByRole('button', { name: '暂停' }),
      ).toBeInTheDocument();
    } finally {
      Reflect.deleteProperty(document, 'startViewTransition');
    }
  });

  it('ignores stale timer events and accepts newer rest updates', async () => {
    const desktop = bridge(snapshot(5));
    render(<App bridge={desktop} controls={controls()} />);
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
    expect(screen.getByRole('button', { name: '打开设置' })).toBeDisabled();
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

  it('does not transition a failed timer command', async () => {
    const desktop = bridge();
    desktop.startFocus = vi.fn(async () => {
      throw {
        code: 'action_not_allowed',
        message: 'Timer is already running.',
        retryable: false,
      };
    });
    const startViewTransition = vi.fn();
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: startViewTransition,
    });
    const user = userEvent.setup();

    try {
      render(<App bridge={desktop} controls={controls()} />);
      await user.click(await screen.findByRole('button', { name: '开始专注' }));

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Timer is already running.',
      );
      expect(startViewTransition).not.toHaveBeenCalled();
    } finally {
      Reflect.deleteProperty(document, 'startViewTransition');
    }
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
    render(<App bridge={desktop} controls={controls()} />);

    await user.click(await screen.findByRole('button', { name: '开始专注' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Timer is already running.',
    );
    expect(screen.getByLabelText('剩余时间 20:00')).toBeInTheDocument();
  });
});
