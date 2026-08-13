import { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import {
  desktopBridge,
  type CommandError,
  type DesktopBridge,
  type TimerSnapshot,
} from '../../shared/ipc';

interface TimerController {
  snapshot: TimerSnapshot | null;
  loading: boolean;
  pending: boolean;
  error: CommandError | null;
  run(
    command: () => Promise<TimerSnapshot>,
    options?: { transition?: boolean },
  ): Promise<void>;
  clearError(): void;
}

function prefersReducedMotion() {
  return (
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  );
}

function newerSnapshot(
  first: TimerSnapshot,
  second: TimerSnapshot | null,
): TimerSnapshot {
  return second && second.revision > first.revision ? second : first;
}

function normalizeError(error: unknown): CommandError {
  if (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    'message' in error
  ) {
    return error as CommandError;
  }
  return {
    code: 'unexpected_error',
    message: error instanceof Error ? error.message : String(error),
    retryable: false,
  };
}

export function useTimerController(
  bridge: DesktopBridge = desktopBridge,
): TimerController {
  const [snapshot, setSnapshot] = useState<TimerSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<CommandError | null>(null);
  const transitionPending = useRef(false);
  const deferredSnapshot = useRef<TimerSnapshot | null>(null);

  useEffect(() => {
    let mounted = true;
    let unsubscribe: (() => void) | undefined;
    bridge
      .subscribeToTimer((next) => {
        if (mounted) {
          if (transitionPending.current) {
            deferredSnapshot.current = deferredSnapshot.current
              ? newerSnapshot(deferredSnapshot.current, next)
              : next;
          } else {
            setSnapshot((current) =>
              current && next.revision < current.revision ? current : next,
            );
          }
          setLoading(false);
        }
      })
      .then((subscription) => {
        if (mounted) {
          unsubscribe = subscription.unsubscribe;
        } else {
          subscription.unsubscribe();
        }
      })
      .catch((cause) => {
        if (mounted) {
          setError(normalizeError(cause));
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
      unsubscribe?.();
    };
  }, [bridge]);

  const run = useCallback(
    async (
      command: () => Promise<TimerSnapshot>,
      options: { transition?: boolean } = {},
    ) => {
      const useTransition = options.transition === true;
      if (useTransition) {
        transitionPending.current = true;
        deferredSnapshot.current = null;
      }
      setPending(true);
      setError(null);
      try {
        const commandSnapshot = await command();
        const next = newerSnapshot(commandSnapshot, deferredSnapshot.current);
        const canTransition =
          useTransition &&
          !prefersReducedMotion() &&
          typeof document.startViewTransition === 'function';
        const update = () => {
          flushSync(() => {
            setSnapshot((current) =>
              current && next.revision < current.revision ? current : next,
            );
            setPending(false);
          });
        };
        if (canTransition) {
          const transition = document.startViewTransition(update);
          await transition?.updateCallbackDone;
        } else {
          update();
        }
      } catch (cause) {
        const next = deferredSnapshot.current;
        if (next) {
          setSnapshot((current) =>
            current && next.revision < current.revision ? current : next,
          );
        }
        setError(normalizeError(cause));
        setPending(false);
      } finally {
        transitionPending.current = false;
        deferredSnapshot.current = null;
      }
    },
    [],
  );

  return {
    snapshot,
    loading,
    pending,
    error,
    run,
    clearError: () => setError(null),
  };
}
