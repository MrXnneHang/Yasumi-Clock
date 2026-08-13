import type { DesktopBridge } from '../shared/ipc';
import type { EffectiveTheme } from '../shared/theme/useThemeMode';
import { WindowTitlebar } from '../shared/window/WindowTitlebar';
import {
  currentWindowControls,
  type WindowControls,
} from '../shared/window/windowControls';

export type MainWindowControls = WindowControls;

interface MainTitlebarProps {
  controls?: MainWindowControls;
  effectiveTheme: EffectiveTheme;
  settingsAvailable: boolean;
  themePending: boolean;
  bridge: DesktopBridge;
  onToggleTheme(): void;
}

function GearIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M10.4 3.1h3.2l.5 2.1c.5.2 1 .5 1.4.8l2.1-.7 1.6 2.8-1.6 1.5c.1.5.1 1.1 0 1.6l1.6 1.5-1.6 2.8-2.1-.7c-.4.3-.9.6-1.4.8l-.5 2.1h-3.2l-.5-2.1c-.5-.2-1-.5-1.4-.8l-2.1.7-1.6-2.8 1.6-1.5a6 6 0 0 1 0-1.6L4.8 8.1l1.6-2.8 2.1.7c.4-.3.9-.6 1.4-.8l.5-2.1Zm1.6 5.4a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" />
    </svg>
  );
}

function ThemeIcon({ theme }: { theme: EffectiveTheme }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      {theme === 'dark' ? (
        <path d="M12 3.5a1 1 0 0 1 1 1V6a1 1 0 1 1-2 0V4.5a1 1 0 0 1 1-1Zm0 5A3.5 3.5 0 1 1 12 15.5 3.5 3.5 0 0 1 12 8.5Zm0 9.5a1 1 0 0 1 1 1v1.5a1 1 0 1 1-2 0V19a1 1 0 0 1 1-1ZM4.5 11h1.5a1 1 0 1 1 0 2H4.5a1 1 0 1 1 0-2Zm13.5 0h1.5a1 1 0 1 1 0 2H18a1 1 0 1 1 0-2ZM6.7 5.3l1.1 1.1a1 1 0 0 1-1.4 1.4L5.3 6.7a1 1 0 0 1 1.4-1.4Zm9.5 9.5 1.1 1.1a1 1 0 0 1-1.4 1.4l-1.1-1.1a1 1 0 0 1 1.4-1.4Zm1.1-8.1-1.1 1.1a1 1 0 1 1-1.4-1.4l1.1-1.1a1 1 0 0 1 1.4 1.4ZM7.8 16.2l-1.1 1.1a1 1 0 0 1-1.4-1.4l1.1-1.1a1 1 0 0 1 1.4 1.4Z" />
      ) : (
        <path d="M19.1 15.2A7.7 7.7 0 0 1 8.8 4.9 7.8 7.8 0 1 0 19.1 15.2Zm-2.2 1.2A6.3 6.3 0 1 1 7.6 7.1a9.2 9.2 0 0 0 9.3 9.3Z" />
      )}
    </svg>
  );
}

export function MainTitlebar({
  bridge,
  controls = currentWindowControls,
  effectiveTheme,
  onToggleTheme,
  settingsAvailable,
  themePending,
}: MainTitlebarProps) {
  return (
    <WindowTitlebar
      controls={controls}
      title="Yasumi Clock"
      actions={
        <>
          <button
            aria-label="打开设置"
            className="window-titlebar__button"
            disabled={!settingsAvailable}
            type="button"
            onClick={() => void bridge.openSettings()}
          >
            <GearIcon />
          </button>
          <button
            aria-label={effectiveTheme === 'dark' ? '切换到浅色' : '切换到深色'}
            className="window-titlebar__button"
            disabled={themePending}
            type="button"
            onClick={onToggleTheme}
          >
            <ThemeIcon theme={effectiveTheme} />
          </button>
        </>
      }
    />
  );
}
