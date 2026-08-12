import { useEffect } from 'react';
import type { DesktopBridge, ThemeMode } from '../ipc';

export function applyThemeMode(mode: ThemeMode) {
  if (mode === 'system') {
    document.documentElement.removeAttribute('data-theme');
    return;
  }
  document.documentElement.dataset.theme = mode;
}

export function useThemeMode(bridge: DesktopBridge) {
  useEffect(() => {
    let unsubscribe: () => void = () => undefined;
    bridge
      .subscribeToSettings(({ settings }) => applyThemeMode(settings.themeMode))
      .then((subscription) => {
        unsubscribe = subscription.unsubscribe;
      })
      .catch(() => undefined);

    return () => unsubscribe();
  }, [bridge]);
}
