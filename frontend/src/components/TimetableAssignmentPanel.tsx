import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Divider,
    FormControl,
    InputLabel,
    MenuItem,
    Select,
    SelectChangeEvent,
    Snackbar,
    Stack,
    Typography,
} from '@mui/material';
import { TimetableSlot } from './TimetableCell';
import { groupsAPI, lecturersAPI, timetablesAPI } from '../api';
import { formatGroupLabel, formatPersonName } from '../utils/displayFormatters';

interface LecturerOption {
    id: number;
    full_name: string;
}

interface GroupOption {
    id: number;
    name: string;
}

interface TimetableAssignmentPanelProps {
    selectedSlot: TimetableSlot | null;
    onSlotSelect: (slot: TimetableSlot | null) => void;
    onAssignmentComplete?: () => void;
}

/**
 * TimetableAssignmentPanel
 *
 * Right-hand side panel used in assignment mode to display details for the
 * currently selected slot and allow a coordinator to choose lecturer and
 * student groups. Persistence wiring is intentionally deferred until the
 * corresponding backend endpoints and API client helpers are available.
 */
const TimetableAssignmentPanel: React.FC<TimetableAssignmentPanelProps> = ({
    selectedSlot,
    onSlotSelect,
    onAssignmentComplete,
}) => {
    const [lecturers, setLecturers] = useState<LecturerOption[]>([]);
    const [groups, setGroups] = useState<GroupOption[]>([]);
    const [selectedLecturerId, setSelectedLecturerId] = useState<number | null>(null);
    const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
    const [optionsLoading, setOptionsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [loading, setLoading] = useState(false);
    const [snackbar, setSnackbar] = useState({
        open: false,
        message: '',
        severity: 'success' as 'success' | 'error',
    });

    useEffect(() => {
        const fetchOptions = async () => {
            try {
                setOptionsLoading(true);
                setError(null);

                const [lecturerList, groupList] = await Promise.all([
                    lecturersAPI.getAll(),
                    groupsAPI.getAll(),
                ]);

                setLecturers(
                    lecturerList.map((item: { id: number; full_name: string }) => ({
                        id: item.id,
                        full_name: item.full_name,
                    })),
                );

                setGroups(
                    groupList.map((item: { id: number; name: string }) => ({
                        id: item.id,
                        name: item.name,
                    })),
                );
            } catch (err) {
                setError('Failed to load lecturers and groups. Please try again.');
            } finally {
                setOptionsLoading(false);
            }
        };

        fetchOptions();
    }, []);

    useEffect(() => {
        if (!selectedSlot) {
            setSelectedLecturerId(null);
            setSelectedGroupId(null);
            return;
        }

        setSelectedLecturerId(null);
        setSelectedGroupId(null);
    }, [selectedSlot]);

    const selectedLecturer = useMemo(
        () => lecturers.find((l) => l.id === selectedLecturerId),
        [lecturers, selectedLecturerId],
    );

    const selectedGroup = useMemo(
        () => groups.find((g) => g.id === selectedGroupId),
        [groups, selectedGroupId],
    );

    const handleLecturerChange = (event: SelectChangeEvent<number | ''>) => {
        const value = event.target.value;
        setSelectedLecturerId(value === '' ? null : Number(value));
    };

    const handleSaveAssignment = async () => {
        if (!selectedSlot?.slot_id) {
            setSnackbar({
                open: true,
                message: 'No slot selected',
                severity: 'error',
            });
            return;
        }

        if (!selectedLecturerId) {
            setSnackbar({
                open: true,
                message: 'Please select a lecturer',
                severity: 'error',
            });
            return;
        }

        if (!selectedGroupId) {
            setSnackbar({
                open: true,
                message: 'Please select a student group',
                severity: 'error',
            });
            return;
        }

        try {
            setLoading(true);

            await timetablesAPI.assignSlot(selectedSlot.slot_id, {
                lecturer_id: selectedLecturerId,
                group_id: selectedGroupId,
            });

            setSnackbar({
                open: true,
                message: 'Assignment saved successfully',
                severity: 'success',
            });

            onSlotSelect(null);

            if (onAssignmentComplete) {
                onAssignmentComplete();
            }
        } catch (error: any) {
            let message = 'Failed to save assignment';

            if (error.response?.status === 404) {
                message = 'Time slot not found';
            } else if (error.response?.status === 422) {
                message = 'Invalid lecturer or group selection';
            } else if (error.response?.status === 403) {
                message = 'You do not have permission to assign slots';
            } else if (error.response?.data?.detail) {
                message = error.response.data.detail;
            }

            setSnackbar({
                open: true,
                message,
                severity: 'error',
            });
        } finally {
            setLoading(false);
        }
    };

    if (!selectedSlot) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography variant="subtitle1" color="text.secondary">
                    Select a timetable cell to assign a lecturer and student groups.
                </Typography>
                <Snackbar
                    open={snackbar.open}
                    autoHideDuration={6000}
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                >
                    <Alert
                        severity={snackbar.severity}
                        onClose={() => setSnackbar({ ...snackbar, open: false })}
                    >
                        {snackbar.message}
                    </Alert>
                </Snackbar>
            </Box>
        );
    }

    const saveDisabled = loading || !selectedLecturerId || !selectedGroupId;

    return (
        <Box
            sx={{
                borderLeft: (theme) => `1px solid ${theme.palette.divider}`,
                p: 3,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
            }}
        >
            <Typography variant="h6" fontWeight={600}>
                Assignment Details
            </Typography>

            <Typography variant="body2" color="text.secondary">
                Day: <strong>{selectedSlot.day}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
                Time: <strong>{selectedSlot.start_time} - {selectedSlot.end_time}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
                Course: <strong>{selectedSlot.course_code}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
                Room: <strong>{selectedSlot.room}</strong>
            </Typography>

            <Divider sx={{ my: 1 }} />

            {error && (
                <Alert severity="error">
                    {error}
                </Alert>
            )}

            <Stack spacing={2}>
                <FormControl fullWidth size="small">
                    <InputLabel id="lecturer-select-label">Lecturer</InputLabel>
                    <Select
                        labelId="lecturer-select-label"
                        label="Lecturer"
                        value={selectedLecturerId ?? ''}
                        onChange={handleLecturerChange}
                        disabled={optionsLoading || loading}
                    >
                        <MenuItem value="">
                            <em>Unassigned</em>
                        </MenuItem>
                        {lecturers.map((lecturer) => (
                            <MenuItem key={lecturer.id} value={lecturer.id}>
                                {formatPersonName(lecturer.full_name)}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>

                <FormControl fullWidth size="small">
                    <InputLabel id="groups-select-label">Student Group</InputLabel>
                    <Select
                        labelId="groups-select-label"
                        label="Student Group"
                        value={selectedGroupId ?? ''}
                        onChange={(event: SelectChangeEvent<number>) =>
                            setSelectedGroupId(event.target.value as number)
                        }
                        disabled={optionsLoading || loading}
                    >
                        <MenuItem value="">
                            <em>Unassigned</em>
                        </MenuItem>
                        {groups.map((group) => (
                            <MenuItem key={group.id} value={group.id}>
                                {formatGroupLabel(group)}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Stack>

            <Box sx={{ flexGrow: 1 }} />

            {!selectedSlot.slot_id && (
                <Alert severity="info" sx={{ mb: 1 }}>
                    Saving requires a slot identifier. Please refresh and ensure the backend is returning `slot_id` in the timetable view API.
                </Alert>
            )}

            <Button
                variant="contained"
                color="primary"
                fullWidth
                onClick={handleSaveAssignment}
                disabled={saveDisabled}
                startIcon={loading ? <CircularProgress size={20} /> : null}
            >
                {loading ? 'Saving...' : 'Save Assignment'}
            </Button>

            {selectedLecturer && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                    Selected lecturer: {formatPersonName(selectedLecturer.full_name)}
                </Typography>
            )}

            {selectedGroup && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                    Selected group: {selectedGroup.name}
                </Typography>
            )}

            <Snackbar
                open={snackbar.open}
                autoHideDuration={6000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            >
                <Alert
                    severity={snackbar.severity}
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default TimetableAssignmentPanel;

