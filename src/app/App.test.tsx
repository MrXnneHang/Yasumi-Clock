import { render, screen } from '@testing-library/react';
import { App } from './App';

describe('App', () => {
  it('renders the migration scaffold without product controls', () => {
    render(<App />);

    expect(
      screen.getByRole('heading', { name: 'Yasumi Clock' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('桌面基础工程已就绪');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
