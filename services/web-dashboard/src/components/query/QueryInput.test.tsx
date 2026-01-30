import { describe, it, expect, vi } from 'vitest';
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
    // Get the submit button (the one with the Send icon, not the Attach button)
    const buttons = screen.getAllByRole('button');
    const submitButton = buttons.find(btn => !btn.getAttribute('title')?.includes('Attach'));
    fireEvent.click(submitButton!);

    expect(handleSubmit).toHaveBeenCalledWith('Test query');
  });

  it('clears input after submit', () => {
    render(<QueryInput onSubmit={() => {}} />);

    const input = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: 'Test query' } });
    const buttons = screen.getAllByRole('button');
    const submitButton = buttons.find(btn => !btn.getAttribute('title')?.includes('Attach'));
    fireEvent.click(submitButton!);

    expect(input.value).toBe('');
  });

  it('disables submit when loading', () => {
    render(<QueryInput onSubmit={() => {}} isLoading />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Test query' } });

    const buttons = screen.getAllByRole('button');
    const submitButton = buttons.find(btn => !btn.getAttribute('title')?.includes('Attach'));
    expect(submitButton).toBeDisabled();
  });
});
