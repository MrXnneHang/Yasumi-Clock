import { useEffect, useState } from 'react';
import type { DesktopBridge } from '../shared/ipc';
import { mainWindowControls, type MainWindowControls } from './windowControls';

interface MainTitlebarProps {
  controls?: MainWindowControls;
  settingsAvailable: boolean;
  bridge: DesktopBridge;
}

function GearIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M10.4 3.1h3.2l.5 2.1c.5.2 1 .5 1.4.8l2.1-.7 1.6 2.8-1.6 1.5c.1.5.1 1.1 0 1.6l1.6 1.5-1.6 2.8-2.1-.7c-.4.3-.9.6-1.4.8l-.5 2.1h-3.2l-.5-2.1c-.5-.2-1-.5-1.4-.8l-2.1.7-1.6-2.8 1.6-1.5a6 6 0 0 1 0-1.6L4.8 8.1l1.6-2.8 2.1.7c.4-.3.9-.6 1.4-.8l.5-2.1Zm1.6 5.4a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" />
    </svg>
  );
}

function MinimizeIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M6 12h12v1.5H6z" />
    </svg>
  );
}

function MaximizeIcon({ maximized }: { maximized: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      {maximized ? (
        <path d="M8 5h10a1 1 0 0 1 1 1v10h-1.5V6.5H8V5Zm-3 3h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Zm.5 1.5v9h9v-9h-9Z" />
      ) : (
        <path d="M5 5h14v14H5V5Zm1.5 1.5v11h11v-11h-11Z" />
      )}
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m6.4 5.3 5.6 5.6 5.6-5.6 1.1 1.1-5.6 5.6 5.6 5.6-1.1 1.1-5.6-5.6-5.6 5.6-1.1-1.1 5.6-5.6-5.6-5.6 1.1-1.1Z" />
    </svg>
  );
}

export function MainTitlebar({
  bridge,
  controls = mainWindowControls,
  settingsAvailable,
}: MainTitlebarProps) {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    let mounted = true;
    let unlisten: () => void = () => undefined;
    const refreshMaximized = () => {
      void controls.isMaximized().then((value) => {
        if (mounted) {
          setMaximized(value);
        }
      });
    };

    refreshMaximized();
    void controls.onResized(refreshMaximized).then((unsubscribe) => {
      unlisten = unsubscribe;
    });

    return () => {
      mounted = false;
      unlisten();
    };
  }, [controls]);

  const toggleMaximized = () => {
    void controls
      .toggleMaximize()
      .then(() => controls.isMaximized().then(setMaximized));
  };

  return (
    <header className="app-chrome">
      <button
        aria-label="拖动窗口或切换最大化"
        className="app-chrome__drag-region"
        onDoubleClick={toggleMaximized}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggleMaximized();
          }
        }}
        onPointerDown={(event) => {
          if (event.button === 0) {
            void controls.startDragging();
          }
        }}
        type="button"
      >
        <span>Yasumi Clock</span>
      </button>
      <nav className="app-chrome__controls" aria-label="窗口控制">
        <button
          aria-label="打开设置"
          className="app-chrome__button"
          disabled={!settingsAvailable}
          onClick={() => void bridge.openSettings()}
          type="button"
        >
          <GearIcon />
        </button>
        <button
          aria-label="最小化窗口"
          className="app-chrome__button"
          onClick={() => void controls.minimize()}
          type="button"
        >
          <MinimizeIcon />
        </button>
        <button
          aria-label={maximized ? '还原窗口' : '最大化窗口'}
          className="app-chrome__button"
          onClick={toggleMaximized}
          type="button"
        >
          <MaximizeIcon maximized={maximized} />
        </button>
        <button
          aria-label="关闭窗口"
          className="app-chrome__button app-chrome__button--close"
          onClick={() => void controls.close()}
          type="button"
        >
          <CloseIcon />
        </button>
      </nav>
    </header>
  );
}
