import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { DesktopBridge } from '../shared/ipc';
import { MainTitlebar } from './MainTitlebar';
import type { MainWindowControls } from './windowControls';

function bridge(): DesktopBridge {
  return {
    subscribeToTimer: vi.fn(),
    subscribeToSettings: vi.fn(),
    subscribeToMediaLibrary: vi.fn(),
    startFocus: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    endTimer: vi.fn(),
    endRest: vi.fn(),
    adjustFocusDuration: vi.fn(),
    getSettings: vi.fn(),
    getSettingsState: vi.fn(),
    listImportedMedia: vi.fn(),
    openMediaFolder: vi.fn(),
    importAnimationMedia: vi.fn(),
    openSettings: vi.fn(async () => undefined),
    setThemeMode: vi.fn(),
    updateSettings: vi.fn(),
  };
}

function controls(maximized = false): MainWindowControls {
  return {
    close: vi.fn(async () => undefined),
    isMaximized: vi.fn(async () => maximized),
    minimize: vi.fn(async () => undefined),
    onResized: vi.fn(async () => () => undefined),
    startDragging: vi.fn(async () => undefined),
    toggleMaximize: vi.fn(async () => undefined),
  };
}

describe('MainTitlebar', () => {
  it('places accessible settings and window controls in the expected order', async () => {
    const desktop = bridge();
    const windowControls = controls();
    render(
      <MainTitlebar
        bridge={desktop}
        controls={windowControls}
        effectiveTheme="light"
        settingsAvailable
        themePending={false}
        onToggleTheme={vi.fn()}
      />,
    );

    const names = screen
      .getAllByRole('button')
      .map((button) => button.getAttribute('aria-label'));
    expect(names).toEqual([
      '拖动窗口或切换最大化',
      '打开设置',
      '切换到深色',
      '最小化窗口',
      '最大化窗口',
      '关闭窗口',
    ]);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: '打开设置' }));
    await user.click(screen.getByRole('button', { name: '最小化窗口' }));
    await user.click(screen.getByRole('button', { name: '最大化窗口' }));
    await user.click(screen.getByRole('button', { name: '关闭窗口' }));

    expect(desktop.openSettings).toHaveBeenCalledOnce();
    expect(windowControls.minimize).toHaveBeenCalledOnce();
    expect(windowControls.toggleMaximize).toHaveBeenCalledOnce();
    expect(windowControls.close).toHaveBeenCalledOnce();
  });

  it('uses an accessible theme icon immediately beside settings', async () => {
    const onToggleTheme = vi.fn();
    const user = userEvent.setup();
    render(
      <MainTitlebar
        bridge={bridge()}
        controls={controls()}
        effectiveTheme="dark"
        settingsAvailable
        themePending={false}
        onToggleTheme={onToggleTheme}
      />,
    );

    const button = screen.getByRole('button', { name: '切换到浅色' });
    expect(button.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    await user.click(button);
    expect(onToggleTheme).toHaveBeenCalledOnce();
  });

  it('keeps unavailable settings visible without enabling them', () => {
    render(
      <MainTitlebar
        bridge={bridge()}
        controls={controls()}
        effectiveTheme="light"
        settingsAvailable={false}
        themePending={false}
        onToggleTheme={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: '打开设置' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '切换到深色' })).toBeEnabled();
  });

  it('drags only from the dedicated drag region', () => {
    const windowControls = controls();
    render(
      <MainTitlebar
        bridge={bridge()}
        controls={windowControls}
        effectiveTheme="light"
        settingsAvailable
        themePending={false}
        onToggleTheme={vi.fn()}
      />,
    );

    fireEvent.pointerDown(screen.getByText('Yasumi Clock'), { button: 0 });
    fireEvent.pointerDown(screen.getByRole('button', { name: '最小化窗口' }), {
      button: 0,
    });

    expect(windowControls.startDragging).toHaveBeenCalledOnce();
  });

  it('toggles maximization from the drag region keyboard shortcuts', async () => {
    const windowControls = controls();
    const user = userEvent.setup();
    render(
      <MainTitlebar
        bridge={bridge()}
        controls={windowControls}
        effectiveTheme="light"
        settingsAvailable
        themePending={false}
        onToggleTheme={vi.fn()}
      />,
    );

    const dragRegion = screen.getByRole('button', {
      name: '拖动窗口或切换最大化',
    });
    dragRegion.focus();
    await user.keyboard('{Enter}');
    await user.keyboard(' ');

    expect(windowControls.toggleMaximize).toHaveBeenCalledTimes(2);
  });

  it('refreshes the maximize control label from window state', async () => {
    render(
      <MainTitlebar
        bridge={bridge()}
        controls={controls(true)}
        effectiveTheme="light"
        settingsAvailable
        themePending={false}
        onToggleTheme={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: '还原窗口' }),
      ).toBeInTheDocument();
    });
  });
});
