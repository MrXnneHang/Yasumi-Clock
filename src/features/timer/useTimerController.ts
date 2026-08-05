import { useCallback, useEffect, useState } from 'react';
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
  run(command: () => Promise<TimerSnapshot>): Promise<void>;
  clearError(): void;
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

  useEffect(() => {
    let mounted = true;
    let unsubscribe: (() => void) | undefined;
    bridge
      .subscribeToTimer((next) => {
        if (mounted) {
          setSnapshot((current) =>
            current && next.revision < current.revision ? current : next,
          );
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

  const run = useCallback(async (command: () => Promise<TimerSnapshot>) => {
    setPending(true);
    setError(null);
    try {
      const next = await command();
      setSnapshot((current) =>
        current && next.revision < current.revision ? current : next,
      );
    } catch (cause) {
      setError(normalizeError(cause));
    } finally {
      setPending(false);
    }
  }, []);

  return {
    snapshot,
    loading,
    pending,
    error,
    run,
    clearError: () => setError(null),
  };
}
