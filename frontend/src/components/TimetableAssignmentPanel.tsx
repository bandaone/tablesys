// OWNER: Cursor | TASK: T3 | DATE: 2026-02-19
import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Divider,
    FormControl,
    InputLabel,
    MenuItem,
    Select,
    SelectChangeEvent,
    Stack,
    Typography,
} from '@mui/material';
import { TimetableSlot } from './TimetableCell';
import { lecturersAPI, groupsAPI } from '../api';

interface LecturerOption {
    id: number;
    full_name: string;
}

interface GroupOption {
    id: number;
    name: string;
}

interface TimetableAssignmentPanelProps {
    slot: TimetableSlot | null;
}

/**
 * TimetableAssignmentPanel
 *
 * Right-hand side panel used in assignment mode to display details for the
 * currently selected slot and allow a coordinator to choose lecturer and
 * student groups. Persistence wiring is intentionally deferred until the
 * corresponding backend endpoints and API client helpers are available.
 */
const TimetableAssignmentPanel: React.FC<TimetableAssignmentPanelProps> = ({ slot }) => {
    const [lecturers, setLecturers] = useState<LecturerOption[]>([]);
    const [groups, setGroups] = useState<GroupOption[]>([]);
    const [selectedLecturerId, setSelectedLecturerId] = useState<number | ''>('');
    const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchOptions = async () => {
            try {
                setLoading(true);
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
                setLoading(false);
            }
        };

        fetchOptions();
    }, []);

    useEffect(() => {
        if (!slot) {
            setSelectedLecturerId('');
            setSelectedGroupIds([]);
            return;
        }

        setSelectedLecturerId('');
        setSelectedGroupIds([]);
    }, [slot]);

    const selectedLecturer = useMemo(
        () => lecturers.find((l) => l.id === selectedLecturerId),
        [lecturers, selectedLecturerId],
    );

    const handleLecturerChange = (event: SelectChangeEvent<number | ''>) => {
        const value = event.target.value;
        setSelectedLecturerId(value === '' ? '' : Number(value));
    };

    const handleGroupsChange = (event: SelectChangeEvent<number[]>) => {
        const {
            target: { value },
        } = event;
        setSelectedGroupIds(typeof value === 'string' ? value.split(',').map((id) => Number(id)) : value);
    };

    const handleSave = () => {
        // The actual persistence logic will be implemented once
        // the backend slot-assignment API and api.ts helper are available.
        // For now, keep this as a no-op to avoid cross-domain violations.
        // eslint-disable-next-line no-console
        console.log('Assignment payload (not yet persisted):', {
            slot,
            lecturer_id: selectedLecturerId || null,
            group_ids: selectedGroupIds,
        });
    };

    if (!slot) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography variant="subtitle1" color="text.secondary">
                    Select a timetable cell to assign a lecturer and student groups.
                </Typography>
            </Box>
        );
    }

    const saveDisabled = loading || !slot.slot_id;

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
                Day: <strong>{slot.day}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
                Time: <strong>{slot.start_time} - {slot.end_time}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
                Course: <strong>{slot.course_code}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
                Room: <strong>{slot.room}</strong>
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
                        value={selectedLecturerId}
                        onChange={handleLecturerChange}
                        disabled={loading}
                    >
                        <MenuItem value="">
                            <em>Unassigned</em>
                        </MenuItem>
                        {lecturers.map((lecturer) => (
                            <MenuItem key={lecturer.id} value={lecturer.id}>
                                {lecturer.full_name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>

                <FormControl fullWidth size="small">
                    <InputLabel id="groups-select-label">Student Groups</InputLabel>
                    <Select
                        labelId="groups-select-label"
                        label="Student Groups"
                        multiple
                        value={selectedGroupIds}
                        onChange={handleGroupsChange}
                        disabled={loading}
                        renderValue={(selected) => (
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                {selected.map((value) => {
                                    const group = groups.find((g) => g.id === value);
                                    return group ? (
                                        <Chip key={group.id} label={group.name} size="small" />
                                    ) : null;
                                })}
                            </Box>
                        )}
                    >
                        {groups.map((group) => (
                            <MenuItem key={group.id} value={group.id}>
                                {group.name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Stack>

            <Box sx={{ flexGrow: 1 }} />

            {saveDisabled && (
                <Alert severity="info" sx={{ mb: 1 }}>
                    Saving will be enabled once slot identifiers are exposed by the backend assignment API.
                </Alert>
            )}

            <Button
                variant="contained"
                color="primary"
                onClick={handleSave}
                disabled={saveDisabled}
            >
                Save Assignment
            </Button>

            {selectedLecturer && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                    Selected lecturer: {selectedLecturer.full_name}
                </Typography>
            )}
        </Box>
    );
};

export default TimetableAssignmentPanel;

