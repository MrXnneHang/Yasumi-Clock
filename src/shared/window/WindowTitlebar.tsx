import { useEffect, useState, type ReactNode } from 'react';
import { currentWindowControls, type WindowControls } from './windowControls';

interface WindowTitlebarProps {
  actions?: ReactNode;
  controls?: WindowControls;
  showTitle?: boolean;
  title: string;
  variant?: 'overlay' | 'settings';
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

export function WindowTitlebar({
  actions,
  controls = currentWindowControls,
  showTitle = true,
  title,
  variant = 'overlay',
}: WindowTitlebarProps) {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    let mounted = true;
    let unlisten: () => void = () => undefined;
    const refresh = () => {
      void controls.isMaximized().then((value) => {
        if (mounted) setMaximized(value);
      });
    };
    refresh();
    void controls.onResized(refresh).then((next) => {
      unlisten = next;
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
    <header className={`window-titlebar window-titlebar--${variant}`}>
      <button
        aria-label={showTitle ? '拖动窗口或切换最大化' : `${title}窗口拖动区域`}
        className="window-titlebar__drag-region"
        type="button"
        onDoubleClick={toggleMaximized}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggleMaximized();
          }
        }}
        onPointerDown={(event) => {
          if (event.button === 0) void controls.startDragging();
        }}
      >
        {showTitle && <span>{title}</span>}
      </button>
      <nav className="window-titlebar__controls" aria-label="窗口控制">
        {actions}
        <button
          aria-label="最小化窗口"
          className="window-titlebar__button"
          type="button"
          onClick={() => void controls.minimize()}
        >
          <MinimizeIcon />
        </button>
        <button
          aria-label={maximized ? '还原窗口' : '最大化窗口'}
          className="window-titlebar__button"
          type="button"
          onClick={toggleMaximized}
        >
          <MaximizeIcon maximized={maximized} />
        </button>
        <button
          aria-label="关闭窗口"
          className="window-titlebar__button window-titlebar__button--close"
          type="button"
          onClick={() => void controls.close()}
        >
          <CloseIcon />
        </button>
      </nav>
    </header>
  );
}
