import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DurationDock } from './DurationDock';

describe('DurationDock', () => {
  it('keeps the controlled duration slider and rest estimate visible', () => {
    const onChange = vi.fn();
    render(<DurationDock minutes={26} pending={false} onChange={onChange} />);

    expect(screen.getByLabelText('剩余时间 26:00')).toBeInTheDocument();
    expect(screen.getByText('预计休息 6 分钟')).toBeInTheDocument();
    const slider = screen.getByRole('slider', { name: '本次专注时长' });
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '60');
    expect(slider).toHaveAttribute('step', '1');

    fireEvent.change(slider, { target: { value: '31' } });
    expect(onChange).toHaveBeenCalledWith(31);
  });

  it('describes the zero-minute edge case and disables pending changes', () => {
    render(<DurationDock minutes={0} pending onChange={vi.fn()} />);

    expect(screen.getByLabelText('剩余时间 00:01')).toBeInTheDocument();
    expect(screen.getByText('实际计时 1 秒')).toBeInTheDocument();
    const slider = screen.getByRole('slider', { name: '本次专注时长' });
    expect(slider).toBeDisabled();
    expect(slider).toHaveAttribute('aria-valuetext', '0 分钟，实际计时 1 秒');
  });
});
