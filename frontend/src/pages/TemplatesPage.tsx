import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
    Box, Button, Paper, Typography, Tab, Tabs, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, IconButton,
    Dialog, DialogTitle, DialogContent, DialogActions, TextField,
    Alert, Chip, Tooltip, Grid, CircularProgress, Divider,
    LinearProgress, Stack, ToggleButton, ToggleButtonGroup, ButtonGroup,
} from '@mui/material';
import {
    UploadFile as UploadFileIcon,
    CheckCircle as CheckCircleIcon,
    Star as StarIcon,
    StarBorder as StarBorderIcon,
    Delete as DeleteIcon,
    Visibility as VisibilityIcon,
    TableChart as TableChartIcon,
    Edit as EditIcon,
    Fullscreen as FullscreenIcon,
    FullscreenExit as FullscreenExitIcon,
    Close as CloseIcon,
    FilterList as FilterListIcon,
} from '@mui/icons-material';

const API_BASE = '/api/v1';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

const SESSION_TYPES = ['lecture', 'practical', 'tutorial'] as const;
type SessionType = typeof SESSION_TYPES[number];

const SESSION_META: Record<SessionType, { bg: string; border: string; color: string; label: string }> = {
    lecture: { bg: '#ddeeff', border: '#1565c0', color: '#1565c0', label: 'Lecture' },
    practical: { bg: '#ddffdd', border: '#2e7d32', color: '#2e7d32', label: 'Lab / Practical' },
    tutorial: { bg: '#fff3cd', border: '#8d5a00', color: '#8d5a00', label: 'Tutorial' },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Container {
    day: string;
    start_hour: number;
    end_hour: number;
    duration: number;
    session_type: SessionType;
    group_label: string;
    col_index: number;
    row_index: number;
}

interface PreviewResult {
    file_type: string;
    shape: Record<string, unknown>;
    containers: Container[];
    container_count: number;
    session_type_counts: Record<string, number>;
}

interface TemplateProfile {
    id: number;
    name: string;
    school_name: string | null;
    is_active: boolean;
    original_filename: string | null;
    file_type: string;
    container_count: number;
    created_at: string;
}

// ---------------------------------------------------------------------------
// Auth hook
// ---------------------------------------------------------------------------

function useAuthHeaders() {
    const token = sessionStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

// ---------------------------------------------------------------------------
// Timetable grid helpers
// ---------------------------------------------------------------------------

/** Extract level number and dept prefix from a group label.
 *  Examples: "AEN-3" → { dept: "AEN", level: 3 }
 *            "MEC-2A" → { dept: "MEC", level: 2 }
 *            "CS3" → { dept: "CS", level: 3 }
 *            "Year 4 ENG" → { dept: "ENG", level: 4 }
 */
function parseGroupLabel(label: string): { dept: string; level: number } {
    // Pattern 1: DEPT-LEVEL  e.g. AEN-3, MEE-2, CSC-1A
    const dashMatch = label.match(/^([A-Z]{2,6})[\s-](\d)/);
    if (dashMatch) return { dept: dashMatch[1], level: parseInt(dashMatch[2], 10) };

    // Pattern 2: DEPTLEVEL  e.g. CS3, EE4
    const inlineMatch = label.match(/^([A-Za-z]{2,6})(\d)/);
    if (inlineMatch) return { dept: inlineMatch[1].toUpperCase(), level: parseInt(inlineMatch[2], 10) };

    // Pattern 3: Year N DEPT  e.g. "Year 3 Engineering"
    const yearMatch = label.match(/year\s*(\d)/i);
    if (yearMatch) return { dept: label.replace(/year\s*\d/i, '').trim().toUpperCase().slice(0, 6) || 'GEN', level: parseInt(yearMatch[1], 10) };

    return { dept: label.slice(0, 6).toUpperCase(), level: 0 };
}

/** Sort group labels: first by level (asc), then by dept name (alpha). */
function sortGroups(groups: string[]): string[] {
    return [...groups].sort((a, b) => {
        const pa = parseGroupLabel(a);
        const pb = parseGroupLabel(b);
        if (pa.level !== pb.level) return pa.level - pb.level;
        return pa.dept.localeCompare(pb.dept);
    });
}

function fmt(h: number) {
    return `${String(h).padStart(2, '0')}:00`;
}

// ---------------------------------------------------------------------------
// Timetable grid preview component
// ---------------------------------------------------------------------------

interface GridPreviewProps {
    containers: Container[];
    onChange: (updated: Container[]) => void;
    readOnly?: boolean;
}

/**
 * New grid: single active level (Year 1–5). Time on rows, Days on columns.
 */
function TimetableGridPreview({ containers, onChange, readOnly = false }: GridPreviewProps) {
    const [isFullscreen, setIsFullscreen] = useState(false);
    
    const baseLevels = ['Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5'];
    const [activeLevel, setActiveLevel] = useState<string>('Year 1');
    const [selectedLayer, setSelectedLayer] = useState<string>('ALL');

    // We build lookup to easily find the painted containers
    let minHour = 7;
    let maxHour = 18;

    const lookup = new Map<string, Container>();
    for (const c of containers) {
        if (c.start_hour < minHour) minHour = c.start_hour;
        if (c.end_hour - 1 > maxHour) maxHour = c.end_hour - 1;
        for (let h = c.start_hour; h < c.end_hour; h++) {
            lookup.set(`${c.day}|${h}|${c.group_label}`, c);
        }
    }
    const hours = Array.from({ length: maxHour - minHour + 1 }, (_, i) => minHour + i);

    const cycleSession = useCallback(
        (day: string, hour: number, group: string) => {
            if (readOnly) return;
            const key = `${day}|${hour}|${group}`;
            const existing = lookup.get(key);
            if (!existing) {
                const newC: Container = {
                    day, start_hour: hour, end_hour: hour + 1, duration: 1,
                    session_type: 'lecture', group_label: group, col_index: 0, row_index: 0,
                };
                onChange([...containers, newC]);
                return;
            }
            const idx = SESSION_TYPES.indexOf(existing.session_type);
            const nextIdx = (idx + 1) % (SESSION_TYPES.length + 1);
            if (nextIdx === SESSION_TYPES.length) {
                onChange(containers.filter(c =>
                    !(c.day === day && c.group_label === group &&
                        c.start_hour === existing.start_hour && c.end_hour === existing.end_hour)));
            } else {
                onChange(containers.map(c =>
                    c.day === day && c.group_label === group &&
                        c.start_hour === existing.start_hour && c.end_hour === existing.end_hour
                        ? { ...c, session_type: SESSION_TYPES[nextIdx] } : c));
            }
        },
        [containers, lookup, onChange, readOnly]
    );

    // ── Filter and Level Selector ──────────────────────────────────────────────────
    const filterBar = (
        <Box sx={{ mb: 2 }}>
            <Box sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}>
                <Tabs 
                    value={activeLevel} 
                    onChange={(_, val) => setActiveLevel(val)}
                    variant="scrollable"
                    scrollButtons="auto"
                >
                    {baseLevels.map(level => (
                        <Tab key={level} label={level} value={level} sx={{ fontWeight: 700 }} />
                    ))}
                </Tabs>
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1, flexWrap: 'wrap' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <FilterListIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                    <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                        Layer
                    </Typography>
                </Box>
                <ButtonGroup variant="outlined" size="small">
                    {['ALL', 'lecture', 'practical', 'tutorial'].map(layer => {
                        const labels: Record<string, string> = { ALL: 'All', lecture: 'Lectures', practical: 'Labs', tutorial: 'Tutorials' };
                        return (
                            <Button
                                key={layer}
                                variant={selectedLayer === layer ? 'contained' : 'outlined'}
                                onClick={() => setSelectedLayer(layer)}
                            >
                                {labels[layer]}
                            </Button>
                        );
                    })}
                </ButtonGroup>
            </Box>
        </Box>
    );

    // ── Legend + fullscreen toggle ─────────────────────────────────────────
    const legendBar = (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                {SESSION_TYPES.map(t => (
                    <Chip key={t} label={SESSION_META[t].label} size="small" sx={{
                        bgcolor: SESSION_META[t].bg, color: SESSION_META[t].color,
                        border: `1px solid ${SESSION_META[t].border}40`, fontWeight: 600, fontSize: 11,
                    }} />
                ))}
                {!readOnly && (
                    <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
                        Click any cell to cycle: Lecture → Lab → Tutorial → Empty
                    </Typography>
                )}
            </Stack>
            <Tooltip title="Toggle Fullscreen">
                <IconButton onClick={() => setIsFullscreen(!isFullscreen)} color="primary" sx={{ bgcolor: 'action.hover' }}>
                    {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
                </IconButton>
            </Tooltip>
        </Box>
    );

    // ── Grid table: Time rows, Day columns for actively selected level ───────────────
    const gridContent = (
        <TableContainer
            component={Paper}
            variant="outlined"
            sx={{
                borderRadius: isFullscreen ? 0 : 2,
                border: isFullscreen ? 'none' : undefined,
                overflowX: 'auto',
                maxHeight: isFullscreen ? 'calc(100vh - 200px)' : 600,
                overflowY: 'auto',
                bgcolor: '#fff',
            }}
        >
            <Table size="small" stickyHeader>
                <TableHead>
                    <TableRow>
                        <TableCell sx={{
                            bgcolor: '#263238', color: '#fff', fontWeight: 700, fontSize: 12,
                            minWidth: 80, position: 'sticky', left: 0, zIndex: 4,
                        }}>
                            Time
                        </TableCell>
                        {DAYS.map(day => (
                            <TableCell key={day} align="center" sx={{
                                bgcolor: '#37474f', color: '#fff', fontWeight: 700, fontSize: 12,
                                minWidth: 100, whiteSpace: 'nowrap', width: `${100/DAYS.length}%`
                            }}>
                                {day}
                            </TableCell>
                        ))}
                    </TableRow>
                </TableHead>
                <TableBody>
                    {hours.map((hour, rowIdx) => {
                        if (hour === 13) {
                            return (
                                <TableRow key={`lunch-${hour}`}>
                                    <TableCell
                                        colSpan={1 + DAYS.length}
                                        align="center"
                                        sx={{
                                            bgcolor: '#ffebee', color: '#c62828', fontWeight: 800,
                                            letterSpacing: 6, py: 0.75, fontSize: 11,
                                            borderTop: '2px solid #ffcdd2', borderBottom: '2px solid #ffcdd2',
                                            textTransform: 'uppercase', position: 'sticky', left: 0,
                                        }}
                                    >
                                        Lunch Break
                                    </TableCell>
                                </TableRow>
                            );
                        }

                        const rowBg = rowIdx % 2 === 0 ? '#fff' : '#f9fafb';
                        const timeCellBg = rowIdx % 2 === 0 ? '#f5f7fa' : '#eef1f4';

                        return (
                            <TableRow key={`${hour}`} sx={{ bgcolor: rowBg, height: 60 }}>
                                <TableCell
                                    sx={{
                                        fontWeight: 600, fontSize: 12, color: '#455a64',
                                        whiteSpace: 'nowrap', position: 'sticky', left: 0,
                                        bgcolor: timeCellBg, zIndex: 1,
                                        borderRight: '2px solid #cfd8dc',
                                    }}
                                >
                                    {fmt(hour)}–{fmt(hour + 1)}
                                </TableCell>

                                {DAYS.map(day => {
                                    const key = `${day}|${hour}|${activeLevel}`;
                                    const container = lookup.get(key);
                                    let meta = null;
                                    let isFilteredOut = false;
                                    
                                    if (container) {
                                        if (selectedLayer === 'ALL' || container.session_type === selectedLayer) {
                                            meta = SESSION_META[container.session_type];
                                        } else {
                                            isFilteredOut = true;
                                        }
                                    }
                                    
                                    return (
                                        <TableCell
                                            key={day}
                                            align="center"
                                            onClick={() => cycleSession(day, hour, activeLevel)}
                                            sx={{
                                                p: 0.6, verticalAlign: 'middle',
                                                cursor: readOnly ? 'default' : 'pointer',
                                                transition: 'background 0.12s',
                                                '&:hover': readOnly ? {} : {
                                                    bgcolor: (meta && container) ? meta.bg : '#f0f4f8',
                                                    outline: '2px solid #90a4ae',
                                                    outlineOffset: '-2px',
                                                },
                                            }}
                                        >
                                            {meta && container ? (
                                                <Box sx={{
                                                    bgcolor: meta.bg,
                                                    border: `1.5px solid ${meta.border}60`,
                                                    borderRadius: 1, px: 0.5, py: 0.4,
                                                    height: '100%',
                                                    minHeight: 40,
                                                    display: 'flex', flexDirection: 'column',
                                                    alignItems: 'center', justifyContent: 'center',
                                                }}>
                                                    <Typography variant="caption" fontWeight={700}
                                                        sx={{ color: meta.color, lineHeight: 1.2, fontSize: 11 }}>
                                                        {meta.label}
                                                    </Typography>
                                                </Box>
                                            ) : (
                                                <Box sx={{
                                                    minHeight: 40, borderRadius: 1, height: '100%',
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    border: isFilteredOut ? 'none' : '1px dashed #e0e0e0',
                                                    bgcolor: isFilteredOut ? 'transparent' : 'transparent',
                                                }}>
                                                    {isFilteredOut && (
                                                        <Typography variant="caption" color="text.disabled" sx={{ fontSize: 10 }}>
                                                            Hidden by layer
                                                        </Typography>
                                                    )}
                                                </Box>
                                            )}
                                        </TableCell>
                                    );
                                })}
                            </TableRow>
                        );
                    })}
                </TableBody>
            </Table>
        </TableContainer>
    );

    if (isFullscreen) {
        return (
            <Dialog fullScreen open={isFullscreen} onClose={() => setIsFullscreen(false)}
                PaperProps={{ sx: { bgcolor: '#f5f7fb' } }}>
                <Box sx={{
                    p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    bgcolor: '#fff', borderBottom: 1, borderColor: 'divider'
                }}>
                    <Typography variant="h6" fontWeight={700} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TableChartIcon color="primary" />
                        Fullscreen — Weekly Timetable Blueprint
                    </Typography>
                    <IconButton onClick={() => setIsFullscreen(false)}><CloseIcon /></IconButton>
                </Box>
                <Box sx={{ p: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {filterBar}
                    {legendBar}
                    {gridContent}
                </Box>
            </Dialog>
        );
    }

    return (
        <Box>
            {filterBar}
            {legendBar}
            {gridContent}
        </Box>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function TemplatesPage() {
    const authHeaders = useAuthHeaders();

    const [profiles, setProfiles] = useState<TemplateProfile[]>([]);
    const [loadingProfiles, setLoadingProfiles] = useState(false);

    const [preview, setPreview] = useState<PreviewResult | null>(null);
    // Local editable copy of containers
    const [editedContainers, setEditedContainers] = useState<Container[]>([]);

    const [showSaveDialog, setShowSaveDialog] = useState(false);
    const [profileName, setProfileName] = useState('');
    const [schoolName, setSchoolName] = useState('');
    const [saving, setSaving] = useState(false);
    const [savedOk, setSavedOk] = useState('');

    const [viewProfile, setViewProfile] = useState<(TemplateProfile & { containers?: Container[] }) | null>(null);
    const [loadingDetail, setLoadingDetail] = useState(false);

    const [deleteTarget, setDeleteTarget] = useState<TemplateProfile | null>(null);
    const [globalError, setGlobalError] = useState('');

    useEffect(() => { fetchProfiles(); }, []);

    async function fetchProfiles() {
        setLoadingProfiles(true);
        try {
            const res = await fetch(`${API_BASE}/templates/`, { headers: authHeaders as HeadersInit });
            if (res.ok) setProfiles(await res.json());
        } catch {
            setGlobalError('Failed to load template profiles.');
        } finally {
            setLoadingProfiles(false);
        }
    }

    async function handleSave() {
        if (!preview || !profileName.trim()) return;
        setSaving(true);
        try {
            const body = {
                name: profileName.trim(),
                school_name: schoolName.trim() || null,
                original_filename: null,
                file_type: 'internal',
                shape: preview.shape,
                containers: editedContainers,   // save the (possibly edited) version
            };
            const res = await fetch(`${API_BASE}/templates/save`, {
                method: 'POST',
                headers: { ...(authHeaders as HeadersInit), 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json();
                setGlobalError(err.detail || 'Save failed.');
                return;
            }
            setShowSaveDialog(false);
            setSavedOk(`Profile "${profileName}" saved successfully!`);
            setProfileName(''); setSchoolName('');
            setPreview(null); setEditedContainers([]);
            fetchProfiles();
        } finally {
            setSaving(false);
        }
    }

    async function handleActivate(profile: TemplateProfile) {
        const res = await fetch(`${API_BASE}/templates/${profile.id}/activate`, {
            method: 'PUT',
            headers: authHeaders as HeadersInit,
        });
        if (res.ok) fetchProfiles();
    }

    async function handleViewDetail(profile: TemplateProfile) {
        setViewProfile({ ...profile });
        setLoadingDetail(true);
        const res = await fetch(`${API_BASE}/templates/${profile.id}`, { headers: authHeaders as HeadersInit });
        if (res.ok) {
            const data = await res.json();
            setViewProfile({ ...profile, containers: data.containers });
        }
        setLoadingDetail(false);
    }

    async function handleDelete() {
        if (!deleteTarget) return;
        const res = await fetch(`${API_BASE}/templates/${deleteTarget.id}`, {
            method: 'DELETE',
            headers: authHeaders as HeadersInit,
        });
        if (res.ok || res.status === 204) { setDeleteTarget(null); fetchProfiles(); }
    }

    // Derived stats for edited containers
    const editedCounts = editedContainers.reduce<Record<string, number>>((acc, c) => {
        acc[c.session_type] = (acc[c.session_type] || 0) + 1;
        return acc;
    }, {});

    return (
        <Box sx={{ p: 3, maxWidth: 1200, mx: 'auto' }}>
            <Typography variant="h4" fontWeight={700} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TableChartIcon fontSize="large" color="primary" />
                Timetable Template Profiles
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                Build a standalone template guide visually. The solver uses these Year-Level patterns as heuristics when generating class timetables.
            </Typography>

            {globalError && <Alert severity="error" sx={{ mb: 2 }}>{globalError}</Alert>}
            {savedOk && <Alert severity="success" icon={<CheckCircleIcon />} sx={{ mb: 2 }}>{savedOk}</Alert>}

            {/* ── Action Section ── */}
            <Paper elevation={2} sx={{ p: 3, mb: 4, borderRadius: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                    <Typography variant="h6" fontWeight={600}>
                        1. Template Builder Canvas
                    </Typography>
                    
                    {!preview && (
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={() => {
                                setPreview({
                                    file_type: 'internal',
                                    shape: {},
                                    containers: [],
                                    container_count: 0,
                                    session_type_counts: {}
                                });
                                setEditedContainers([]);
                                setSavedOk('');
                            }}
                            sx={{ fontWeight: 700, borderRadius: 2 }}
                        >
                            + Create New Guideline
                        </Button>
                    )}
                </Box>

                {preview && (
                    <Box sx={{ mt: 3, borderTop: '1px solid #cfd8dc', pt: 3 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                            <Box>
                                <Typography variant="h6" fontWeight={600} gutterBottom>
                                    2. Paint Your Sub-Levels
                                </Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                                    Cycle cells: Lecture → Lab → Tutorial → Empty
                                </Typography>
                                <Stack direction="row" spacing={1} flexWrap="wrap">
                                    <Chip
                                        icon={<CheckCircleIcon />}
                                        label={`${editedContainers.length} total blocks`}
                                        color="success"
                                        size="small"
                                    />
                                    {Object.entries(editedCounts).map(([type, count]) => {
                                        const meta = SESSION_META[type as SessionType];
                                        return (
                                            <Chip
                                                key={type}
                                                label={`${count} x ${meta?.label ?? type}`}
                                                size="small"
                                                sx={{ bgcolor: meta?.bg, color: meta?.color, fontWeight: 700 }}
                                            />
                                        );
                                    })}
                                </Stack>
                            </Box>
                            <Button
                                variant="contained"
                                color="success"
                                size="large"
                                startIcon={<CheckCircleIcon />}
                                onClick={() => setShowSaveDialog(true)}
                                sx={{ borderRadius: 2, px: 4 }}
                            >
                                Save Profile
                            </Button>
                        </Box>

                        <TimetableGridPreview
                            containers={editedContainers}
                            onChange={setEditedContainers}
                        />
                    </Box>
                )}
            </Paper>

            {/* ── Saved Profiles ── */}
            <Paper elevation={2} sx={{ p: 3, borderRadius: 3 }}>
                <Typography variant="h6" fontWeight={600} gutterBottom>Saved Template Profiles</Typography>

                {loadingProfiles ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
                ) : profiles.length === 0 ? (
                    <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                        No profiles saved yet. Click the button above to get started.
                    </Typography>
                ) : (
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                                    <TableCell><strong>Name</strong></TableCell>
                                    <TableCell><strong>School</strong></TableCell>
                                    <TableCell><strong>Format</strong></TableCell>
                                    <TableCell><strong>Blocks</strong></TableCell>
                                    <TableCell><strong>Status</strong></TableCell>
                                    <TableCell><strong>Created</strong></TableCell>
                                    <TableCell align="center"><strong>Actions</strong></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {profiles.map((p) => (
                                    <TableRow key={p.id} hover sx={{ '&:last-child td': { border: 0 } }}>
                                        <TableCell>
                                            <Typography fontWeight={p.is_active ? 700 : 400}>{p.name}</Typography>
                                            {p.original_filename && (
                                                <Typography variant="caption" color="text.secondary">{p.original_filename}</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>{p.school_name || '--'}</TableCell>
                                        <TableCell>
                                            <Chip label={p.file_type.toUpperCase()} size="small" variant="outlined" />
                                        </TableCell>
                                        <TableCell>{p.container_count}</TableCell>
                                        <TableCell>
                                            {p.is_active
                                                ? <Chip icon={<StarIcon />} label="Active" color="primary" size="small" />
                                                : <Chip label="Inactive" size="small" variant="outlined" />
                                            }
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="caption">
                                                {new Date(p.created_at).toLocaleDateString()}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="center">
                                            <Tooltip title="View timetable grid">
                                                <IconButton size="small" onClick={() => handleViewDetail(p)}>
                                                    <VisibilityIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title={p.is_active ? 'Already active' : 'Set as active template'}>
                                                <span>
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => handleActivate(p)}
                                                        disabled={p.is_active}
                                                        color={p.is_active ? 'primary' : 'default'}
                                                    >
                                                        {p.is_active ? <StarIcon fontSize="small" /> : <StarBorderIcon fontSize="small" />}
                                                    </IconButton>
                                                </span>
                                            </Tooltip>
                                            <Tooltip title="Delete profile">
                                                <IconButton size="small" color="error" onClick={() => setDeleteTarget(p)}>
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </Paper>

            {/* ── Save Dialog ── */}
            <Dialog open={showSaveDialog} onClose={() => setShowSaveDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle fontWeight={700}>Save Template Profile</DialogTitle>
                <DialogContent>
                    <TextField
                        label="Profile Name *"
                        value={profileName}
                        onChange={(e) => setProfileName(e.target.value)}
                        fullWidth sx={{ mt: 1, mb: 2 }}
                        placeholder="e.g. Science Faculty 2026"
                    />
                    <TextField
                        label="School / Faculty (optional)"
                        value={schoolName}
                        onChange={(e) => setSchoolName(e.target.value)}
                        fullWidth
                        placeholder="e.g. Faculty of Science"
                    />
                    <Alert severity="info" sx={{ mt: 2 }}>
                        {editedContainers.length} session blocks will be saved.
                    </Alert>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2 }}>
                    <Button onClick={() => setShowSaveDialog(false)} disabled={saving}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleSave}
                        disabled={!profileName.trim() || saving}
                        startIcon={saving ? <CircularProgress size={16} /> : <CheckCircleIcon />}
                    >
                        {saving ? 'Saving...' : 'Save Profile'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* ── View Detail Dialog ── */}
            <Dialog
                open={!!viewProfile}
                onClose={() => setViewProfile(null)}
                maxWidth="xl"
                fullWidth
                PaperProps={{ sx: { borderRadius: 3, height: '90vh' } }}
            >
                <DialogTitle fontWeight={700} sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 1.5 }}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <TableChartIcon color="primary" />
                        <span>{viewProfile?.name}</span>
                        {viewProfile?.is_active && (
                            <Chip icon={<StarIcon />} label="Active" color="primary" size="small" />
                        )}
                    </Stack>
                </DialogTitle>
                <DialogContent sx={{ p: 3, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    {loadingDetail ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                            <CircularProgress />
                        </Box>
                    ) : (
                        <>
                            <Grid container spacing={2} sx={{ mb: 2 }}>
                                <Grid item xs={6}>
                                    <Typography variant="body2" color="text.secondary">School</Typography>
                                    <Typography>{viewProfile?.school_name || '--'}</Typography>
                                </Grid>
                                <Grid item xs={3}>
                                    <Typography variant="body2" color="text.secondary">Format</Typography>
                                    <Chip label={(viewProfile?.file_type || '').toUpperCase()} size="small" variant="outlined" />
                                </Grid>
                                <Grid item xs={3}>
                                    <Typography variant="body2" color="text.secondary">Total Blocks</Typography>
                                    <Typography fontWeight={700}>{viewProfile?.container_count}</Typography>
                                </Grid>
                            </Grid>
                            <Divider sx={{ mb: 2 }} />
                            <Box sx={{ flex: 1, overflow: 'auto' }}>
                                <TimetableGridPreview
                                    containers={viewProfile?.containers || []}
                                    onChange={() => { }} // read-only in view mode
                                    readOnly
                                />
                            </Box>
                        </>
                    )}
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Button onClick={() => setViewProfile(null)}>Close</Button>
                    {viewProfile && !viewProfile.is_active && (
                        <Button
                            variant="contained"
                            startIcon={<StarIcon />}
                            onClick={() => { handleActivate(viewProfile); setViewProfile(null); }}
                        >
                            Set as Active
                        </Button>
                    )}
                </DialogActions>
            </Dialog>

            {/* ── Delete Confirm ── */}
            <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
                <DialogTitle>Delete Profile?</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete <strong>"{deleteTarget?.name}"</strong>? This cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
                    <Button variant="contained" color="error" onClick={handleDelete}>Delete</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
