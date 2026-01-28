import { render, screen, fireEvent } from '@testing-library/react';
import { QueryInput } from './QueryInput';

describe('QueryInput', () => {
  it('renders input field', () => {
    render(<QueryInput onSubmit={() => {}} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('calls onSubmit when button clicked', () => {
    const handleSubmit = vi.fn();
    render(<QueryInput onSubmit={handleSubmit} />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Test query' } });
    fireEvent.click(screen.getByRole('button'));

    expect(handleSubmit).toHaveBeenCalledWith('Test query');
  });

  it('clears input after submit', () => {
    render(<QueryInput onSubmit={() => {}} />);

    const input = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: 'Test query' } });
    fireEvent.click(screen.getByRole('button'));

    expect(input.value).toBe('');
  });

  it('disables submit when loading', () => {
    render(<QueryInput onSubmit={() => {}} isLoading />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Test query' } });

    expect(screen.getByRole('button')).toBeDisabled();
  });
});
