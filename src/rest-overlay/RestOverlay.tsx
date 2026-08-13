import { SessionAnimation } from '../features/timer/SessionAnimation';
import { useAnimationSettings } from '../features/timer/useAnimationSettings';
import { useTimerController } from '../features/timer/useTimerController';
import { desktopBridge, type DesktopBridge } from '../shared/ipc';
import { useThemeMode } from '../shared/theme/useThemeMode';

interface RestOverlayProps {
  bridge?: DesktopBridge;
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${remainder
    .toString()
    .padStart(2, '0')}`;
}

export function RestOverlay({ bridge = desktopBridge }: RestOverlayProps) {
  useThemeMode(bridge);
  const controller = useTimerController(bridge);
  const animations = useAnimationSettings(bridge);

  if (controller.loading) {
    return (
      <main className="rest-overlay rest-overlay--loading">
        <p role="status">正在连接休息计时…</p>
      </main>
    );
  }

  if (controller.snapshot?.phase !== 'rest') {
    return (
      <main className="rest-overlay rest-overlay--loading">
        <p>休息已结束</p>
      </main>
    );
  }

  const canEnd = controller.snapshot.allowedActions.includes('end');

  return (
    <main className="rest-overlay" aria-labelledby="rest-overlay-heading">
      <div className="rest-overlay__media">
        <SessionAnimation
          animations={animations}
          phase="rest"
          status={controller.snapshot.status}
        />
      </div>
      <section className="rest-overlay__content">
        <p className="rest-overlay__eyebrow">Yasumi Clock</p>
        <h1 id="rest-overlay-heading">休息中</h1>
        <output
          className="rest-overlay__timer"
          aria-label={`剩余时间 ${formatTime(controller.snapshot.remainingSeconds)}`}
        >
          {formatTime(controller.snapshot.remainingSeconds)}
        </output>
        <p className="rest-overlay__hint">暂时放下，呼吸一下。</p>
        {controller.error && (
          <div className="rest-overlay__error" role="alert">
            {controller.error.message}
          </div>
        )}
        <button
          className="rest-overlay__end"
          type="button"
          disabled={!canEnd || controller.pending}
          onClick={() => controller.run(() => bridge.endRest())}
        >
          结束休息
        </button>
      </section>
    </main>
  );
}
