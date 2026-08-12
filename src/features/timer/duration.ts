const MIN_FOCUS_MINUTES = 0;
const MAX_FOCUS_MINUTES = 60;

function validateFocusMinutes(minutes: number) {
  if (
    !Number.isInteger(minutes) ||
    minutes < MIN_FOCUS_MINUTES ||
    minutes > MAX_FOCUS_MINUTES
  ) {
    throw new RangeError('focus minutes must be an integer from 0 to 60');
  }
}

export function focusDurationSeconds(minutes: number) {
  validateFocusMinutes(minutes);
  return minutes === 0 ? 1 : minutes * 60;
}

export function deriveRestDurationMinutes(focusMinutes: number) {
  validateFocusMinutes(focusMinutes);
  return 5 + Math.ceil(Math.max(focusMinutes - 25, 0) / 5);
}

export function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${remainder
    .toString()
    .padStart(2, '0')}`;
}
