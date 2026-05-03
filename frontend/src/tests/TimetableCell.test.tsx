import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import TimetableCell from '../components/TimetableCell';

describe('TimetableCell', () => {
    it('renders empty cell when no slot is provided', () => {
        const { container } = render(<TimetableCell />);
        // Checking for the CSS class or aria-label
        const emptyCell = container.querySelector('.empty-cell');
        expect(emptyCell).toBeInTheDocument();
        expect(emptyCell).toHaveAttribute('aria-label', 'No class scheduled');
    });

    it('renders slot details correctly when props are provided', () => {
        const mockSlot = {
            day: 'Monday',
            start_time: '08:00',
            end_time: '10:00',
            course_code: 'CS101',
            room: 'LH1',
            lecturer: 'Dr. Turing',
        };

        render(<TimetableCell slot={mockSlot} />);

        // Check if course code is rendered
        expect(screen.getByText('CS101')).toBeInTheDocument();
        // Check if room is rendered
        expect(screen.getByText('LH1')).toBeInTheDocument();
        // Check if lecturer is rendered
        expect(screen.getByText('Dr. Turing')).toBeInTheDocument();
    });

    it('handles clicking when onClick prop is passed', () => {
        const mockSlot = {
            day: 'Monday',
            start_time: '10:00',
            end_time: '12:00',
            course_code: 'ENG200',
            room: 'Room 20',
        };
        const mockOnClick = vi.fn();

        render(<TimetableCell slot={mockSlot} onClick={mockOnClick} />);

        // Find the cell bounding box
        const cell = screen.getByRole('listitem');
        fireEvent.click(cell);

        expect(mockOnClick).toHaveBeenCalledTimes(1);
        expect(mockOnClick).toHaveBeenCalledWith(mockSlot);
    });

    it('renders shared group visualization when multiple groups are assigned', () => {
        const mockSlot = {
            day: 'Tuesday',
            start_time: '14:00',
            end_time: '16:00',
            course_code: 'PHY100',
            room: 'Main Lab',
            shared_group_ids: [1, 2, 3],
            combined_size: 150
        };

        render(<TimetableCell slot={mockSlot} />);
        
        expect(screen.getByText('Shared (150 students)')).toBeInTheDocument();
    });
});
