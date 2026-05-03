import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Divider,
    FormControlLabel,
    List,
    ListItem,
    ListItemText,
    Stack,
    Switch,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AutoAwesome as AutoIcon,
    Group as GroupIcon,
    School as SchoolIcon,
    Warning as WarnIcon,
} from '@mui/icons-material';
import { coursesAPI } from '../api';
import { formatGroupLabel } from '../utils/displayFormatters';

interface EnrollmentGroupOption {
    id: number;
    name: string;
    display_code?: string | null;
    level: number;
    size: number;
    department_id: number;
    department_name?: string | null;
    department_code?: string | null;
    ownership_kind: 'owner' | 'shared';
    selected: boolean;
}

interface EnrollmentMap {
    course_id: number;
    course_code: string;
    course_name: string;
    course_department_id: number;
    course_department_name?: string | null;
    lecture_mode: 'shared' | 'separate';
    selected_group_ids: number[];
    eligible_groups: EnrollmentGroupOption[];
    stream_mapping_note: string;
}

interface CourseGroupAssignerProps {
    courseId: number;
    courseLevel: number;
    onSaved?: () => void;
}

export const CourseGroupAssigner: React.FC<CourseGroupAssignerProps> = ({
    courseId,
    courseLevel,
    onSaved,
}) => {
    const [mapping, setMapping] = useState<EnrollmentMap | null>(null);
    const [selectedIds, setSelectedIds] = useState<number[]>([]);
    const [isSharedLecture, setIsSharedLecture] = useState(false);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const fetchMapping = async () => {
        setLoading(true);
        setError('');
        try {
            const data: EnrollmentMap = await coursesAPI.getEnrollmentMap(courseId);
            setMapping(data);
            setSelectedIds(data.selected_group_ids);
            setIsSharedLecture(data.lecture_mode === 'shared');
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to load course enrolment mapping.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void fetchMapping();
    }, [courseId]);

    const eligibleGroups = mapping?.eligible_groups ?? [];
    const selectedLookup = useMemo(() => new Set(selectedIds), [selectedIds]);

    const combinedSize = useMemo(
        () => eligibleGroups.filter((group) => selectedLookup.has(group.id)).reduce((sum, group) => sum + group.size, 0),
        [eligibleGroups, selectedLookup],
    );

    const ownerGroupIds = useMemo(
        () => eligibleGroups.filter((group) => group.ownership_kind === 'owner').map((group) => group.id),
        [eligibleGroups],
    );

    const groupedByDepartment = useMemo(() => {
        const grouped = new Map<number, EnrollmentGroupOption[]>();
        eligibleGroups.forEach((group) => {
            const current = grouped.get(group.department_id) ?? [];
            current.push(group);
            grouped.set(group.department_id, current);
        });
        return Array.from(grouped.entries()).map(([departmentId, groups]) => ({
            departmentId,
            departmentCode: groups[0]?.department_code ?? `D${departmentId}`,
            departmentName: groups[0]?.department_name ?? 'Unknown Department',
            groups,
        }));
    }, [eligibleGroups]);

    const toggleGroup = (id: number) => {
        setSelectedIds((prev) => (
            prev.includes(id)
                ? prev.filter((item) => item !== id)
                : [...prev, id]
        ));
    };

    const handleSave = async () => {
        setSaving(true);
        setError('');
        setSuccess('');
        try {
            const response: EnrollmentMap = await coursesAPI.updateEnrollmentMap(courseId, {
                group_ids: selectedIds,
                lecture_mode: isSharedLecture && selectedIds.length > 1 ? 'shared' : 'separate',
            });
            setMapping(response);
            setSelectedIds(response.selected_group_ids);
            setIsSharedLecture(response.lecture_mode === 'shared');
            setSuccess(
                response.selected_group_ids.length === 0
                    ? 'Saved. No main cohorts are enrolled on this course yet.'
                    : response.lecture_mode === 'shared' && response.selected_group_ids.length > 1
                        ? `Saved. ${response.selected_group_ids.length} cohorts now share one lecture audience.`
                        : `Saved. ${response.selected_group_ids.length} cohort(s) are enrolled with separate lecture delivery.`
            );
            onSaved?.();
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to save course enrolment.');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <CircularProgress size={24} />;
    }

    return (
        <Box>
            {error && <Alert severity="error" sx={{ mb: 1 }} onClose={() => setError('')}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 1 }} onClose={() => setSuccess('')}>{success}</Alert>}

            <Alert severity="info" sx={{ mb: 2 }}>
                Use this panel to <strong>pull same-level groups into this specific course</strong>.
                Receiving departments will see the result on their Groups page, but they do not control it there.
            </Alert>

            {mapping && (
                <Box sx={{ mb: 1.5 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                        Owner Department
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                        {mapping.course_department_name || 'Unknown Department'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        Year {courseLevel >= 100 ? Math.round(courseLevel / 100) : courseLevel} main groups only
                    </Typography>
                </Box>
            )}

            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5, flexWrap: 'wrap' }}>
                <Tooltip title="Broadcast this course to every eligible main cohort across the owner and shared departments">
                    <Button
                        size="small"
                        variant="outlined"
                        color="secondary"
                        startIcon={<AutoIcon />}
                        onClick={() => setSelectedIds(eligibleGroups.map((group) => group.id))}
                    >
                        Select All Eligible
                    </Button>
                </Tooltip>
                <Button
                    size="small"
                    variant="outlined"
                    onClick={() => setSelectedIds(ownerGroupIds)}
                >
                    Owner Groups Only
                </Button>
                <Button
                    size="small"
                    variant="text"
                    color="inherit"
                    onClick={() => setSelectedIds([])}
                >
                    Clear
                </Button>
                {selectedIds.length > 0 && (
                    <Chip
                        icon={<GroupIcon />}
                        label={`${combinedSize} students`}
                        color={combinedSize > 200 ? 'warning' : 'success'}
                        size="small"
                    />
                )}
            </Stack>

            <List dense disablePadding>
                {eligibleGroups.length === 0 && !error && (
                    <Alert severity="warning" sx={{ mb: 1.5 }}>
                        No eligible main groups were found for this course yet.
                        Check that student groups exist for the course level and owner/shared departments.
                    </Alert>
                )}
                {groupedByDepartment.map((entry) => (
                    <Box key={entry.departmentId} sx={{ mb: 0.5 }}>
                        <ListItem sx={{ py: 0.25, bgcolor: 'rgba(0,0,0,0.03)', borderRadius: 1 }}>
                            <ListItemText
                                primary={
                                    <Stack direction="row" spacing={1} alignItems="center">
                                        <Typography variant="body2" fontWeight={700}>
                                            {entry.departmentCode}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {entry.departmentName}
                                        </Typography>
                                    </Stack>
                                }
                            />
                        </ListItem>
                        {entry.groups.map((group) => (
                            <ListItem key={group.id} disablePadding sx={{ py: 0.25 }}>
                                <Checkbox
                                    checked={selectedLookup.has(group.id)}
                                    onChange={() => toggleGroup(group.id)}
                                    size="small"
                                />
                                <ListItemText
                                    primary={
                                        <Stack direction="row" spacing={1} alignItems="center">
                                            <Typography variant="body2">
                                                {formatGroupLabel({ name: group.name, display_code: group.display_code })}
                                            </Typography>
                                            <Chip
                                                label={group.ownership_kind === 'owner' ? 'Owner' : 'Shared'}
                                                size="small"
                                                color={group.ownership_kind === 'owner' ? 'primary' : 'secondary'}
                                                variant="outlined"
                                            />
                                        </Stack>
                                    }
                                    secondary={`${group.display_code || group.department_code || 'Group'} · ${group.size} students`}
                                    primaryTypographyProps={{ component: 'div' }}
                                    secondaryTypographyProps={{ variant: 'caption' }}
                                />
                            </ListItem>
                        ))}
                    </Box>
                ))}
            </List>

            <Divider sx={{ my: 1.5 }} />

            {selectedIds.length > 1 && (
                <>
                    <FormControlLabel
                        control={(
                            <Switch
                                checked={isSharedLecture}
                                onChange={(event) => setIsSharedLecture(event.target.checked)}
                                color="secondary"
                            />
                        )}
                        label={(
                            <Box>
                                <Typography variant="body2" fontWeight={700}>
                                    Shared Lecture Delivery
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    Use one combined lecture slot for every selected main cohort.
                                </Typography>
                            </Box>
                        )}
                    />
                    {isSharedLecture && combinedSize > 300 && (
                        <Alert severity="warning" icon={<WarnIcon />} sx={{ mt: 1, py: 0.5 }}>
                            Combined size is {combinedSize}. Make sure a large enough venue exists.
                        </Alert>
                    )}
                    {isSharedLecture && (
                        <Alert severity="info" sx={{ mt: 1, py: 0.5 }}>
                            The generator will treat these selected cohorts as one shared lecture audience.
                        </Alert>
                    )}
                </>
            )}

            {mapping?.stream_mapping_note && (
                <Alert severity="info" sx={{ mt: 1.5, py: 0.5 }}>
                    {mapping.stream_mapping_note}
                </Alert>
            )}

            <Box sx={{ mt: 1.5 }}>
                <Button
                    variant="contained"
                    size="small"
                    onClick={handleSave}
                    disabled={saving}
                    startIcon={saving ? <CircularProgress size={14} /> : <SchoolIcon />}
                >
                    {saving ? 'Saving...' : 'Save Enrolment'}
                </Button>
            </Box>
        </Box>
    );
};

export default CourseGroupAssigner;
