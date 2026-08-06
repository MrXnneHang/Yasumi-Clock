import { fireEvent, render, screen } from '@testing-library/react';
import { SessionAnimation } from './SessionAnimation';

describe('SessionAnimation', () => {
  it('uses focus and break media according to the Rust phase', () => {
    const { rerender } = render(
      <SessionAnimation phase="focus" status="running" />,
    );
    expect(screen.getByLabelText('专注动画')).toHaveAttribute(
      'src',
      expect.stringContaining('/src/mp4/work.mp4'),
    );

    rerender(<SessionAnimation phase="shortBreak" status="running" />);
    expect(screen.getByLabelText('休息动画')).toHaveAttribute(
      'src',
      expect.stringContaining('/src/mp4/play.mp4'),
    );
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
