type TimerActionIconName = 'play' | 'pause' | 'stop';

interface TimerActionIconProps {
  name: TimerActionIconName;
}

export function TimerActionIcon({ name }: TimerActionIconProps) {
  return (
    <svg aria-hidden="true" className="timer-action-icon" viewBox="0 0 24 24">
      {name === 'play' && <path d="M8 5.6v12.8L18.5 12 8 5.6Z" />}
      {name === 'pause' && <path d="M7 5h3.5v14H7V5Zm6.5 0H17v14h-3.5V5Z" />}
      {name === 'stop' && <path d="M6 6h12v12H6V6Z" />}
    </svg>
  );
}
