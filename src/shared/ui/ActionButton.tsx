import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  tone?: 'primary' | 'secondary' | 'danger';
}

export function ActionButton({
  children,
  className = '',
  tone = 'secondary',
  type = 'button',
  ...props
}: ActionButtonProps) {
  return (
    <button
      className={`action-button action-button--${tone} ${className}`.trim()}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}
