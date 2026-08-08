import { useEffect, useState } from 'react';
import {
  desktopBridge,
  type AnimationSettings,
  type DesktopBridge,
} from '../../shared/ipc';

export const defaultAnimationSettings: AnimationSettings = {
  idle: { kind: 'builtin', id: 'play' },
  focus: { kind: 'builtin', id: 'work' },
  rest: { kind: 'builtin', id: 'mayi' },
  restPlayback: 'once',
};

export function useAnimationSettings(
  bridge: DesktopBridge = desktopBridge,
): AnimationSettings {
  const [animations, setAnimations] = useState(defaultAnimationSettings);

  useEffect(() => {
    let mounted = true;
    let unsubscribe: () => void = () => undefined;
    bridge
      .subscribeToSettings(({ settings }) => {
        if (mounted) {
          setAnimations(settings.animations);
        }
      })
      .then((subscription) => {
        unsubscribe = subscription.unsubscribe;
      })
      .catch(() => undefined);

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, [bridge]);

  return animations;
}
