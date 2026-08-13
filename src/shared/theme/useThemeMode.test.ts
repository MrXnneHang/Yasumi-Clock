import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { DesktopBridge, SettingsState, TimerSnapshot } from '../ipc';
import {
  applyThemeMode,
  effectiveTheme,
  nextThemeMode,
  useThemeMode,
} from './useThemeMode';

const settingsState = (themeMode: SettingsState['settings']['themeMode']) => ({
  revision: 1,
  settings: {
    focusDurationMinutes: 20,
    themeMode,
    animations: {
      idle: { kind: 'builtin' as const, id: 'play' as const },
      focus: { kind: 'builtin' as const, id: 'work' as const },
      rest: { kind: 'builtin' as const, id: 'mayi' as const },
      restPlayback: 'once' as const,
    },
  },
});

function bridge(state: SettingsState): DesktopBridge & {
  emitSettings(state: SettingsState): void;
} {
  let onSettings: ((state: SettingsState) => void) | undefined;
  return {
    emitSettings(next) {
      onSettings?.(next);
    },
    subscribeToTimer: vi.fn(),
    subscribeToSettings: vi.fn(async (handler) => {
      onSettings = handler;
      handler(state);
      return { unsubscribe: vi.fn() };
    }),
    startFocus: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    endTimer: vi.fn(),
    endRest: vi.fn(),
    adjustFocusDuration: vi.fn(),
    getSettings: vi.fn(async () => state.settings),
    getSettingsState: vi.fn(async () => state),
    listImportedMedia: vi.fn(async () => []),
    importAnimationMedia: vi.fn(async () => null),
    openSettings: vi.fn(async () => undefined),
    setThemeMode: vi.fn(),
    updateSettings: vi.fn(async () => ({}) as TimerSnapshot),
  };
}

describe('theme mode', () => {
  it('applies saved theme modes from settings subscriptions', async () => {
    const desktop = bridge(settingsState('dark'));
    renderHook(() => useThemeMode(desktop));

    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    });

    desktop.emitSettings({ ...settingsState('light'), revision: 2 });
    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    });
  });

  it('resolves and toggles the effective system theme', () => {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn(() => ({ matches: false })),
    });
    expect(effectiveTheme('system')).toBe('light');
    expect(nextThemeMode('system')).toBe('dark');

    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn(() => ({ matches: true })),
    });
    expect(effectiveTheme('system')).toBe('dark');
    expect(nextThemeMode('system')).toBe('light');
    Reflect.deleteProperty(window, 'matchMedia');
  });

  it('removes the explicit mode for system preference', () => {
    applyThemeMode('light');
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');

    applyThemeMode('system');
    expect(document.documentElement).not.toHaveAttribute('data-theme');
  });
});
