import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    Collapse,
    CircularProgress,
    Container,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControl,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    Slider,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Add as AddIcon,
    ClearAll as ClearAllIcon,
    Delete as DeleteIcon,
    ExpandMore as ExpandMoreIcon,
    Group as GroupIcon,
    Science as ScienceIcon,
    AccountTree as StreamIcon,
    AutoAwesome as AutoAwesomeIcon,
} from '@mui/icons-material';
import { groupsAPI, departmentsAPI } from '../api';
import { formatGroupLabel } from '../utils/displayFormatters';

interface Group {
    id: number;
    name: string;
    level: number;
    size: number;
    department_id: number;
    group_type: string;
    display_code?: string;
    parent_group_id?: number | null;
}

interface Department {
    id: number;
    name: string;
    code: string;
}

interface TeachingNode {
    id: number;
    parentId: number | null;
    name: string;
    display_code?: string;
    size: number;
    level: number;
    department_id: number;
    kind: 'parent' | 'stream';
    teachingGroups: Group[];
}

const ALPHA_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

function previewNames(mode: string, prefix: string, count: number, customNames: string): string[] {
    if (mode === 'alpha') return ALPHA_LETTERS.slice(0, count);
    if (mode === 'custom') return customNames.split(',').map(s => s.trim()).filter(Boolean).slice(0, count);
    return Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
}

const typeChipStyles: Record<string, { label: string; color?: 'success' | 'warning' | 'info'; sx?: any }> = {
    lab_group: { label: 'Lab', color: 'success' },
    tutorial_group: { label: 'Tutorial', color: 'warning' },
    drawing_group: { label: 'Drawing', color: 'info' },
};

