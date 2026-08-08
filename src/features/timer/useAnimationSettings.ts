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
    bridge
      .getSettings()
      .then((settings) => {
        if (mounted) {
          setAnimations(settings.animations);
        }
      })
      .catch(() => undefined);

    return () => {
      mounted = false;
    };
  }, [bridge]);

  return animations;
}
