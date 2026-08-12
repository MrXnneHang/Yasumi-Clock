import { MainTitlebar } from './MainTitlebar';
import { mainWindowControls, type MainWindowControls } from './windowControls';
import { TimerPanel } from '../features/timer/TimerPanel';
import { useAnimationSettings } from '../features/timer/useAnimationSettings';
import { useTimerController } from '../features/timer/useTimerController';
import { desktopBridge, type DesktopBridge } from '../shared/ipc';
import { useThemeMode } from '../shared/theme/useThemeMode';

interface AppProps {
  bridge?: DesktopBridge;
  controls?: MainWindowControls;
}

export function App({
  bridge = desktopBridge,
  controls = mainWindowControls,
}: AppProps) {
  useThemeMode(bridge);
  const controller = useTimerController(bridge);
  const animations = useAnimationSettings(bridge);
  const settingsAvailable =
    controller.snapshot?.allowedActions.includes('changeSettings') ?? false;

  return (
    <main className="main-window">
      <MainTitlebar
        bridge={bridge}
        controls={controls}
        settingsAvailable={settingsAvailable}
      />
      {controller.loading ? (
        <section className="app-state app-state--loading">
          <p role="status">正在连接计时核心…</p>
        </section>
      ) : !controller.snapshot ? (
        <section className="app-state app-state--loading">
          <div className="error-banner" role="alert">
            <strong>计时核心暂不可用</strong>
            <span>
              {controller.error?.message ?? '请重新启动 Yasumi Clock。'}
            </span>
          </div>
        </section>
      ) : (
        <TimerPanel
          animations={animations}
          bridge={bridge}
          error={controller.error?.message}
          pending={controller.pending}
          run={controller.run}
          snapshot={controller.snapshot}
          onClearError={controller.clearError}
        />
      )}
    </main>
  );
}
