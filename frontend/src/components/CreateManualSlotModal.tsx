import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    Alert,
    CircularProgress,
    Grid
} from '@mui/material';
import { timetablesAPI, coursesAPI, lecturersAPI, roomsAPI, groupsAPI } from '../api';
import { useInstitutionSetup } from '../hooks/useInstitutionSetup';
import { formatGroupName, formatPersonName, formatRoomName } from '../utils/displayFormatters';

interface CreateManualSlotModalProps {
    open: boolean;
    onClose: () => void;
    onSuccess: () => void;
    timetableId: number;
}

const DAYS = [
    { value: 0, label: 'Monday' },
    { value: 1, label: 'Tuesday' },
    { value: 2, label: 'Wednesday' },
    { value: 3, label: 'Thursday' },
    { value: 4, label: 'Friday' }
];

export const CreateManualSlotModal: React.FC<CreateManualSlotModalProps> = ({ open, onClose, onSuccess, timetableId }) => {
    const { activityTypes } = useInstitutionSetup();
    const [loading, setLoading] = useState(false);
    const [dataLoading, setDataLoading] = useState(false);
    const [error, setError] = useState('');

    const [courses, setCourses] = useState<any[]>([]);
    const [lecturers, setLecturers] = useState<any[]>([]);
    const [rooms, setRooms] = useState<any[]>([]);
    const [groups, setGroups] = useState<any[]>([]);

    const [formData, setFormData] = useState({
        course_id: '',
        lecturer_id: '',
        room_id: '',
        group_id: '',
        day_of_week: 0,
        start_time: '08:00',
        end_time: '10:00',
        session_type: 'lecture'
    });

    const activityOptions = activityTypes.length > 0
        ? activityTypes.map((activityType) => ({
            value: activityType.key,
            label: activityType.display_name,
        }))
        : [
            { value: 'lecture', label: 'Lecture' },
            { value: 'practical', label: 'Practical/Lab' },
            { value: 'tutorial', label: 'Tutorial' },
        ];

    useEffect(() => {
        if (open) {
            loadFormData();
        }
    }, [open]);

    useEffect(() => {
        if (!open) return;
        const currentValue = String(formData.session_type || '').trim().toLowerCase();
        const validValues = new Set(activityOptions.map((option) => option.value));
        if (!validValues.has(currentValue)) {
            setFormData((prev) => ({
                ...prev,
                session_type: activityOptions[0]?.value || 'lecture',
            }));
        }
    }, [activityOptions, formData.session_type, open]);

    const loadFormData = async () => {
        setDataLoading(true);
        try {
            const [coursesRes, lecturersRes, roomsRes, groupsRes] = await Promise.all([
                coursesAPI.getAll(),
                lecturersAPI.getAll(),
                roomsAPI.getAll(),
                groupsAPI.getAll()
            ]);
            setCourses(coursesRes);
            setLecturers(lecturersRes);
            setRooms(roomsRes);
            setGroups(groupsRes);
        } catch (err) {
            setError('Failed to load selection data.');
        } finally {
            setDataLoading(false);
        }
    };

    const handleSubmit = async () => {
        if (!formData.course_id || !formData.lecturer_id || !formData.room_id || !formData.group_id) {
            setError('Please fill in all required fields.');
            return;
        }

        try {
            setLoading(true);
            setError('');
            await timetablesAPI.createManualSlot(timetableId, {
                course_id: Number(formData.course_id),
                lecturer_id: Number(formData.lecturer_id),
                room_id: Number(formData.room_id),
                group_id: Number(formData.group_id),
                day_of_week: formData.day_of_week,
                start_time: formData.start_time,
                end_time: formData.end_time,
                session_type: formData.session_type,
                is_fixed: true
            });
            onSuccess();
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create manual slot.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Create Custom Timetable Slot</DialogTitle>
            <DialogContent dividers>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                {dataLoading ? (
                    <CircularProgress sx={{ display: 'block', mx: 'auto', my: 2 }} />
                ) : (
                    <Grid container spacing={2}>
                        <Grid item xs={12}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Activity Type</InputLabel>
                                <Select
                                    value={formData.session_type}
                                    label="Activity Type"
                                    onChange={(e) => setFormData({ ...formData, session_type: e.target.value as string })}
                                >
                                    {activityOptions.map((option) => (
                                        <MenuItem key={option.value} value={option.value}>
                                            {option.label}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Course</InputLabel>
                                <Select
                                    value={formData.course_id}
                                    label="Course"
                                    onChange={(e) => setFormData({ ...formData, course_id: e.target.value as string })}
                                >
                                    {courses.map(c => <MenuItem key={c.id} value={c.id}>{c.code} - {c.title}</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Student Group</InputLabel>
                                <Select
                                    value={formData.group_id}
                                    label="Student Group"
                                    onChange={(e) => setFormData({ ...formData, group_id: e.target.value as string })}
                                >
                                    {groups.map(g => <MenuItem key={g.id} value={g.id}>{formatGroupName(g.group_name, g.display_code)} ({g.size} students)</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Lecturer</InputLabel>
                                <Select
                                    value={formData.lecturer_id}
                                    label="Lecturer"
                                    onChange={(e) => setFormData({ ...formData, lecturer_id: e.target.value as string })}
                                >
                                    {lecturers.map(l => <MenuItem key={l.id} value={l.id}>{formatPersonName(l.full_name)}</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} sm={6}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Room / Venue</InputLabel>
                                <Select
                                    value={formData.room_id}
                                    label="Room / Venue"
                                    onChange={(e) => setFormData({ ...formData, room_id: e.target.value as string })}
                                >
                                    {rooms.map(r => <MenuItem key={r.id} value={r.id}>{formatRoomName(r.name)} (Cap: {r.capacity})</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} sm={4}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Day</InputLabel>
                                <Select
                                    value={formData.day_of_week}
                                    label="Day"
                                    onChange={(e) => setFormData({ ...formData, day_of_week: Number(e.target.value) })}
                                >
                                    {DAYS.map(d => <MenuItem key={d.value} value={d.value}>{d.label}</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} sm={4}>
                            <TextField
                                fullWidth size="small"
                                type="time" label="Start Time"
                                value={formData.start_time}
                                onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                                InputLabelProps={{ shrink: true }}
                            />
                        </Grid>

                        <Grid item xs={12} sm={4}>
                            <TextField
                                fullWidth size="small"
                                type="time" label="End Time"
                                value={formData.end_time}
                                onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                                InputLabelProps={{ shrink: true }}
                            />
                        </Grid>
                    </Grid>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={loading}>Cancel</Button>
                <Button variant="contained" onClick={handleSubmit} disabled={loading || dataLoading}>
                    {loading ? 'Creating...' : 'Create Slot'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