const LabGroupsPage: React.FC = () => {
    const [mainGroups, setMainGroups] = useState<Group[]>([]);
    const [departments, setDepartments] = useState<Department[]>([]);
    const [streamMap, setStreamMap] = useState<Record<number, Group[]>>({});
    const [teachingGroupMap, setTeachingGroupMap] = useState<Record<number, Group[]>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

    const [genDialog, setGenDialog] = useState<{
        open: boolean;
        targetId: number;
        targetName: string;
        targetKind: 'parent' | 'stream';
    }>({
        open: false,
        targetId: 0,
        targetName: '',
        targetKind: 'parent',
    });
    const [genForm, setGenForm] = useState({
        naming_mode: 'alpha' as 'alpha' | 'numeric' | 'custom',
        prefix: 'L',
        count: 4,
        size_per_group: 10,
        group_type: 'lab_group',
        custom_names: '',
    });
    const [generating, setGenerating] = useState(false);
    const [genError, setGenError] = useState('');

    const deptName = (id: number) => departments.find(d => d.id === id)?.name ?? `Dept ${id}`;
    const levelLabel = (l: number) => {
        const year = l >= 100 ? Math.round(l / 100) : l;
        return `Year ${year}`;
    };

    const fetchAll = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const [groups, depts] = await Promise.all([
                groupsAPI.getByTier('main'),
                departmentsAPI.getAll(),
            ]);
            setMainGroups(groups);
            setDepartments(depts);

            const streamsByParentEntries = await Promise.all(
                groups.map(async (group: Group) => ({
                    parentId: group.id,
                    streams: await groupsAPI.getStreams(group.id).catch(() => []),
                })),
            );

            const nextStreamMap: Record<number, Group[]> = {};
            streamsByParentEntries.forEach(({ parentId, streams }) => {
                nextStreamMap[parentId] = streams;
            });
            setStreamMap(nextStreamMap);

            const allNodeIds = [
                ...groups.map((group: Group) => group.id),
                ...streamsByParentEntries.flatMap(({ streams }) => streams.map((stream: Group) => stream.id)),
            ];

            const teachingEntries = await Promise.all(
                allNodeIds.map(async (nodeId) => ({
                    nodeId,
                    teachingGroups: (await groupsAPI.getSubgroups(nodeId).catch(() => []))
                        .filter((group: Group) => ['lab_group', 'tutorial_group', 'drawing_group'].includes(group.group_type)),
                })),
            );

            const nextTeachingGroupMap: Record<number, Group[]> = {};
            teachingEntries.forEach(({ nodeId, teachingGroups }) => {
                nextTeachingGroupMap[nodeId] = teachingGroups;
            });
            setTeachingGroupMap(nextTeachingGroupMap);
        } catch {
            setError('Failed to load lab and tutorial group data. Please refresh.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void fetchAll();
    }, [fetchAll]);

    const openGenDialog = (targetId: number, targetName: string, targetKind: 'parent' | 'stream') => {
        setGenForm({
            naming_mode: 'alpha',
            prefix: targetKind === 'stream' ? 'S' : 'L',
            count: 4,
            size_per_group: 10,
            group_type: 'lab_group',
            custom_names: '',
        });
        setGenError('');
        setGenDialog({ open: true, targetId, targetName, targetKind });
    };

    const handleGenerate = async () => {
        setGenError('');
        if (genForm.size_per_group < 4 || genForm.size_per_group > 13) {
            setGenError('Teaching subgroup size must be between 4 and 13 students.');
            return;
        }

        setGenerating(true);
        try {
            const payload: any = {
                count: genForm.count,
                size_per_group: genForm.size_per_group,
                group_type: genForm.group_type,
                naming_mode: genForm.naming_mode,
                prefix: genForm.prefix,
            };
            if (genForm.naming_mode === 'custom') {
                payload.custom_names = genForm.custom_names.split(',').map(s => s.trim()).filter(Boolean);
            }

            await groupsAPI.generateSubgroups(genDialog.targetId, payload);
            setGenDialog((prev) => ({ ...prev, open: false }));
            setSuccess(`${genForm.group_type.replace('_', ' ')} groups created for "${genDialog.targetName}"`);
            void fetchAll();
        } catch (e: any) {
            setGenError(e.response?.data?.detail || 'Failed to generate teaching subgroups.');
        } finally {
            setGenerating(false);
        }
    };

    const handleDeleteSubgroup = async (parentId: number, subgroupId: number, name: string) => {
        if (!window.confirm(`Delete "${name}"?`)) return;
        try {
            await groupsAPI.deleteSubgroup(parentId, subgroupId);
            setSuccess(`Deleted "${name}"`);
            void fetchAll();
        } catch {
            setError('Failed to delete subgroup.');
        }
    };

    const handleClearAll = async (parentId: number, parentName: string) => {
        if (!window.confirm(`Delete all teaching groups under "${parentName}"? This cannot be undone.`)) return;
        try {
            const res = await groupsAPI.deleteAllSubgroups(parentId);
            setSuccess(`Deleted ${res?.deleted ?? 0} teaching groups from "${parentName}"`);
            void fetchAll();
        } catch {
            setError('Failed to clear teaching groups.');
        }
    };

    const preview = previewNames(genForm.naming_mode, genForm.prefix, genForm.count, genForm.custom_names);

    const getNodeKey = (kind: 'parent' | 'stream', id: number) => `${kind}-${id}`;
    const isNodeExpanded = (kind: 'parent' | 'stream', id: number) => expandedNodes[getNodeKey(kind, id)] ?? true;
    const toggleNodeExpanded = (kind: 'parent' | 'stream', id: number) => {
        const key = getNodeKey(kind, id);
        setExpandedNodes((prev) => ({
            ...prev,
            [key]: !(prev[key] ?? true),
        }));
    };

    const treeData = useMemo(() => (
        mainGroups.map((group) => ({
            parent: group,
            streams: (streamMap[group.id] ?? []).sort((a, b) => a.name.localeCompare(b.name)),
        }))
    ), [mainGroups, streamMap]);

    const renderTeachingNode = (node: TeachingNode) => {
        const teachingGroups = teachingGroupMap[node.id] ?? [];
        const isStream = node.kind === 'stream';

        return (
            <Box
                key={node.id}
                sx={{
                    ml: isStream ? 4 : 0,
                    mt: isStream ? 1.5 : 0,
                    pl: isStream ? 2.5 : 0,
                    borderLeft: isStream ? '2px solid rgba(124,58,237,0.22)' : 'none',
                }}
            >
                <Card
                    variant="outlined"
                    sx={{
                        borderRadius: 3,
                        borderColor: isStream ? 'rgba(124,58,237,0.28)' : 'rgba(59,130,246,0.18)',
                        bgcolor: isStream ? 'rgba(124,58,237,0.03)' : '#ffffff',
                    }}
                >
                    <CardContent sx={{ p: 2.25 }}>
                        <Box
                            sx={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                alignItems: 'center',
                                gap: 1.25,
                                mb: 1.5,
                            }}
                        >
                            {isStream ? <StreamIcon color="secondary" fontSize="small" /> : <GroupIcon color="primary" fontSize="small" />}
                            <Typography variant="subtitle1" fontWeight={700}>
                                {node.name}
                            </Typography>
                            <Chip label={isStream ? 'Elective Stream' : 'Parent Cohort'} size="small" color={isStream ? 'secondary' : 'primary'} variant={isStream ? 'filled' : 'outlined'} />
                            <Chip label={levelLabel(node.level)} size="small" variant="outlined" />
                            <Chip label={`${node.size} students`} size="small" variant="outlined" />
                            <Chip label={deptName(node.department_id)} size="small" variant="outlined" />
                        </Box>

                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1.75 }}>
                            <Button
                                size="small"
                                variant="contained"
                                color="success"
                                startIcon={<AddIcon />}
                                onClick={() => openGenDialog(node.id, node.name, node.kind)}
                            >
                                Add Labs / Tutorials
                            </Button>
                            {teachingGroups.length > 0 && (
                                <Button
                                    size="small"
                                    variant="outlined"
                                    color="error"
                                    startIcon={<ClearAllIcon />}
                                    onClick={() => handleClearAll(node.id, node.name)}
                                >
                                    Clear All
                                </Button>
                            )}
                        </Box>

                        {teachingGroups.length === 0 ? (
                            <Alert severity="info" sx={{ py: 0.5 }}>
                                No lab, tutorial, or drawing groups created under this {isStream ? 'stream' : 'cohort'} yet.
                            </Alert>
                        ) : (
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                                {teachingGroups.map((group) => {
                                    const meta = typeChipStyles[group.group_type] || { label: group.group_type };
                                    return (
                                        <Card
                                            key={group.id}
                                            variant="outlined"
                                            sx={{
                                                minWidth: 165,
                                                flex: '0 1 180px',
                                                borderRadius: 2,
                                                bgcolor: 'rgba(248,250,252,0.85)',
                                            }}
                                        >
                                            <CardContent sx={{ p: 1.25, '&:last-child': { pb: 1.25 } }}>
                                                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                                                    <Box>
                                                        <Typography variant="body2" fontWeight={700}>
                                                            {formatGroupLabel(group, true)}
                                                        </Typography>
                                                        <Typography variant="caption" color="text.secondary">
                                                            {group.size} students
                                                        </Typography>
                                                    </Box>
                                                    <Tooltip title="Delete teaching group">
                                                        <IconButton
                                                            size="small"
                                                            color="error"
                                                            onClick={() => handleDeleteSubgroup(node.id, group.id, formatGroupLabel(group))}
                                                        >
                                                            <DeleteIcon fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                </Box>
                                                <Chip
                                                    label={meta.label}
                                                    size="small"
                                                    color={meta.color}
                                                    sx={{ mt: 0.75, fontSize: '0.68rem' }}
                                                />
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </Box>
                        )}
                    </CardContent>
                </Card>
            </Box>
        );
    };

    return (
        <Container maxWidth={false} sx={{ mt: 3, mb: 4 }}>
            <Card sx={{ mb: 3, background: 'linear-gradient(135deg, #0f172a 0%, #1a3a4f 100%)', color: 'white' }}>
                <CardContent sx={{ py: 2.25, px: 3 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <ScienceIcon sx={{ fontSize: 38, color: '#34d399' }} />
                        <Box>
                            <Typography variant="h5" fontWeight="bold" color="white">Lab & Tutorial Groups</Typography>
                            <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                                Create lab, tutorial, and drawing groups from parent cohorts or their elective streams in one clean tree view.
                            </Typography>
                        </Box>
                    </Box>
                </CardContent>
            </Card>

            {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>{success}</Alert>}

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
                    <CircularProgress size={48} />
                </Box>
            ) : treeData.length === 0 ? (
                <Alert severity="info">
                    No parent cohorts found. Create cohorts and elective streams from the Student Groups page first.
                </Alert>
            ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {treeData.map(({ parent, streams }) => (
                        <Card key={parent.id} sx={{ borderRadius: 4, boxShadow: '0 8px 24px rgba(15,23,42,0.06)' }}>
                            <CardContent sx={{ p: 2.5 }}>
                                <Box
                                    onClick={() => toggleNodeExpanded('parent', parent.id)}
                                    sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: isNodeExpanded('parent', parent.id) ? 2 : 0, cursor: 'pointer' }}
                                >
                                    <ExpandMoreIcon
                                        sx={{
                                            color: '#64748b',
                                            transition: 'transform 0.2s ease',
                                            transform: isNodeExpanded('parent', parent.id) ? 'rotate(0deg)' : 'rotate(-90deg)',
                                        }}
                                    />
                                    <Typography variant="h6" fontWeight={800}>
                                        {parent.name}
                                    </Typography>
                                    <Chip label={`${streams.length} elective stream${streams.length === 1 ? '' : 's'}`} size="small" color="secondary" variant="outlined" />
                                </Box>

                                <Collapse in={isNodeExpanded('parent', parent.id)} timeout={220}>
                                    {renderTeachingNode({
                                        id: parent.id,
                                        parentId: null,
                                        name: parent.name,
                                        display_code: parent.display_code,
                                        size: parent.size,
                                        level: parent.level,
                                        department_id: parent.department_id,
                                        kind: 'parent',
                                        teachingGroups: teachingGroupMap[parent.id] ?? [],
                                    })}

                                    {streams.length > 0 && (
                                        <Box sx={{ mt: 2.25 }}>
                                            <Typography
                                                variant="overline"
                                                sx={{ color: '#7c3aed', fontWeight: 800, letterSpacing: 0.7 }}
                                            >
                                                Elective Streams
                                            </Typography>
                                            <Box sx={{ mt: 0.75 }}>
                                                {streams.map((stream) => renderTeachingNode({
                                                    id: stream.id,
                                                    parentId: parent.id,
                                                    name: stream.name,
                                                    display_code: stream.display_code,
                                                    size: stream.size,
                                                    level: stream.level,
                                                    department_id: stream.department_id,
                                                    kind: 'stream',
                                                    teachingGroups: teachingGroupMap[stream.id] ?? [],
                                                }))}
                                            </Box>
                                        </Box>
                                    )}
                                </Collapse>
                            </CardContent>
                        </Card>
                    ))}
                </Box>
            )}

            <Dialog open={genDialog.open} onClose={() => setGenDialog(prev => ({ ...prev, open: false }))} maxWidth="sm" fullWidth>
                <DialogTitle>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <AutoAwesomeIcon color="success" />
                        Add Teaching Groups — <em>{genDialog.targetName}</em>
                    </Box>
                </DialogTitle>
                <DialogContent dividers>
                    {genError && <Alert severity="error" sx={{ mb: 2 }}>{genError}</Alert>}
                    <Alert severity="info" sx={{ mb: 2 }}>
                        You are creating lab, tutorial, or drawing groups under a {genDialog.targetKind === 'stream' ? 'stream' : 'parent cohort'}.
                    </Alert>

                    <FormControl fullWidth sx={{ mb: 2 }}>
                        <InputLabel>Group Type</InputLabel>
                        <Select
                            value={genForm.group_type}
                            label="Group Type"
                            onChange={(e) => setGenForm((prev) => ({ ...prev, group_type: e.target.value }))}
                        >
                            <MenuItem value="lab_group">Lab Group</MenuItem>
                            <MenuItem value="tutorial_group">Tutorial Group</MenuItem>
                            <MenuItem value="drawing_group">Drawing Group</MenuItem>
                        </Select>
                    </FormControl>

                    <FormControl fullWidth sx={{ mb: 2 }}>
                        <InputLabel>Naming Mode</InputLabel>
                        <Select
                            value={genForm.naming_mode}
                            label="Naming Mode"
                            onChange={(e) => setGenForm((prev) => ({ ...prev, naming_mode: e.target.value as 'alpha' | 'numeric' | 'custom' }))}
                        >
                            <MenuItem value="alpha">Letters Only — A, B, C, D...</MenuItem>
                            <MenuItem value="numeric">Prefix + Number — L1, L2, T1...</MenuItem>
                            <MenuItem value="custom">Custom names</MenuItem>
                        </Select>
                    </FormControl>

                    {genForm.naming_mode === 'numeric' && (
                        <FormControl fullWidth sx={{ mb: 2 }}>
                            <InputLabel>Prefix</InputLabel>
                            <Select
                                value={genForm.prefix}
                                label="Prefix"
                                onChange={(e) => setGenForm((prev) => ({ ...prev, prefix: e.target.value }))}
                            >
                                <MenuItem value="L">L</MenuItem>
                                <MenuItem value="T">T</MenuItem>
                                <MenuItem value="D">D</MenuItem>
                                <MenuItem value="S">S</MenuItem>
                            </Select>
                        </FormControl>
                    )}

                    {genForm.naming_mode === 'custom' && (
                        <FormControl fullWidth sx={{ mb: 2 }}>
                            <InputLabel shrink>Custom Names</InputLabel>
                            <Select
                                native={false}
                                value=""
                                displayEmpty
                                renderValue={() => 'Use the field below'}
                                disabled
                                sx={{ display: 'none' }}
                            />
                            <Box sx={{ mt: 0.5 }}>
                                <textarea
                                    value={genForm.custom_names}
                                    onChange={(e) => setGenForm((prev) => ({ ...prev, custom_names: e.target.value }))}
                                    rows={3}
                                    style={{
                                        width: '100%',
                                        borderRadius: 8,
                                        border: '1px solid rgba(0,0,0,0.23)',
                                        padding: 12,
                                        font: 'inherit',
                                        resize: 'vertical',
                                    }}
                                    placeholder="Enter names separated by commas, e.g. A1, A2, B1, B2"
                                />
                            </Box>
                        </FormControl>
                    )}

                    <Typography gutterBottom>
                        Number of Groups: <strong>{genForm.count}</strong>
                    </Typography>
                    <Slider
                        value={genForm.count}
                        min={2}
                        max={20}
                        step={1}
                        marks={[{ value: 2, label: '2' }, { value: 10, label: '10' }, { value: 20, label: '20' }]}
                        onChange={(_, value) => setGenForm((prev) => ({ ...prev, count: value as number }))}
                        sx={{ mb: 3 }}
                    />

                    <Typography gutterBottom>
                        Size per Group: <strong>{genForm.size_per_group} students</strong>
                    </Typography>
                    <Slider
                        value={genForm.size_per_group}
                        min={4}
                        max={13}
                        step={1}
                        marks={[{ value: 4, label: '4' }, { value: 8, label: '8' }, { value: 13, label: '13' }]}
                        onChange={(_, value) => setGenForm((prev) => ({ ...prev, size_per_group: value as number }))}
                        sx={{ mb: 2 }}
                    />

                    <Divider sx={{ my: 2 }} />
                    <Typography variant="subtitle2" gutterBottom>Preview</Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                        {preview.map((label, index) => (
                            <Chip
                                key={`${label}-${index}`}
                                label={`${genDialog.targetName} - ${label}`}
                                size="small"
                                color="success"
                                variant="outlined"
                            />
                        ))}
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setGenDialog(prev => ({ ...prev, open: false }))} color="inherit">Cancel</Button>
                    <Button
                        onClick={handleGenerate}
                        variant="contained"
                        color="success"
                        disabled={generating}
                        startIcon={generating ? <CircularProgress size={16} /> : <AddIcon />}
                    >
                        {generating ? 'Creating...' : 'Create Groups'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
};

export default LabGroupsPage;
