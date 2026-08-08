import { TimerPanel } from '../features/timer/TimerPanel';
import { useAnimationSettings } from '../features/timer/useAnimationSettings';
import { useTimerController } from '../features/timer/useTimerController';
import { desktopBridge, type DesktopBridge } from '../shared/ipc';

interface AppProps {
  bridge?: DesktopBridge;
}

export function App({ bridge = desktopBridge }: AppProps) {
  const controller = useTimerController(bridge);
  const animations = useAnimationSettings(bridge);

  if (controller.loading) {
    return (
      <main className="app-shell app-shell--loading">
        <p role="status">正在连接计时核心…</p>
      </main>
    );
  }

  if (!controller.snapshot) {
    return (
      <main className="app-shell app-shell--loading">
        <div className="error-banner" role="alert">
          <strong>计时核心暂不可用</strong>
          <span>
            {controller.error?.message ?? '请重新启动 Yasumi Clock。'}
          </span>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      {controller.error && (
        <div className="error-banner error-banner--floating" role="alert">
          <span>{controller.error.message}</span>
          <button type="button" onClick={controller.clearError}>
            关闭
          </button>
        </div>
      )}
      <div className="app-layout">
        <TimerPanel
          animations={animations}
          bridge={bridge}
          pending={controller.pending}
          run={controller.run}
          snapshot={controller.snapshot}
        />
      </div>
    </main>
  );
}
