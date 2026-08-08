import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import type { DesktopBridge, TimerSnapshot } from '../shared/ipc';
import { RestOverlay } from './RestOverlay';

const restSnapshot = (patch: Partial<TimerSnapshot> = {}): TimerSnapshot => ({
  revision: 1,
  status: 'running',
  phase: 'rest',
  remainingSeconds: 300,
  deadlineUtcSeconds: 1_700_000_300,
  focusDurationMinutes: 20,
  dailyCompletedFocusCount: 1,
  allowedActions: ['end'],
  ...patch,
});

function bridge(initial = restSnapshot()): DesktopBridge {
  return {
    subscribeToTimer: vi.fn(async (onSnapshot) => {
      onSnapshot(initial);
      return { unsubscribe: vi.fn() };
    }),
    startFocus: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    endTimer: vi.fn(),
    endRest: vi.fn(async () =>
      restSnapshot({ revision: 2, phase: null, status: 'idle' }),
    ),
    adjustFocusDuration: vi.fn(),
    getSettings: vi.fn(),
    listImportedMedia: vi.fn(async () => []),
    importAnimationMedia: vi.fn(async () => null),
    updateSettings: vi.fn(),
  };
}

describe('RestOverlay', () => {
  it('renders the rest countdown and ends rest through its narrow command', async () => {
    const desktop = bridge();
    const user = userEvent.setup();
    render(<RestOverlay bridge={desktop} />);

    expect(
      await screen.findByRole('heading', { name: '休息中' }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('剩余时间 05:00')).toBeInTheDocument();
    const restAnimation = screen.getByLabelText('休息动画');
    expect(restAnimation.tagName).toBe('IMG');
    expect(restAnimation).toHaveAttribute(
      'src',
      expect.stringContaining('/src/img/mayi.gif'),
    );
    expect(restAnimation).not.toHaveAttribute('loop');
    expect(
      screen.queryByRole('button', { name: '暂停' }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '结束休息' }));

    expect(desktop.endRest).toHaveBeenCalledOnce();
  });

  it('does not expose rest controls after an idle snapshot', async () => {
    render(
      <RestOverlay
        bridge={bridge(
          restSnapshot({ phase: null, status: 'idle', allowedActions: [] }),
        )}
      />,
    );

    expect(await screen.findByText('休息已结束')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '结束休息' }),
    ).not.toBeInTheDocument();
  });
});
