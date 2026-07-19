import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
    Alert,
    Badge,
    Box,
    Button,
    ButtonGroup,
    Chip,
    CircularProgress,
    Collapse,
    IconButton,
    MenuItem,
    Select,
    SelectChangeEvent,
    ToggleButton,
    ToggleButtonGroup,
    Typography,
} from '@mui/material';
import {
    Warning as WarningIcon,
    ExpandMore as ExpandMoreIcon,
    ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import TimetableGrid from '../components/TimetableGrid';
import TimetableAssignmentPanel from '../components/TimetableAssignmentPanel';
import { CreateManualSlotModal } from '../components/CreateManualSlotModal';
import { TimetableSlot } from '../components/TimetableCell';
import api, { departmentsAPI } from '../api';
import { useInstitutionSetup } from '../hooks/useInstitutionSetup';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TimetableMetadata {
    id?: number;
    term: string;
    year: number;
    total_courses: number;
    available_years?: number[];
    grid_config?: {
        start_time?: string;
        end_time?: string;
        lunch_start?: string;
        lunch_end?: string;
        active_days?: string[];
    };
}

interface TimetableViewData {
    metadata: TimetableMetadata;
    slots: TimetableSlot[];
}

interface Conflict {
    type: string;
    severity: string;
    slot_ids: number[];
    resource: {
        id: number;
        name: string;
        type: string;
    };
    day_of_week: number;
    start_time: string;
    end_time: string;
    description: string;
}

interface ConflictSummary {
    total_conflicts: number;
    by_type: {
        lecturer: number;
        room: number;
        group: number;
        lecturer_transit?: number;
        group_transit?: number;
    };
    by_severity: {
        high: number;
        medium: number;
    };
    conflicts: Conflict[];
}

interface ValidationIssue {
    entity_type: string;
    entity_id: number;
    field: string;
    message: string;
    severity: 'error' | 'warning' | 'info';
}

interface ValidationReport {
    valid: boolean;
    total_issues: number;
    errors: ValidationIssue[];
    warnings: ValidationIssue[];
    info: ValidationIssue[];
}

type ViewMode = 'view' | 'assign';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MIN_SUPPORTED_YEAR = 1;
const MAX_SUPPORTED_YEAR = 7;

const normalizeYearLevel = (rawLevel: unknown): number | null => {
    const numericLevel = Number(rawLevel);
    if (!Number.isInteger(numericLevel) || numericLevel <= 0) {
        return null;
    }

    if (numericLevel >= 100) {
        return Math.round(numericLevel / 100);
    }

    return numericLevel;
};

const formatYearLabel = (year: number): string => {
    const rem100 = year % 100;
    if (rem100 >= 11 && rem100 <= 13) {
        return `${year}th Year`;
    }

    const rem10 = year % 10;
    if (rem10 === 1) {
        return `${year}st Year`;
    }
    if (rem10 === 2) {
        return `${year}nd Year`;
    }
    if (rem10 === 3) {
        return `${year}rd Year`;
    }
    return `${year}th Year`;
};

const buildYearOptions = (years: number[]): { value: number; label: string }[] => (
    years.map((year) => ({ value: year, label: formatYearLabel(year) }))
);

const extractAvailableYears = (rows: Array<{ level?: number | null }>): number[] => {
    const years = Array.from(
        new Set(
            rows
                .map((row) => normalizeYearLevel(row.level))
                .filter((level): level is number => (
                    level !== null
                    && level >= MIN_SUPPORTED_YEAR
                    && level <= MAX_SUPPORTED_YEAR
                )),
        ),
    );

    return years.sort((a, b) => a - b);
};

const errorDetailToMessage = (detail: unknown): string | null => {
    if (typeof detail === 'string') {
        return detail;
    }

    if (Array.isArray(detail)) {
        return detail
            .map((item) => {
                if (typeof item === 'string') {
                    return item;
                }
                if (item && typeof item === 'object' && 'msg' in item) {
                    return String((item as { msg?: unknown }).msg);
                }
                return null;
            })
            .filter((value): value is string => Boolean(value))
            .join('; ');
    }

    return null;
};

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

/**
 * TimetableViewPage
 *
 * Renders the timetable grid view for the Institution.
 * Users can filter by year level and program. Data is fetched from
 * GET /api/v1/timetables/view with query parameters.
 *
 * In "Assign" mode, coordinators can click on timetable cells to
 * prepare lecturer and group assignments. Persistence will be wired
 * once the backend exposes slot identifiers and assignment endpoints.
 */
const TimetableViewPage: React.FC = () => {
    const { id: routeId } = useParams<{ id: string }>();
    const [selectedYear, setSelectedYear] = useState<number>(1);
    const [availableYears, setAvailableYears] = useState<number[]>([]);
    const [selectedProgram, setSelectedProgram] = useState<string>('ALL');
    const [selectedLayer, setSelectedLayer] = useState<string>('ALL');
    const [data, setData] = useState<TimetableViewData | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [mode, setMode] = useState<ViewMode>('view');
    const [selectedSlot, setSelectedSlot] = useState<TimetableSlot | null>(null);
    const [conflicts, setConflicts] = useState<ConflictSummary | null>(null);
    const [showConflicts, setShowConflicts] = useState<boolean>(false);
    const [validation, setValidation] = useState<ValidationReport | null>(null);
    const [showValidation, setShowValidation] = useState<boolean>(false);
    const [timetableId, setTimetableId] = useState<number | null>(null);
    const [openManualSlotModal, setOpenManualSlotModal] = useState(false);
    const [departments, setDepartments] = useState<{ id: number; name: string; code: string }[]>([]);
    const { activityTypes, activityTypesByKey } = useInstitutionSetup();

    // Build the layer filter items from live activity types, or fall back to the
    // three legacy hardcoded types for Engineering tenants without custom config.
    const layerItems: Array<{ key: string; label: string; color?: string }> = activityTypes.length > 0
        ? activityTypes.map((at) => ({ key: at.key, label: at.display_name, color: at.color }))
        : [
            { key: 'lecture',   label: 'Lectures' },
            { key: 'practical', label: 'Labs'     },
            { key: 'tutorial',  label: 'Tutorials' },
        ];

    useEffect(() => {
        const fetchFilters = async () => {
            try {
                const [depts, groupsRes, coursesRes] = await Promise.all([
                    departmentsAPI.getAll(),
                    api.get('/groups/?limit=1000').catch(() => null),
                    api.get('/courses/?limit=1000').catch(() => null),
                ]);

                setDepartments(depts);

                const groupPayload = groupsRes?.data;
                const groupRows = Array.isArray(groupPayload)
                    ? groupPayload
                    : Array.isArray(groupPayload?.items)
                        ? groupPayload.items
                        : [];

                const coursePayload = coursesRes?.data;
                const courseRows = Array.isArray(coursePayload)
                    ? coursePayload
                    : Array.isArray(coursePayload?.items)
                        ? coursePayload.items
                        : [];

                const years = Array.from(
                    new Set([
                        ...extractAvailableYears(groupRows),
                        ...extractAvailableYears(courseRows),
                    ]),
                ).sort((a, b) => a - b);

                if (years.length > 0) {
                    setAvailableYears(years);
                }
            } catch (err) {
                console.error('Failed to load timetable filters:', err);
            }
        };

        fetchFilters();
    }, []);

    useEffect(() => {
        if (availableYears.length === 0) {
            return;
        }

        if (!availableYears.includes(selectedYear)) {
            setSelectedYear(availableYears[0]);
        }
    }, [availableYears, selectedYear]);

    const fetchTimetable = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            let targetTimetableId: number | null = null;
            
            if (routeId) {
                const parsedRouteId = Number.parseInt(routeId, 10);
                targetTimetableId = Number.isNaN(parsedRouteId) ? null : parsedRouteId;
                setTimetableId(targetTimetableId);

                if (targetTimetableId !== null) {
                    fetchConflicts(targetTimetableId);
                    fetchValidation(targetTimetableId);
                }
            } else {
                // First get the active timetable to get its ID
                const timetablesResponse = await api.get('/timetables/');
                const activeTimetable = timetablesResponse.data.find((t: any) => t.is_active);

                if (activeTimetable) {
                    targetTimetableId = activeTimetable.id;
                    setTimetableId(targetTimetableId);
                    // Fetch conflicts and validation for this timetable
                    if (targetTimetableId !== null) {
                        fetchConflicts(targetTimetableId);
                        fetchValidation(targetTimetableId);
                    }
                }
            }

            const response = await api.get<TimetableViewData>('/timetables/view', {
                params: {
                    year: selectedYear,
                    program: selectedProgram,
                    ...(targetTimetableId ? { timetable_id: targetTimetableId } : {}),
                },
            });
            const responseYears = Array.isArray(response.data?.metadata?.available_years)
                ? response.data.metadata.available_years
                : [];
            if (responseYears.length > 0 && !responseYears.includes(selectedYear)) {
                setAvailableYears(responseYears);
                setSelectedYear(responseYears[0]);
                return;
            }
            if (responseYears.length > 0) {
                setAvailableYears(responseYears);
            }
            setData(response.data);
            setSelectedSlot(null);
        } catch (err: unknown) {
            const detailMessage = errorDetailToMessage(
                (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail,
            );
            const message = detailMessage
                || (err instanceof Error ? err.message : 'Failed to load timetable data.');
            setError(message);
        } finally {
            setLoading(false);
        }
    }, [selectedYear, selectedProgram, routeId]);

    const fetchConflicts = async (id: number) => {
        try {
            const response = await api.get(`/timetables/${id}/conflicts`);
            setConflicts(response.data);
        } catch (err) { console.error('Error fetching conflicts:', err); }
    };

    const fetchValidation = async (id: number) => {
        try {
            const response = await api.get(`/validate/timetable/${id}`);
            setValidation(response.data);
        } catch (err) { console.error('Error fetching validation:', err); }
    };

    useEffect(() => { fetchTimetable(); }, [fetchTimetable]);

    const handleYearSelect = (year: number) => { setSelectedYear(year); };
    const handleProgramChange = (event: SelectChangeEvent<string>) => { setSelectedProgram(event.target.value); };
    const handleModeChange = (_event: React.MouseEvent<HTMLElement>, newMode: ViewMode | null) => {
        if (!newMode) return;
        setMode(newMode);
        if (newMode === 'view') setSelectedSlot(null);
    };
    const handleSlotClick = (slot: TimetableSlot) => { setSelectedSlot(slot); };

    const yearOptions = buildYearOptions(availableYears.length > 0 ? availableYears : [selectedYear]);
    const hasSlots = !!data && data.slots.length > 0;

    return (
        <Box sx={{ padding: 3 }}>
            <Typography variant="h5" fontWeight={700} gutterBottom>Institution Timetable</Typography>

            {data?.metadata && (
                <Typography variant="body2" color="text.secondary" gutterBottom>
                    {data.metadata.term} {data.metadata.year}&nbsp;&mdash;&nbsp;
                    {data.metadata.total_courses} course{data.metadata.total_courses !== 1 ? 's' : ''}
                </Typography>
            )}

            {conflicts && conflicts.total_conflicts > 0 && (
                <Alert severity="warning" sx={{ mt: 2, mb: 2 }}
                    action={<IconButton aria-label="toggle conflicts" color="inherit" size="small" onClick={() => setShowConflicts(!showConflicts)}>{showConflicts ? <ExpandLessIcon /> : <ExpandMoreIcon />}</IconButton>}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <WarningIcon />
                        <Typography variant="body2" fontWeight="bold">
                            {conflicts.total_conflicts} Scheduling Conflict{conflicts.total_conflicts !== 1 ? 's' : ''} Detected
                        </Typography>
                    </Box>
                    <Collapse in={showConflicts} sx={{ mt: 2 }}>
                        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                            {conflicts.by_type.lecturer > 0 && <Chip label={`${conflicts.by_type.lecturer} Lecturer conflicts`} color="error" size="small" variant="outlined" />}
                            {conflicts.by_type.room > 0 && <Chip label={`${conflicts.by_type.room} Room conflicts`} color="error" size="small" variant="outlined" />}
                            {conflicts.by_type.group > 0 && <Chip label={`${conflicts.by_type.group} Group conflicts`} color="error" size="small" variant="outlined" />}
                            {(conflicts.by_type.lecturer_transit || 0) > 0 && <Chip label={`${conflicts.by_type.lecturer_transit} Lecturer transit issues`} color="warning" size="small" variant="outlined" />}
                            {(conflicts.by_type.group_transit || 0) > 0 && <Chip label={`${conflicts.by_type.group_transit} Student transit issues`} color="warning" size="small" variant="outlined" />}
                        </Box>
                        <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                            {conflicts.conflicts.map((conflict, idx) => (
                                <Box key={idx} sx={{ mb: 1, p: 1.5, bgcolor: 'rgba(255,152,0,0.08)', borderRadius: 1, border: '1px solid', borderColor: conflict.severity === 'high' ? 'error.main' : 'warning.main' }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                        <Typography variant="caption" fontWeight="bold">{conflict.resource.type.toUpperCase()} CONFLICT</Typography>
                                        <Badge badgeContent={conflict.slot_ids.length} color={conflict.severity === 'high' ? 'error' : 'warning'} sx={{ mr: 1 }}><WarningIcon fontSize="small" /></Badge>
                                    </Box>
                                    <Typography variant="body2">{conflict.description}</Typography>
                                </Box>
                            ))}
                        </Box>
                    </Collapse>
                </Alert>
            )}

            {validation && validation.total_issues > 0 && (
                <Alert severity={validation.errors.length > 0 ? 'error' : 'warning'} sx={{ mt: 2, mb: 2 }}
                    action={<IconButton aria-label="toggle validation" color="inherit" size="small" onClick={() => setShowValidation(!showValidation)}>{showValidation ? <ExpandLessIcon /> : <ExpandMoreIcon />}</IconButton>}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <WarningIcon />
                        <Typography variant="body2" fontWeight="bold">
                            {validation.total_issues} Validation Issue{validation.total_issues !== 1 ? 's' : ''} Found
                        </Typography>
                    </Box>
                    <Collapse in={showValidation} sx={{ mt: 2 }}>
                        <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                            {validation.errors.length > 0 && <Chip label={`${validation.errors.length} Error${validation.errors.length !== 1 ? 's' : ''}`} color="error" size="small" />}
                            {validation.warnings.length > 0 && <Chip label={`${validation.warnings.length} Warning${validation.warnings.length !== 1 ? 's' : ''}`} color="warning" size="small" />}
                            {validation.info.length > 0 && <Chip label={`${validation.info.length} Info`} color="info" size="small" />}
                        </Box>
                        <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                            {validation.errors.map((issue, idx) => (
                                <Box key={`e-${idx}`} sx={{ mb: 1, p: 1.5, bgcolor: 'rgba(211,47,47,0.08)', borderRadius: 1, border: '1px solid', borderColor: 'error.main' }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                        <Typography variant="caption" fontWeight="bold" color="error">ERROR &bull; {issue.entity_type.toUpperCase()} #{issue.entity_id}</Typography>
                                        <Chip label={issue.field} size="small" color="error" variant="outlined" />
                                    </Box>
                                    <Typography variant="body2">{issue.message}</Typography>
                                </Box>
                            ))}
                            {validation.warnings.map((issue, idx) => (
                                <Box key={`w-${idx}`} sx={{ mb: 1, p: 1.5, bgcolor: 'rgba(255,152,0,0.08)', borderRadius: 1, border: '1px solid', borderColor: 'warning.main' }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                        <Typography variant="caption" fontWeight="bold" color="warning.dark">WARNING &bull; {issue.entity_type.toUpperCase()} #{issue.entity_id}</Typography>
                                        <Chip label={issue.field} size="small" color="warning" variant="outlined" />
                                    </Box>
                                    <Typography variant="body2">{issue.message}</Typography>
                                </Box>
                            ))}
                            {validation.info.map((issue, idx) => (
                                <Box key={`i-${idx}`} sx={{ mb: 1, p: 1.5, bgcolor: 'rgba(2,136,209,0.08)', borderRadius: 1, border: '1px solid', borderColor: 'info.main' }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                        <Typography variant="caption" fontWeight="bold" color="info.dark">INFO &bull; {issue.entity_type.toUpperCase()} #{issue.entity_id}</Typography>
                                        <Chip label={issue.field} size="small" color="info" variant="outlined" />
                                    </Box>
                                    <Typography variant="body2">{issue.message}</Typography>
                                </Box>
                            ))}
                        </Box>
                    </Collapse>
                </Alert>
            )}

            {/* ── Filter Bar ── */}
            <Box className="timetable-filter-bar" sx={{ mt: 2, mb: 1, alignItems: 'flex-end' }}>
                <Box className="timetable-filter-group">
                    <Typography className="timetable-filter-label" variant="caption">Year Level</Typography>
                    <ButtonGroup variant="outlined" size="small" aria-label="Select year level">
                        {yearOptions.map(({ value, label }) => (
                            <Button key={value} variant={selectedYear === value ? 'contained' : 'outlined'} onClick={() => handleYearSelect(value)} aria-pressed={selectedYear === value} disableElevation>
                                {label}
                            </Button>
                        ))}
                    </ButtonGroup>
                </Box>

                <Box className="timetable-filter-group" sx={{ minWidth: 220 }}>
                    <Typography className="timetable-filter-label" variant="caption">Program</Typography>
                    <Select value={selectedProgram} onChange={handleProgramChange} size="small" fullWidth inputProps={{ 'aria-label': 'Select program' }}>
                        <MenuItem value="ALL">All Programs</MenuItem>
                        {departments.map((dept) => (
                            <MenuItem key={dept.id} value={dept.code}>{dept.name}</MenuItem>
                        ))}
                    </Select>
                </Box>

                {/* Dynamic activity-type layer filter */}
                <Box className="timetable-filter-group" sx={{ ml: 2 }}>
                    <Typography className="timetable-filter-label" variant="caption">Layer</Typography>
                    <ButtonGroup variant="outlined" size="small" sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.25 }}>
                        <Button variant={selectedLayer === 'ALL' ? 'contained' : 'outlined'} onClick={() => setSelectedLayer('ALL')}>All</Button>
                        {layerItems.map((item) => (
                            <Button
                                key={item.key}
                                variant={selectedLayer === item.key ? 'contained' : 'outlined'}
                                onClick={() => setSelectedLayer(item.key)}
                                sx={selectedLayer === item.key && item.color ? {
                                    bgcolor: item.color, borderColor: item.color,
                                    '&:hover': { bgcolor: item.color, filter: 'brightness(0.9)' },
                                } : {}}
                            >
                                {item.color && (
                                    <Box component="span" sx={{
                                        display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                                        bgcolor: selectedLayer === item.key ? '#fff' : item.color,
                                        mr: 0.75, flexShrink: 0, verticalAlign: 'middle',
                                    }} />
                                )}
                                {item.label}
                            </Button>
                        ))}
                    </ButtonGroup>
                </Box>

                <Box sx={{ flexGrow: 1 }} />

                {mode === 'assign' && timetableId && (
                    <Box sx={{ mr: 2 }}>
                        <Button variant="outlined" color="secondary" onClick={() => setOpenManualSlotModal(true)} size="small" sx={{ mt: 2 }}>
                            + Add Session
                        </Button>
                    </Box>
                )}

                <Box className="timetable-filter-group">
                    <Typography className="timetable-filter-label" variant="caption">Mode</Typography>
                    <ToggleButtonGroup size="small" value={mode} exclusive onChange={handleModeChange} aria-label="Timetable mode">
                        <ToggleButton value="view" aria-label="View mode">View</ToggleButton>
                        <ToggleButton value="assign" aria-label="Assignment mode" disabled={!hasSlots}>Assign</ToggleButton>
                    </ToggleButtonGroup>
                </Box>
            </Box>

            {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 6 }} aria-label="Loading timetable" aria-busy="true">
                    <CircularProgress />
                </Box>
            )}

            {!loading && error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

            {!loading && !error && data && data.slots.length === 0 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                    No timetable data found for {formatYearLabel(selectedYear)}
                    {selectedProgram !== 'ALL' ? ` — ${selectedProgram}` : ''}.
                    Import timetable data or adjust filters.
                </Alert>
            )}

            {!loading && !error && data && data.slots.length > 0 && (
                <Box sx={{ display: 'flex', mt: 2 }}>
                    <Box sx={{ flex: 3, pr: 2 }}>
                        <TimetableGrid
                            slots={data.slots.filter(slot => selectedLayer === 'ALL' || slot.session_type === selectedLayer)}
                            gridConfig={data.metadata.grid_config}
                            mode={mode}
                            onSlotClick={handleSlotClick}
                            selectedSlot={selectedSlot}
                            activityTypesMap={activityTypesByKey}
                        />
                    </Box>
                    {mode === 'assign' && (
                        <Box sx={{ flex: 2, minWidth: 320 }}>
                            <TimetableAssignmentPanel
                                selectedSlot={selectedSlot}
                                onSlotSelect={setSelectedSlot}
                                onAssignmentComplete={fetchTimetable}
                            />
                        </Box>
                    )}
                </Box>
            )}

            {timetableId && (
                <CreateManualSlotModal
                    open={openManualSlotModal}
                    onClose={() => setOpenManualSlotModal(false)}
                    onSuccess={() => { fetchTimetable(); }}
                    timetableId={timetableId}
                />
            )}
        </Box>
    );
};

export default TimetableViewPage;
