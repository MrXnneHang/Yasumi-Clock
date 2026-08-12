import { useEffect, useState } from 'react';
import type { DesktopBridge, ThemeMode } from '../ipc';

export type EffectiveTheme = 'light' | 'dark';

const themeQuery = '(prefers-color-scheme: dark)';

export function applyThemeMode(mode: ThemeMode) {
  if (mode === 'system') {
    document.documentElement.removeAttribute('data-theme');
    return;
  }
  document.documentElement.dataset.theme = mode;
}

export function effectiveTheme(mode: ThemeMode): EffectiveTheme {
  if (mode !== 'system') {
    return mode;
  }
  return window.matchMedia?.(themeQuery).matches ? 'dark' : 'light';
}

export function nextThemeMode(mode: ThemeMode): ThemeMode {
  return effectiveTheme(mode) === 'dark' ? 'light' : 'dark';
}

export function useThemeMode(bridge: DesktopBridge) {
  const [mode, setMode] = useState<ThemeMode>('system');
  const [effective, setEffective] = useState<EffectiveTheme>(() =>
    effectiveTheme('system'),
  );

  useEffect(() => {
    let unsubscribe: () => void = () => undefined;
    bridge
      .subscribeToSettings(({ settings }) => {
        setMode(settings.themeMode);
        applyThemeMode(settings.themeMode);
        setEffective(effectiveTheme(settings.themeMode));
      })
      .then((subscription) => {
        unsubscribe = subscription.unsubscribe;
      })
      .catch(() => undefined);

    return () => unsubscribe();
  }, [bridge]);

  useEffect(() => {
    const query = window.matchMedia?.(themeQuery);
    if (!query || mode !== 'system') {
      return;
    }
    const refresh = () => setEffective(query.matches ? 'dark' : 'light');
    query.addEventListener?.('change', refresh);
    return () => query.removeEventListener?.('change', refresh);
  }, [mode]);

  return { effectiveTheme: effective, mode };
}
