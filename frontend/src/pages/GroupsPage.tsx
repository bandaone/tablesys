import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Alert,
  Chip,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Grid,
  LinearProgress,
  Fade,
  Collapse,
} from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon, Upload as UploadIcon, CallSplit as CallSplitIcon, MenuBook as MenuBookIcon, KeyboardArrowRight as ExpandIcon } from '@mui/icons-material';
import { groupsAPI, departmentsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { GroupCourseManager } from '../components/GroupCourseManager';
import TableSkeleton from '../components/skeletons/TableSkeleton';
import { formatGroupLabel } from '../utils/displayFormatters';

type GroupType = 'general' | 'department' | 'stream' | 'lab_group' | 'tutorial_group' | 'drawing_group';

interface Group {
  id: number;
  name: string;
  level: number;
  size: number;
  department_id: number;
  group_type?: GroupType;
  display_code?: string;
  parent_group_id?: number | null;
  preferred_venues?: Record<string, number>;
}

const GroupsPage: React.FC = () => {
  const [groups, setGroups] = useState<Group[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [rooms, setRooms] = useState<any[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openUploadDialog, setOpenUploadDialog] = useState(false);
  const [editingGroup, setEditingGroup] = useState<Group | null>(null);
  const [error, setError] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [formData, setFormData] = useState({
    name: '',
    level: 2,
    size: 30,
    department_id: 1,
    group_type: 'department',
    display_code: '',
    parent_group_id: undefined as number | undefined | null,
    preferred_venues: {} as Record<string, number>,
  });

  const [openSubdivideDialog, setOpenSubdivideDialog] = useState(false);
  const [subdivideTarget, setSubdivideTarget] = useState<Group | null>(null);
  const [subdivideForm, setSubdivideForm] = useState({
    count: 2,
    type: 'stream' as 'stream' | 'lab_group' | 'tutorial_group' | 'drawing_group'
  });
  const [subgroupSizes, setSubgroupSizes] = useState<number[]>([]);

  const [openCourseManager, setOpenCourseManager] = useState(false);
  const [courseManagerTarget, setCourseManagerTarget] = useState<Group | null>(null);
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});

  const { isCoordinator } = useAuth();


  useEffect(() => {
    Promise.all([
      fetchGroups(),
      fetchDepartments(),
      fetchRooms(),
    ]).finally(() => setPageLoading(false));
  }, []);

  const fetchRooms = async () => {
    try {
      const { roomsAPI } = await import('../api');
      const data = await roomsAPI.getAll();
      setRooms(data);
    } catch (err) {
      console.error('Failed to load rooms');
    }
  };

  const fetchDepartments = async () => {
    try {
      const data = await departmentsAPI.getAll();
      setDepartments(data);
    } catch (err) {
      console.error('Failed to load departments');
    }
  };

  const fetchGroups = async () => {
    try {
      const data = await groupsAPI.getAll();
      // Lab, tutorial and drawing groups are scheduling delivery detail. They
      // are managed on Lab Scheduling, not nested into the academic cohort /
      // stream tree where they make the mapping view unreadable.
      setGroups(data.filter((group: Group) => !['lab_group', 'tutorial_group', 'drawing_group'].includes(group.group_type || 'department')));
    } catch (err) {
      setError('Failed to load groups');
    }
  };

  const handleOpenDialog = (group?: Group) => {
    if (group) {
      setEditingGroup(group);
      setFormData({
        name: group.name,
        level: group.level,
        size: group.size,
        department_id: group.department_id,
        group_type: group.group_type || 'department',
        display_code: group.display_code || '',
        parent_group_id: group.parent_group_id,
        preferred_venues: group.preferred_venues || {},
      });
    } else {
      setEditingGroup(null);
      setFormData({
        name: '',
        level: 2,
        size: 30,
        department_id: 1,
        group_type: 'department',
        display_code: '',
        parent_group_id: undefined,
        preferred_venues: {},
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingGroup(null);
    setError('');
  };

  const handleSubmit = async () => {
    try {
      if (editingGroup) {
        await groupsAPI.update(editingGroup.id, formData);
      } else {
        await groupsAPI.create(formData);
      }
      await fetchGroups();
      handleCloseDialog();
    } catch (err) {
      setError('Failed to save group');
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this group?')) {
      try {
        await groupsAPI.delete(id);
        await fetchGroups();
      } catch (err) {
        setError('Failed to delete group');
      }
    }
  };

  const handleOpenSubdivide = (group: Group) => {
    setSubdivideTarget(group);
    const defaultCount = 2;
    const baseSize = Math.floor(group.size / defaultCount);
    const remainder = group.size % defaultCount;
    setSubgroupSizes(Array.from({ length: defaultCount }, (_, i) => baseSize + (i < remainder ? 1 : 0)));
    setSubdivideForm({ count: defaultCount, type: 'stream' });
    setOpenSubdivideDialog(true);
  };

  const handleSubdivideCountChange = (newCount: number) => {
    if (!subdivideTarget) return;
    const baseSize = Math.floor(subdivideTarget.size / newCount);
    const remainder = subdivideTarget.size % newCount;
    setSubgroupSizes(Array.from({ length: newCount }, (_, i) => baseSize + (i < remainder ? 1 : 0)));
    setSubdivideForm(prev => ({ ...prev, count: newCount }));
  };

  const handleSubgroupSizeChange = (idx: number, val: number) => {
    setSubgroupSizes(prev => prev.map((s, i) => i === idx ? val : s));
  };

  const handleSubdivideSubmit = async () => {
    if (!subdivideTarget) return;
    
    const totalSubgroupSize = subgroupSizes.reduce((sum, size) => sum + size, 0);
    if (totalSubgroupSize > subdivideTarget.size) {
        setError(`Total stream sizes (${totalSubgroupSize}) cannot exceed the parent cohort size (${subdivideTarget.size}). Please adjust the numbers.`);
        return;
    }

    setLoading(true);
    try {
      const promises = [];
      for (let i = 1; i <= subdivideForm.count; i++) {
        const groupSize = subgroupSizes[i - 1] ?? Math.floor(subdivideTarget.size / subdivideForm.count);
        promises.push(
          groupsAPI.create({
            name: `${subdivideTarget.name} Elective ${i}`,
            level: subdivideTarget.level,
            size: groupSize,
            department_id: subdivideTarget.department_id,
            group_type: 'stream',
            parent_group_id: subdivideTarget.id,
            display_code: `${subdivideTarget.display_code || ''} E${i}`.trim(),
            preferred_venues: {},
          })
        );
      }
      await Promise.all(promises);
      await fetchGroups();
      setOpenSubdivideDialog(false);
      setSubdivideTarget(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to subdivide group');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleBulkUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file');
      return;
    }

    setLoading(true);
    setError('');
    setUploadResult(null);

    try {
      const result = await groupsAPI.bulkUpload(selectedFile);
      setUploadResult(result);
      fetchGroups();
      setTimeout(() => {
        setOpenUploadDialog(false);
        setSelectedFile(null);
        setUploadResult(null);
        const input = document.getElementById('group-file-upload') as HTMLInputElement;
        if (input) input.value = '';
      }, 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error uploading file');
    } finally {
      setLoading(false);
    }
  };

  // Normalise stored level to single digit (handles both 3 and 300 formats)
  const normaliseLevel = (level: number) => level >= 100 ? Math.round(level / 100) : level;

  const getLevelColor = (level: number) => {
    const n = normaliseLevel(level);
    const colors: Record<number, 'success' | 'info' | 'warning' | 'error'> = {
      1: 'success',
      2: 'success',
      3: 'info',
      4: 'warning',
      5: 'error',
    };
    return colors[n] || 'default';
  };

  const getTypeChip = (type: GroupType | undefined) => {
    switch (type) {
      case 'stream':        return <Chip label="Stream" size="small" sx={{ bgcolor: '#1976d2', color: '#fff', fontWeight: 600, fontSize: '0.68rem' }} />;
      case 'general':       return <Chip label="General" size="small" sx={{ bgcolor: '#0284c7', color: '#fff', fontWeight: 600, fontSize: '0.68rem' }} />;
      default:              return <Chip label="Department" size="small" variant="outlined" sx={{ fontSize: '0.68rem' }} />;
    }
  };

  const getDepartmentCode = (deptId: number) => {
    const dept = departments.find(d => d.id === deptId);
    return dept ? (dept.code || dept.name.substring(0, 3).toUpperCase()) : 'UNK';
  };

  const toggleExpandedRow = (groupId: number) => {
    setExpandedRows(prev => ({
      ...prev,
      [groupId]: !prev[groupId],
    }));
  };

  const knownGroupIds = useMemo(() => {
    const ids = new Set<number>();
    groups.forEach(group => ids.add(group.id));
    return ids;
  }, [groups]);

  const childGroupsMap = useMemo(() => {
    const map: Record<number, Group[]> = {};

    groups.forEach(group => {
      if (!group.parent_group_id) return;
      if (!map[group.parent_group_id]) {
        map[group.parent_group_id] = [];
      }
      map[group.parent_group_id].push(group);
    });

    Object.values(map).forEach(children => {
      children.sort((a, b) => {
        const levelDiff = normaliseLevel(a.level) - normaliseLevel(b.level);
        if (levelDiff !== 0) return levelDiff;
        if (a.group_type !== b.group_type) {
          return (a.group_type || '').localeCompare(b.group_type || '');
        }
        return a.name.localeCompare(b.name);
      });
    });

    return map;
  }, [groups]);

  const rootGroups = useMemo(() => {
    return groups
      .filter(group => !group.parent_group_id || !knownGroupIds.has(group.parent_group_id))
      .sort((a, b) => {
        const levelDiff = normaliseLevel(a.level) - normaliseLevel(b.level);
        if (levelDiff !== 0) return levelDiff;
        if (a.group_type !== b.group_type) {
          return (a.group_type || '').localeCompare(b.group_type || '');
        }
        return a.name.localeCompare(b.name);
      });
  }, [groups, knownGroupIds]);

  const getChildSummary = (children: Group[]) => {
    const streamCount = children.filter(child => child.group_type === 'stream').length;
    if (streamCount === children.length) {
      return `${streamCount} stream${streamCount > 1 ? 's' : ''}`;
    }
    return `${children.length} child group${children.length > 1 ? 's' : ''}`;
  };

  const renderActionButtons = (group: Group) => {
    return (
      <>
        <IconButton
          size="small"
          sx={{ color: '#0284c7' }}
          title={group.group_type === 'stream' ? 'Manage Stream Courses' : 'Manage Group Courses'}
          onClick={() => {
            setCourseManagerTarget(group);
            setOpenCourseManager(true);
          }}
        >
          <MenuBookIcon />
        </IconButton>
        {group.group_type !== 'stream' && (
          <IconButton
            size="small"
            color="secondary"
            title="Create Elective Streams"
            onClick={() => { handleOpenSubdivide(group); }}
          >
            <CallSplitIcon />
          </IconButton>
        )}
        <IconButton
          size="small"
          color="primary"
          title="Edit"
          onClick={() => { handleOpenDialog(group); }}
        >
          <EditIcon />
        </IconButton>
        <IconButton
          size="small"
          color="error"
          onClick={() => { void handleDelete(group.id); }}
        >
          <DeleteIcon />
        </IconButton>
      </>
    );
  };

  const renderTreeRow = (group: Group, depth = 0): React.ReactNode => {
    const children = childGroupsMap[group.id] ?? [];
    const hasChildren = children.length > 0;
    const isExpanded = Boolean(expandedRows[group.id]);
    const isStream = group.group_type === 'stream';

    return (
      <React.Fragment key={`group-${group.id}`}>
        <TableRow
          hover
          sx={{
            bgcolor: isStream ? 'rgba(0,104,55,0.03)' : depth > 0 ? 'rgba(253,185,19,0.03)' : 'inherit',
            borderLeft: isStream ? '3px solid #1976d2' : 'none',
          }}
        >
          <TableCell>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: depth * 2 }}>
              {hasChildren ? (
                <IconButton
                  size="small"
                  aria-label={isExpanded ? 'Collapse child groups' : 'Expand child groups'}
                  onClick={() => { toggleExpandedRow(group.id); }}
                  sx={{
                    transition: 'transform 0.25s ease',
                    transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                  }}
                >
                  <ExpandIcon fontSize="small" />
                </IconButton>
              ) : (
                <Box sx={{ width: 34 }} />
              )}

              {depth > 0 && (
                <Box sx={{ width: 10, height: 2, bgcolor: 'divider', borderRadius: 99 }} />
              )}

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
                <Typography
                  variant="body1"
                  fontWeight={isStream ? 500 : 'medium'}
                  sx={{ cursor: hasChildren ? 'pointer' : 'default' }}
                  onClick={hasChildren ? () => { toggleExpandedRow(group.id); } : undefined}
                >
                  {formatGroupLabel(group)}
                </Typography>
                {hasChildren && (
                  <Typography variant="caption" color="text.secondary">
                    {getChildSummary(children)}
                  </Typography>
                )}
              </Box>
            </Box>
          </TableCell>
          <TableCell>{getTypeChip(group.group_type)}</TableCell>
          <TableCell>
            <Chip label={getDepartmentCode(group.department_id)} size="small" variant="outlined" />
          </TableCell>
          <TableCell>
            <Chip label={`Year ${normaliseLevel(group.level)}`} color={getLevelColor(group.level)} size="small" />
          </TableCell>
          <TableCell>
            <Chip label={`${group.size} students`} variant="outlined" size="small" />
          </TableCell>
          <TableCell align="center">{renderActionButtons(group)}</TableCell>
        </TableRow>

        {hasChildren && (
          <TableRow>
            <TableCell colSpan={6} sx={{ p: 0, borderBottom: isExpanded ? '1px solid rgba(0,0,0,0.05)' : 'none' }}>
              <Collapse in={isExpanded} timeout={280} unmountOnExit>
                <Box sx={{ pl: 2.5, pr: 1.5, py: 0.5 }}>
                  <Table size="small" sx={{ '& .MuiTableCell-root': { borderBottom: '1px dashed rgba(0,0,0,0.05)' } }}>
                    <TableBody>
                      {children.map(child => renderTreeRow(child, depth + 1))}
                    </TableBody>
                  </Table>
                </Box>
              </Collapse>
            </TableCell>
          </TableRow>
        )}
      </React.Fragment>
    );
  };

  return (
    <Fade in timeout={600}>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" fontWeight="bold">
            Student Groups
          </Typography>
          {isCoordinator && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                startIcon={<UploadIcon />}
                onClick={() => { setOpenUploadDialog(true); }}
                sx={{
                  transition: 'all 0.3s ease',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: '0 4px 12px rgba(0,104,55,0.2)',
                  },
                }}
              >
                Bulk Upload
              </Button>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => { handleOpenDialog(); }}
                sx={{
                  background: 'linear-gradient(135deg, #1976d2 0%, #115293 100%)',
                  transition: 'all 0.3s ease',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: '0 6px 16px rgba(0,104,55,0.3)',
                  },
                }}
              >
                Add Group
              </Button>
            </Box>
          )}
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => { setError(''); }}>
            {error}
          </Alert>
        )}

        {!pageLoading && rootGroups.length > 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Click the arrow beside a main group to smoothly open its child groups.
          </Typography>
        )}

        {pageLoading ? (
          <TableSkeleton columns={6} rows={8} />
        ) : (
          <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 3, border: '1px solid rgba(0,0,0,0.06)', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}>
            <Table sx={{ '& .MuiTableCell-root': { borderBottom: '1px solid rgba(0,0,0,0.05)' }}}>
            <TableHead sx={{ bgcolor: '#f8fafc' }}>
              <TableRow>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Group Name</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Type</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Dept</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Level</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Size</TableCell>
                <TableCell align="center" sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rootGroups.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                    <Typography variant="body1" color="text.secondary">
                      No student groups found. Click "Add Group" to create a cohort first.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                rootGroups.map(group => renderTreeRow(group))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        )}

        <Dialog open={openDialog} onClose={() => { setOpenDialog(false); }} maxWidth="sm" fullWidth>
          <DialogTitle>
            {editingGroup ? 'Edit Cohort or Stream' : 'Add Cohort or Stream'}
          </DialogTitle>
          <DialogContent>
            <TextField
              fullWidth
              label="Group Name"
              value={formData.name}
              onChange={(e: any) => { setFormData({ ...formData, name: e.target.value }); }}
              margin="normal"
              required
              placeholder="e.g., EEE-4, MEC-3, EEE-4 Power"
              helperText="Create cohorts here, or attach an elective stream to a parent cohort."
            />
            <FormControl fullWidth margin="normal" required>
              <InputLabel>Department</InputLabel>
              <Select
                value={formData.department_id}
                label="Department"
                onChange={(e: any) => { setFormData({ ...formData, department_id: e.target.value as number }); }}
              >
                {departments.map((dept: any) => (
                  <MenuItem key={dept.id} value={dept.id}>
                    {dept.name} ({dept.code})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label="Display Code"
              value={formData.display_code}
              onChange={(e: any) => { setFormData({ ...formData, display_code: e.target.value }); }}
              margin="normal"
              placeholder="e.g., AEN"
              helperText="Short code for timetable grid (e.g., AEN)"
            />
            <FormControl fullWidth margin="normal">
              <InputLabel>Group Type</InputLabel>
              <Select
                value={formData.group_type}
                label="Group Type"
                onChange={(e: any) => { setFormData({ ...formData, group_type: e.target.value as any }); }}
              >
                <MenuItem value="general">General (cross-school)</MenuItem>
                <MenuItem value="department">Department Year Group</MenuItem>
                <MenuItem value="stream">Elective Stream</MenuItem>
              </Select>
            </FormControl>

            {formData.group_type === 'stream' && (
              <FormControl fullWidth margin="normal">
                <InputLabel>Parent Cohort</InputLabel>
                <Select
                  value={formData.parent_group_id || ''}
                  label="Parent Cohort"
                  onChange={(e: any) => { setFormData({ ...formData, parent_group_id: Number(e.target.value) }); }}
                >
                  <MenuItem value=""><em>None</em></MenuItem>
                  {groups
                    .filter(g => {
                      const deptCode = departments.find(d => d.id === g.department_id)?.code?.toUpperCase();
                      const isGeneral = deptCode === 'GEN' || deptCode === 'ENG';
                      return g.level === formData.level && (g.department_id === formData.department_id || isGeneral) && g.group_type !== 'stream';
                    })
                    .map((g) => (
                      <MenuItem key={g.id} value={g.id}>
                        {formatGroupLabel(g)}
                      </MenuItem>
                    ))}
                </Select>
              </FormControl>
            )}
            <TextField
              fullWidth
              type="number"
              label="Level"
              value={formData.level}
              onChange={(e: any) => { setFormData({ ...formData, level: parseInt(e.target.value) || 1 }); }}
              margin="normal"
              required
              inputProps={{ min: 1, max: 20 }}
            />
            <TextField
              fullWidth
              label="Group Size"
              type="number"
              value={formData.size}
              onChange={(e: any) => { setFormData({ ...formData, size: parseInt(e.target.value) }); }}
              margin="normal"
              required
              inputProps={{ min: 1, max: 200 }}
              helperText="Number of students in this group"
            />

            <Box sx={{ mt: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                School Ground Assessment (Venue Priority)
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                Set which specific rooms this group should prioritize (1-10).
              </Typography>

              <Grid container spacing={1} alignItems="center">
                <Grid item xs={7}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Target Venue</InputLabel>
                    <Select
                      label="Target Venue"
                      value=""
                      onChange={(e: any) => {
                        const roomId = e.target.value as string;
                        if (roomId && !formData.preferred_venues[roomId]) {
                          setFormData({
                            ...formData,
                            preferred_venues: { ...formData.preferred_venues, [roomId]: 10 }
                          });
                        }
                      }}
                    >
                      {rooms.map(r => (
                        <MenuItem key={r.id} value={String(r.id)}>{r.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={5}>
                  <Typography variant="caption">Select to add priority</Typography>
                </Grid>
              </Grid>

              <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {Object.entries(formData.preferred_venues).map(([roomId, priority]) => {
                  const room = rooms.find(r => String(r.id) === roomId);
                  return (
                    <Chip
                      key={roomId}
                      label={`${room?.name || 'Venue'}: P${priority}`}
                      onDelete={() => {
                        const newPrefs = { ...formData.preferred_venues };
                        delete newPrefs[roomId];
                        setFormData({ ...formData, preferred_venues: newPrefs });
                      }}
                      color="primary"
                      variant="outlined"
                      size="small"
                    />
                  );
                })}
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseDialog}>Cancel</Button>
            <Button onClick={() => { void handleSubmit(); }} variant="contained">
              {editingGroup ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </Dialog>

        <Dialog open={openUploadDialog} onClose={() => {
          setOpenUploadDialog(false);
          setSelectedFile(null);
          setUploadResult(null);
          const input = document.getElementById('group-file-upload') as HTMLInputElement;
          if (input) input.value = '';
        }} maxWidth="sm" fullWidth>
          <DialogTitle>Bulk Upload Student Groups</DialogTitle>
          <DialogContent>
            <Box sx={{ mt: 2 }}>
              <Alert severity="info" sx={{ mb: 3 }}>
                Upload a <strong>CSV or Excel</strong> file containing your student groups.
                <Box component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
                  <li>Accepted formats: .csv, .xlsx, .xls (max 5 MB)</li>
                  <li>Include group name, academic level, and number of students</li>
                  <li>Specify the department each group belongs to</li>
                  <li>Duplicate entries will be automatically skipped</li>
                </Box>
              </Alert>

              <input
                key={openUploadDialog ? 'open' : 'closed'}
                accept=".csv,.xlsx,.xls"
                style={{ display: 'none' }}
                id="group-file-upload"
                type="file"
                onChange={handleFileSelect}
              />
              <label htmlFor="group-file-upload">
                <Button
                  variant="outlined"
                  component="span"
                  fullWidth
                  sx={{ py: 1.5, textTransform: 'none' }}
                >
                  {selectedFile ? selectedFile.name : 'Select File'}
                </Button>
              </label>

              {loading && <LinearProgress sx={{ mt: 2 }} />}

              {uploadResult && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  Successfully created {uploadResult.created} groups.
                  {uploadResult.skipped > 0 && ` Skipped ${uploadResult.skipped} duplicates.`}
                </Alert>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => { 
              setOpenUploadDialog(false);
              setSelectedFile(null);
              setUploadResult(null);
              const input = document.getElementById('group-file-upload') as HTMLInputElement;
              if (input) input.value = '';
            }}>Cancel</Button>
            <Button
              onClick={() => { void handleBulkUpload(); }}
              variant="contained"
              disabled={!selectedFile || loading}
            >
              {loading ? 'Uploading...' : 'Upload'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Subdivide Group Dialog */}
        <Dialog open={openSubdivideDialog} onClose={() => { setOpenSubdivideDialog(false); }} maxWidth="sm" fullWidth>
          <DialogTitle>Create Elective Streams: {subdivideTarget ? formatGroupLabel(subdivideTarget) : ''}</DialogTitle>
          <DialogContent>
            <Box sx={{ mt: 2 }}>
              {/* Running total indicator */}
              {(() => {
                const total = subgroupSizes.reduce((a, b) => a + b, 0);
                const parentSize = subdivideTarget?.size || 0;
                const diff = total - parentSize;
                const color = diff === 0 ? 'success' : 'warning';
                return (
                  <Alert severity={color} sx={{ mb: 2 }}>
                    <strong>Total assigned: {total}</strong> / {parentSize} students
                    {diff !== 0 && <> &nbsp;({diff > 0 ? '+' : ''}{diff} from parent size — adjust below)</>}
                  </Alert>
                );
              })()}

              <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                <TextField
                  label="Number of Streams"
                  type="number"
                  value={subdivideForm.count}
                  onChange={(e: any) => { handleSubdivideCountChange(parseInt(e.target.value) || 2); }}
                  margin="normal"
                  inputProps={{ min: 2, max: 20 }}
                  sx={{ width: 180, flexShrink: 0 }}
                />
                <Alert severity="info" sx={{ mt: 2, flex: 1 }}>
                  New streams inherit the parent cohort's courses automatically.
                </Alert>
              </Box>

              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>Set size per stream:</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                  {subgroupSizes.map((sz, idx) => (
                    <TextField
                      key={idx}
                      label={`Stream ${idx + 1}`}
                      type="number"
                      value={sz}
                      onChange={(e: any) => handleSubgroupSizeChange(idx, parseInt(e.target.value) || 0)}
                      inputProps={{ min: 1, max: subdivideTarget?.size || 500 }}
                      size="small"
                      sx={{ width: 110 }}
                    />
                  ))}
                </Box>
              </Box>
              <Alert severity="info" sx={{ mt: 2, fontSize: '0.8rem' }}>
                Keep a course on multiple sibling streams to make it common/shared. Remove it from a stream to make it elective and separate.
              </Alert>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => { setOpenSubdivideDialog(false); }}>Cancel</Button>
            <Button
              onClick={() => { void handleSubdivideSubmit(); }}
              variant="contained"
              color="secondary"
              disabled={loading || subdivideForm.count < 2}
            >
              {loading ? 'Creating...' : 'Create Streams'}
            </Button>
          </DialogActions>
        </Dialog>

        {courseManagerTarget && (
          <GroupCourseManager
            open={openCourseManager}
            onClose={() => {
              setOpenCourseManager(false);
              setCourseManagerTarget(null);
            }}
            groupId={courseManagerTarget.id}
            groupName={formatGroupLabel(courseManagerTarget)}
            groupCode={courseManagerTarget.display_code}
            groupType={courseManagerTarget.group_type}
            parentGroupName={(() => {
              const parent = groups.find(g => g.id === courseManagerTarget.parent_group_id);
              return parent ? formatGroupLabel(parent) : undefined;
            })()}
            groupLevel={courseManagerTarget.level}
            groupDepartmentId={courseManagerTarget.department_id}
          />
        )}
      </Box>
    </Fade>
  );
};

export default GroupsPage;
