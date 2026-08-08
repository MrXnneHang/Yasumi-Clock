import { fireEvent, render, screen } from '@testing-library/react';
import { SessionAnimation } from './SessionAnimation';

describe('SessionAnimation', () => {
  it('uses idle, focus, and rest media according to the timer phase', () => {
    const { rerender } = render(
      <SessionAnimation phase={null} status="idle" />,
    );
    const idleAnimation = screen.getByLabelText('空闲动画');
    expect(idleAnimation.tagName).toBe('VIDEO');
    expect(idleAnimation).toHaveAttribute(
      'src',
      expect.stringContaining('/src/mp4/play.mp4'),
    );
    expect(idleAnimation).toHaveAttribute('loop');
    expect(idleAnimation).toHaveAttribute('autoplay');
    expect(idleAnimation).not.toHaveAttribute('poster');

    rerender(<SessionAnimation phase="focus" status="running" />);
    const focusAnimation = screen.getByLabelText('专注动画');
    expect(focusAnimation.tagName).toBe('VIDEO');
    expect(focusAnimation).toHaveAttribute(
      'src',
      expect.stringContaining('/src/mp4/work.mp4'),
    );
    expect(focusAnimation).toHaveAttribute('loop');

    rerender(<SessionAnimation phase="rest" status="running" />);
    const restAnimation = screen.getByLabelText('休息动画');
    expect(restAnimation.tagName).toBe('IMG');
    expect(restAnimation).toHaveAttribute(
      'src',
      expect.stringContaining('/src/img/mayi.gif'),
    );
    expect(restAnimation).not.toHaveAttribute('loop');
  });

  it('shows an accessible image fallback when media fails', () => {
    render(<SessionAnimation phase="focus" status="running" />);
    fireEvent.error(screen.getByLabelText('专注动画'));

    expect(
      screen.getByRole('img', { name: '专注动画不可用' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('动画暂不可用，计时仍在继续。'),
    ).toBeInTheDocument();
  });
});
