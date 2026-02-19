// OWNER: Cursor | TASK: T3 | DATE: 2026-02-19
import React, { useCallback, useEffect, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    ButtonGroup,
    CircularProgress,
    MenuItem,
    Select,
    SelectChangeEvent,
    ToggleButton,
    ToggleButtonGroup,
    Typography,
} from '@mui/material';
import TimetableGrid from '../components/TimetableGrid';
import TimetableAssignmentPanel from '../components/TimetableAssignmentPanel';
import { TimetableSlot } from '../components/TimetableCell';
import api from '../api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TimetableMetadata {
    term: string;
    year: number;
    total_courses: number;
}

interface TimetableViewData {
    metadata: TimetableMetadata;
    slots: TimetableSlot[];
}

type ViewMode = 'view' | 'assign';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const YEAR_OPTIONS: { value: number; label: string }[] = [
    { value: 2, label: '2nd Year' },
    { value: 3, label: '3rd Year' },
    { value: 4, label: '4th Year' },
    { value: 5, label: '5th Year' },
];

const PROGRAM_OPTIONS: { value: string; label: string }[] = [
    { value: 'ALL', label: 'All Programs' },
    { value: 'AEN', label: 'Agricultural Engineering' },
    { value: 'CEE', label: 'Civil Engineering' },
    { value: 'EEE', label: 'Electrical Engineering' },
    { value: 'GEE', label: 'Geomatics Engineering' },
    { value: 'MEC', label: 'Mechanical Engineering' },
];

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

/**
 * TimetableViewPage
 *
 * Renders the timetable grid view for the School of Engineering.
 * Users can filter by year level and program. Data is fetched from
 * GET /api/timetables/view with query parameters.
 *
 * In "Assign" mode, coordinators can click on timetable cells to
 * prepare lecturer and group assignments. Persistence will be wired
 * once the backend exposes slot identifiers and assignment endpoints.
 */
const TimetableViewPage: React.FC = () => {
    const [selectedYear, setSelectedYear] = useState<number>(5);
    const [selectedProgram, setSelectedProgram] = useState<string>('ALL');
    const [data, setData] = useState<TimetableViewData | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [mode, setMode] = useState<ViewMode>('view');
    const [selectedSlot, setSelectedSlot] = useState<TimetableSlot | null>(null);

    const fetchTimetable = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.get<TimetableViewData>('/api/timetables/view', {
                params: {
                    year: selectedYear,
                    program: selectedProgram,
                },
            });
            setData(response.data);
            setSelectedSlot(null);
        } catch (err: unknown) {
            const message =
                err instanceof Error
                    ? err.message
                    : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                    'Failed to load timetable data.';
            setError(message);
        } finally {
            setLoading(false);
        }
    }, [selectedYear, selectedProgram]);

    useEffect(() => {
        fetchTimetable();
    }, [fetchTimetable]);

    const handleYearSelect = (year: number) => {
        setSelectedYear(year);
    };

    const handleProgramChange = (event: SelectChangeEvent<string>) => {
        setSelectedProgram(event.target.value);
    };

    const handleModeChange = (_event: React.MouseEvent<HTMLElement>, newMode: ViewMode | null) => {
        if (!newMode) {
            return;
        }
        setMode(newMode);
        if (newMode === 'view') {
            setSelectedSlot(null);
        }
    };

    const handleSlotClick = (slot: TimetableSlot) => {
        setSelectedSlot(slot);
    };

    const hasSlots = !!data && data.slots.length > 0;

    return (
        <Box sx={{ padding: 3 }}>
            {/* Page Header */}
            <Typography variant="h5" fontWeight={700} gutterBottom>
                UNZA School of Engineering Timetable
            </Typography>

            {data?.metadata && (
                <Typography variant="body2" color="text.secondary" gutterBottom>
                    {data.metadata.term} {data.metadata.year}&nbsp;&mdash;&nbsp;
                    {data.metadata.total_courses} course{data.metadata.total_courses !== 1 ? 's' : ''}
                </Typography>
            )}

            {/* Filter Bar */}
            <Box className="timetable-filter-bar" sx={{ mt: 2, mb: 1, alignItems: 'flex-end' }}>
                <Box className="timetable-filter-group">
                    <Typography className="timetable-filter-label" variant="caption">
                        Year Level
                    </Typography>
                    <ButtonGroup variant="outlined" size="small" aria-label="Select year level">
                        {YEAR_OPTIONS.map(({ value, label }) => (
                            <Button
                                key={value}
                                variant={selectedYear === value ? 'contained' : 'outlined'}
                                onClick={() => handleYearSelect(value)}
                                aria-pressed={selectedYear === value}
                                disableElevation
                            >
                                {label}
                            </Button>
                        ))}
                    </ButtonGroup>
                </Box>

                <Box className="timetable-filter-group" sx={{ minWidth: 220 }}>
                    <Typography className="timetable-filter-label" variant="caption">
                        Program
                    </Typography>
                    <Select
                        value={selectedProgram}
                        onChange={handleProgramChange}
                        size="small"
                        fullWidth
                        inputProps={{ 'aria-label': 'Select program' }}
                    >
                        {PROGRAM_OPTIONS.map(({ value, label }) => (
                            <MenuItem key={value} value={value}>
                                {label}
                            </MenuItem>
                        ))}
                    </Select>
                </Box>

                <Box sx={{ flexGrow: 1 }} />

                <Box className="timetable-filter-group">
                    <Typography className="timetable-filter-label" variant="caption">
                        Mode
                    </Typography>
                    <ToggleButtonGroup
                        size="small"
                        value={mode}
                        exclusive
                        onChange={handleModeChange}
                        aria-label="Timetable mode"
                    >
                        <ToggleButton value="view" aria-label="View mode">
                            View
                        </ToggleButton>
                        <ToggleButton value="assign" aria-label="Assignment mode" disabled={!hasSlots}>
                            Assign
                        </ToggleButton>
                    </ToggleButtonGroup>
                </Box>
            </Box>

            {/* Loading State */}
            {loading && (
                <Box
                    sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 6 }}
                    aria-label="Loading timetable"
                    aria-busy="true"
                >
                    <CircularProgress />
                </Box>
            )}

            {/* Error State */}
            {!loading && error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                    {error}
                </Alert>
            )}

            {/* Empty State */}
            {!loading && !error && data && data.slots.length === 0 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                    No timetable data found for {selectedYear === 2 ? '2nd' : selectedYear === 3 ? '3rd' : `${selectedYear}th`} Year
                    {selectedProgram !== 'ALL' ? ` — ${selectedProgram}` : ''}.
                    Import timetable data or adjust filters.
                </Alert>
            )}

            {/* Timetable Grid + Assignment Panel */}
            {!loading && !error && data && data.slots.length > 0 && (
                <Box sx={{ display: 'flex', mt: 2 }}>
                    <Box sx={{ flex: 3, pr: 2 }}>
                        <TimetableGrid
                            slots={data.slots}
                            mode={mode}
                            onSlotClick={handleSlotClick}
                            selectedSlot={selectedSlot}
                        />
                    </Box>
                    {mode === 'assign' && (
                        <Box sx={{ flex: 2, minWidth: 320 }}>
                            <TimetableAssignmentPanel slot={selectedSlot} />
                        </Box>
                    )}
                </Box>
            )}
        </Box>
    );
};

export default TimetableViewPage;
