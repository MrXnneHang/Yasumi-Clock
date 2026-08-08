import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnimationSettings } from '../../shared/ipc';
import { defaultAnimationSettings } from './useAnimationSettings';
import { SessionAnimation } from './SessionAnimation';

const importedMp4: AnimationSettings = {
  ...defaultAnimationSettings,
  focus: { kind: 'imported', id: '93c59dcf-4d9c-4a91-8722-e0b5cd6ecbd9', format: 'mp4' },
  rest: { kind: 'imported', id: '0d473d60-0713-4f62-bac5-2ab62046dbdc', format: 'mp4' },
  restPlayback: 'loop',
};

const importedGif: AnimationSettings = {
  ...importedMp4,
  rest: { kind: 'imported', id: 'bf22abf9-0ad3-4d52-9efc-f188c376b2cd', format: 'gif' },
};

describe('SessionAnimation', () => {
  beforeEach(() => {
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: {
        convertFileSrc: vi.fn(
          (id: string, protocol: string) => `http://${protocol}.localhost/${id}`,
        ),
      },
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(window, '__TAURI_INTERNALS__');
  });

  it('uses idle, focus, and rest builtins according to the timer phase', () => {
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

    rerender(<SessionAnimation phase="focus" status="running" />);
    const focusAnimation = screen.getByLabelText('专注动画');
    expect(focusAnimation.tagName).toBe('VIDEO');
    expect(focusAnimation).toHaveAttribute(
      'src',
      expect.stringContaining('/src/mp4/work.mp4'),
    );

    rerender(<SessionAnimation phase="rest" status="running" />);
    const restAnimation = screen.getByLabelText('休息动画');
    expect(restAnimation.tagName).toBe('IMG');
    expect(restAnimation).toHaveAttribute(
      'src',
      expect.stringContaining('/src/img/mayi.gif'),
    );
  });

  it('resolves imported MP4 files through the dedicated protocol', () => {
    render(
      <SessionAnimation
        animations={importedMp4}
        phase="focus"
        status="running"
      />,
    );

    expect(screen.getByLabelText('专注动画')).toHaveAttribute(
      'src',
      'http://yasumi-media.localhost/93c59dcf-4d9c-4a91-8722-e0b5cd6ecbd9',
    );
  });

  it('uses video loop mode for rest MP4 and preserves GIF metadata', () => {
    const { rerender } = render(
      <SessionAnimation animations={importedMp4} phase="rest" status="running" />,
    );
    expect(screen.getByLabelText('休息动画')).toHaveAttribute('loop');

    rerender(
      <SessionAnimation animations={importedGif} phase="rest" status="running" />,
    );
    expect(screen.getByLabelText('休息动画').tagName).toBe('IMG');
    expect(screen.getByLabelText('休息动画')).not.toHaveAttribute('loop');
  });

  it('clears a media failure after the source changes', () => {
    const { rerender } = render(
      <SessionAnimation animations={importedMp4} phase="focus" status="running" />,
    );
    fireEvent.error(screen.getByLabelText('专注动画'));
    expect(screen.getByRole('img', { name: '专注动画不可用' })).toBeInTheDocument();

    rerender(
      <SessionAnimation animations={defaultAnimationSettings} phase="focus" status="running" />,
    );
    expect(screen.getByLabelText('专注动画')).toBeInTheDocument();
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
