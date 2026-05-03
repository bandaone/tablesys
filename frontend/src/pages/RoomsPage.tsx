import React, { useEffect, useState, useMemo } from 'react';
import {
  Box, Button, Typography, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Dialog, DialogTitle,
  DialogContent, DialogActions, TextField, IconButton, Alert,
  Chip, MenuItem, Switch, FormControlLabel, Slider, Tooltip,
  Divider, Grid, Fade, LinearProgress, InputAdornment,
  Stack,
} from '@mui/material';
import {
  Upload as UploadIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  CheckCircle as CheckIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
  People as PeopleIcon,
  MeetingRoom as RoomIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { roomsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import TableSkeleton from '../components/skeletons/TableSkeleton';
import { formatRoomName } from '../utils/displayFormatters';

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface Room {
  id: number;
  name: string;
  building: string;
  capacity: number;
  room_type: string;
  has_whiteboard: boolean;
  has_chalkboard: boolean;
  has_projector: boolean;
  priority_level: number;
  is_blocked: boolean;
  availability: string | null;
  availability_blocks?: Array<{ day: string; start_time: string; end_time: string }>;
  department_id: number | null;
  coordinator_managed_affinities?: Record<string, number>;
}

interface AvailabilityBlock {
  day: string;
  start_time: string;
  end_time: string;
}

interface FormState {
  name: string;
  building: string;
  capacity: number;
  room_type: string;
  has_whiteboard: boolean;
  has_chalkboard: boolean;
  has_projector: boolean;
  priority_level: number;
  is_blocked: boolean;
  availability_blocks: AvailabilityBlock[];
  manual_affinities: Record<string, number>;
}

// --------------------------------------------------------------------------
// Constants
// --------------------------------------------------------------------------

const ROOM_TYPES = [
  { value: 'lecture_hall', label: 'Lecture Hall' },
  { value: 'tutorial_room', label: 'Tutorial Room' },
  { value: 'seminar_room', label: 'Seminar Room' },
  { value: 'lab', label: 'Laboratory' },
  { value: 'drawing_room', label: 'Drawing Room' },
  { value: 'surveying_room', label: 'Surveying Room' },
  { value: 'auditorium', label: 'Auditorium' },
];

const TYPE_COLORS: Record<string, string> = {
  lecture_hall: '#1565c0',
  tutorial_room: '#6a1b9a',
  seminar_room: '#2e7d32',
  lab: '#bf360c',
  drawing_room: '#f57f17',
  surveying_room: '#00695c',
  auditorium: '#37474f',
};

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const EMPTY_BLOCK: AvailabilityBlock = {
  day: 'Monday',
  start_time: '07:00',
  end_time: '19:00',
};

const EMPTY_FORM: FormState = {
  name: '', building: '', capacity: 30, room_type: 'lecture_hall',
  has_whiteboard: true, has_chalkboard: false, has_projector: true,
  priority_level: 5, is_blocked: false, availability_blocks: [],
  manual_affinities: {},
};

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

const RoomsPage: React.FC = () => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const [openDialog, setOpenDialog] = useState(false);
  const [openBulkDialog, setOpenBulkDialog] = useState(false);
  const [editingRoom, setEditingRoom] = useState<Room | null>(null);
  const [formData, setFormData] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [uploading, setUploading] = useState(false);
  const [clearing, setClearing] = useState(false);

  const { isCoordinator } = useAuth();

  // ── Data ─────────────────────────────────────────────────────────────────

  useEffect(() => { void fetchRooms(); }, []);

  const fetchRooms = async () => {
    setLoading(true);
    try {
      const data = await roomsAPI.getAll();
      setRooms(data);
    } catch {
      setError('Failed to load venues');
    } finally {
      setLoading(false);
    }
  };

  // ── Stats ─────────────────────────────────────────────────────────────────

  const stats = useMemo(() => ({
    total: rooms.length,
    capacity: rooms.reduce((s, r) => s + r.capacity, 0),
    blocked: rooms.filter(r => r.is_blocked).length,
    available: rooms.filter(r => !r.is_blocked).length,
  }), [rooms]);

  // ── Filtered rooms ────────────────────────────────────────────────────────

  const filtered = useMemo(() => rooms.filter(r => {
    if (search && !r.name.toLowerCase().includes(search.toLowerCase()) &&
      !r.building.toLowerCase().includes(search.toLowerCase())) return false;
    if (filterType && r.room_type !== filterType) return false;
    if (filterStatus === 'available' && r.is_blocked) return false;
    if (filterStatus === 'blocked' && !r.is_blocked) return false;
    return true;
  }), [rooms, search, filterType, filterStatus]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleOpenDialog = (room?: Room) => {
    if (room) {
      setEditingRoom(room);
      setFormData({
        name: room.name, building: room.building, capacity: room.capacity,
        room_type: room.room_type,
        has_whiteboard: room.has_whiteboard,
        has_chalkboard: room.has_chalkboard,
        has_projector: room.has_projector,
        priority_level: room.priority_level,
        is_blocked: room.is_blocked,
        availability_blocks: room.availability_blocks ?? [],
        manual_affinities: room.coordinator_managed_affinities ?? {},
      });
    } else {
      setEditingRoom(null);
      setFormData(EMPTY_FORM);
    }
    setOpenDialog(true);
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      const payload = {
        ...formData,
        availability: null,
        availability_blocks: formData.availability_blocks,
        coordinator_managed_affinities: formData.manual_affinities,
      };
      if (editingRoom) {
        await roomsAPI.update(editingRoom.id, payload);
      } else {
        await roomsAPI.create(payload);
      }
      await fetchRooms();
      setOpenDialog(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save venue');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this venue permanently?')) return;
    try {
      await roomsAPI.delete(id);
      await fetchRooms();
    } catch {
      setError('Failed to delete venue');
    }
  };

  const handleToggleBlock = async (room: Room) => {
    try {
      await roomsAPI.toggleBlock(room.id);
      await fetchRooms();
    } catch {
      setError('Failed to toggle block status');
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm(`This will permanently delete ALL ${stats.total} venues. This cannot be undone.\n\nType OK to confirm.`)) return;
    setClearing(true);
    setError('');
    try {
      const result = await roomsAPI.deleteAll();
      await fetchRooms();
      alert(`Done — ${result.deleted} venue${result.deleted !== 1 ? 's' : ''} deleted.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to clear venues');
    } finally {
      setClearing(false);
    }
  };

  const handleBulkUpload = async () => {
    if (!selectedFile) { setError('Please select a file'); return; }
    setUploading(true);
    setError('');
    setUploadResult(null);
    try {
      const result = await roomsAPI.bulkUpload(selectedFile);
      setUploadResult(result);
      void fetchRooms();
      setTimeout(() => { setOpenBulkDialog(false); setSelectedFile(null); setUploadResult(null); }, 3500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────────────

  const priorityColor = (lvl: number) =>
    lvl >= 8 ? 'error' : lvl >= 5 ? 'warning' : 'default';

  const form = (key: keyof FormState, val: any) =>
    setFormData(f => ({ ...f, [key]: val }));

  const updateAvailabilityBlock = (
    idx: number,
    key: keyof AvailabilityBlock,
    value: string,
  ) => {
    const nextBlocks = [...formData.availability_blocks];
    nextBlocks[idx] = { ...nextBlocks[idx], [key]: value };
    form('availability_blocks', nextBlocks);
  };

  const addAvailabilityBlock = () => {
    form('availability_blocks', [...formData.availability_blocks, { ...EMPTY_BLOCK }]);
  };

  const removeAvailabilityBlock = (idx: number) => {
    const nextBlocks = formData.availability_blocks.filter((_, i) => i !== idx);
    form('availability_blocks', nextBlocks);
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <Fade in timeout={500}>
      <Box>

        {/* ── Page header ── */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
          <Box>
            <Typography variant="h4" fontWeight={700}>Venues & Resources</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Manage all teaching spaces — type, capacity, equipment, and scheduling priority.
            </Typography>
          </Box>
          {isCoordinator && (
            <Stack direction="row" spacing={1.5}>
              <Button
                variant="outlined"
                color="error"
                disabled={clearing || stats.total === 0}
                onClick={() => void handleClearAll()}
                sx={{ borderColor: 'error.main', '&:hover': { bgcolor: 'error.50' } }}
              >
                {clearing ? 'Clearing…' : 'Clear All'}
              </Button>
              <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => setOpenBulkDialog(true)}>
                Bulk Upload
              </Button>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => handleOpenDialog()}
                sx={{ background: 'linear-gradient(135deg,#006837,#004826)', '&:hover': { boxShadow: 4 } }}
              >
                Add Venue
              </Button>
            </Stack>
          )}
        </Box>

        {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

        {/* ── Stats bar ── */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {[
            { label: 'Total Venues', value: stats.total, icon: <RoomIcon />, color: '#1565c0' },
            { label: 'Total Seats', value: stats.capacity, icon: <PeopleIcon />, color: '#2e7d32' },
            { label: 'Available', value: stats.available, icon: <CheckIcon />, color: '#43a047' },
            { label: 'Blocked', value: stats.blocked, icon: <WarningIcon />, color: '#e53935' },
          ].map(s => (
            <Grid item xs={6} sm={3} key={s.label}>
              <Paper elevation={2} sx={{ p: 2, borderRadius: 3, borderLeft: `4px solid ${s.color}` }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Box sx={{ color: s.color }}>{s.icon}</Box>
                  <Box>
                    <Typography variant="h5" fontWeight={700}>{s.value}</Typography>
                    <Typography variant="caption" color="text.secondary">{s.label}</Typography>
                  </Box>
                </Stack>
              </Paper>
            </Grid>
          ))}
        </Grid>

        {/* ── Filters ── */}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
          <TextField
            size="small"
            placeholder="Search by name or building"
            value={search}
            onChange={e => setSearch(e.target.value)}
            sx={{ minWidth: 240 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <TextField select size="small" value={filterType} onChange={e => setFilterType(e.target.value)}
            sx={{ minWidth: 170 }} label="Type"
            InputProps={{ startAdornment: <InputAdornment position="start"><FilterIcon fontSize="small" /></InputAdornment> }}
          >
            <MenuItem value="">All Types</MenuItem>
            {ROOM_TYPES.map(t => <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>)}
          </TextField>
          <TextField select size="small" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
            sx={{ minWidth: 150 }} label="Status"
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="available">Available</MenuItem>
            <MenuItem value="blocked">Blocked</MenuItem>
          </TextField>
          {(search || filterType || filterStatus) && (
            <Button size="small" onClick={() => { setSearch(''); setFilterType(''); setFilterStatus(''); }}>
              Clear
            </Button>
          )}
        </Stack>

        {/* ── Table ── */}
        {loading ? (
          <TableSkeleton columns={isCoordinator ? 9 : 7} rows={8} />
        ) : (
          <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 3, border: '1px solid rgba(0,0,0,0.06)', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}>
            <Table size="small" sx={{ '& .MuiTableCell-root': { borderBottom: '1px solid rgba(0,0,0,0.05)' }}}>
              <TableHead sx={{ bgcolor: '#f8fafc' }}>
                <TableRow>
                  <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Venue</TableCell>
                  <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Building</TableCell>
                  <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Type</TableCell>
                  <TableCell align="center" sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Seats</TableCell>
                  <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Equipment</TableCell>
                  <TableCell align="center" sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Priority</TableCell>
                  <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Availability</TableCell>
                  {isCoordinator && <TableCell align="center" sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Block</TableCell>}
                  {isCoordinator && <TableCell align="center" sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.map(room => (
                <TableRow
                  key={room.id}
                  hover
                  sx={{ opacity: room.is_blocked ? 0.55 : 1, transition: 'opacity 0.2s' }}
                >
                  {/* Name */}
                  <TableCell>
                    <Typography fontWeight={600} variant="body2">{formatRoomName(room.name)}</Typography>
                  </TableCell>

                  {/* Building */}
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {room.building}
                    </Typography>
                  </TableCell>

                  {/* Type */}
                  <TableCell>
                    <Chip
                      label={ROOM_TYPES.find(t => t.value === room.room_type)?.label ?? room.room_type}
                      size="small"
                      sx={{
                        bgcolor: TYPE_COLORS[room.room_type] + '20',
                        color: TYPE_COLORS[room.room_type],
                        fontWeight: 600, fontSize: 11,
                      }}
                    />
                  </TableCell>

                  {/* Seats */}
                  <TableCell align="center">
                    <Typography variant="body2" fontWeight={600}>{room.capacity}</Typography>
                  </TableCell>

                  {/* Equipment — compact labelled chips */}
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <Chip
                        label="WB"
                        size="small"
                        variant={room.has_whiteboard ? 'filled' : 'outlined'}
                        sx={{
                          fontSize: 10,
                          fontWeight: 700,
                          height: 20,
                          bgcolor: room.has_whiteboard ? '#1565c0' : 'transparent',
                          color: room.has_whiteboard ? '#fff' : '#ccc',
                          borderColor: room.has_whiteboard ? '#1565c0' : '#e0e0e0',
                        }}
                      />
                      <Chip
                        label="CB"
                        size="small"
                        variant={room.has_chalkboard ? 'filled' : 'outlined'}
                        sx={{
                          fontSize: 10,
                          fontWeight: 700,
                          height: 20,
                          bgcolor: room.has_chalkboard ? '#4e342e' : 'transparent',
                          color: room.has_chalkboard ? '#fff' : '#ccc',
                          borderColor: room.has_chalkboard ? '#4e342e' : '#e0e0e0',
                        }}
                      />
                      <Chip
                        label="PROJ"
                        size="small"
                        variant={room.has_projector ? 'filled' : 'outlined'}
                        sx={{
                          fontSize: 10,
                          fontWeight: 700,
                          height: 20,
                          bgcolor: room.has_projector ? '#e65100' : 'transparent',
                          color: room.has_projector ? '#fff' : '#ccc',
                          borderColor: room.has_projector ? '#e65100' : '#e0e0e0',
                        }}
                      />
                    </Stack>
                  </TableCell>

                  {/* Priority */}
                  <TableCell align="center">
                    <Chip
                      label={room.priority_level}
                      color={priorityColor(room.priority_level) as any}
                      size="small"
                      variant="outlined"
                      sx={{ fontWeight: 700, minWidth: 36 }}
                    />
                  </TableCell>

                  {/* Availability */}
                  <TableCell>
                    {(room.availability_blocks && room.availability_blocks.length > 0) ? (
                      <Stack spacing={0.25}>
                        <Typography variant="caption" color="text.primary">
                          {room.availability_blocks.length} block{room.availability_blocks.length > 1 ? 's' : ''}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {`${room.availability_blocks[0].day} ${room.availability_blocks[0].start_time}-${room.availability_blocks[0].end_time}`}
                        </Typography>
                      </Stack>
                    ) : (
                      <Typography variant="caption" color="text.disabled">
                        Unrestricted
                      </Typography>
                    )}
                  </TableCell>

                  {/* Quick Block Toggle */}
                  {isCoordinator && (
                    <TableCell align="center">
                      <Tooltip title={room.is_blocked ? 'Unblock venue' : 'Block venue'}>
                        <Switch
                          size="small"
                          checked={room.is_blocked}
                          onChange={() => void handleToggleBlock(room)}
                          color="error"
                          inputProps={{ 'aria-label': room.is_blocked ? 'Unblock' : 'Block' }}
                        />
                      </Tooltip>
                    </TableCell>
                  )}

                  {/* Actions */}
                  {isCoordinator && (
                    <TableCell align="center">
                      <Stack direction="row" spacing={0} justifyContent="center">
                        <Tooltip title="Edit">
                          <IconButton size="small" color="primary" onClick={() => handleOpenDialog(room)}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton size="small" color="error" onClick={() => void handleDelete(room.id)}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </TableCell>
                  )}
                </TableRow>
              ))}

              {filtered.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={9} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                    {rooms.length === 0 ? 'No venues added yet. Add one or bulk upload.' : 'No venues match your filters.'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>        )}
        {/* ── Add / Edit Dialog ── */}
        <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <RoomIcon color="primary" />
            {editingRoom ? `Edit — ${editingRoom.name}` : 'Add New Venue'}
          </DialogTitle>
          <DialogContent dividers>
            <Box sx={{ py: 1 }}>

              {/* Basic info */}
              <Typography variant="subtitle2" color="primary" gutterBottom>Basic Information</Typography>
              <TextField fullWidth label="Venue Name *" value={formData.name}
                onChange={e => form('name', e.target.value)} margin="dense" />
              <TextField fullWidth label="Building *" value={formData.building}
                onChange={e => form('building', e.target.value)} margin="dense" />
              <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
                <TextField select fullWidth label="Room Type *" value={formData.room_type}
                  onChange={e => form('room_type', e.target.value)}>
                  {ROOM_TYPES.map(t => <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>)}
                </TextField>
                <TextField fullWidth label="Capacity *" type="number" value={formData.capacity}
                  onChange={e => form('capacity', parseInt(e.target.value) || 1)} />
              </Box>

              <Divider sx={{ my: 3 }} />

              {/* Equipment */}
              <Typography variant="subtitle2" color="primary" gutterBottom>Teaching Equipment</Typography>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
                Select what is physically available in this room.
              </Typography>
              <Stack direction="row" spacing={2}>
                <FormControlLabel
                  control={<Switch checked={formData.has_whiteboard} onChange={e => form('has_whiteboard', e.target.checked)} />}
                  label="Whiteboard"
                />
                <FormControlLabel
                  control={<Switch checked={formData.has_chalkboard} onChange={e => form('has_chalkboard', e.target.checked)} />}
                  label="Chalkboard"
                />
                <FormControlLabel
                  control={<Switch checked={formData.has_projector} onChange={e => form('has_projector', e.target.checked)} />}
                  label="Projector"
                />
              </Stack>

              <Divider sx={{ my: 3 }} />

              {/* Scheduling controls */}
              <Typography variant="subtitle2" color="primary" gutterBottom>Scheduling Controls</Typography>

              <Box sx={{ px: 1, mb: 2 }}>
                <Typography variant="caption" display="block" gutterBottom>
                  Priority Level (1 = low, 10 = always preferred)
                </Typography>
                <Slider
                  value={formData.priority_level} min={1} max={10} step={1}
                  marks valueLabelDisplay="auto"
                  onChange={(_, v) => form('priority_level', v as number)}
                  sx={{ color: formData.priority_level >= 8 ? 'error.main' : formData.priority_level >= 5 ? 'warning.main' : 'success.main' }}
                />
              </Box>

              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                  Define zero or more availability blocks. No blocks means unrestricted scheduling.
                </Typography>

                {formData.availability_blocks.map((block, idx) => (
                  <Stack key={`${block.day}-${idx}`} direction="row" spacing={1} sx={{ mb: 1 }} alignItems="center">
                    <TextField
                      select
                      size="small"
                      label="Day"
                      value={block.day}
                      onChange={e => updateAvailabilityBlock(idx, 'day', e.target.value)}
                      sx={{ minWidth: 140 }}
                    >
                      {DAYS.map(day => (
                        <MenuItem key={day} value={day}>{day}</MenuItem>
                      ))}
                    </TextField>
                    <TextField
                      size="small"
                      label="Start"
                      type="time"
                      value={block.start_time}
                      onChange={e => updateAvailabilityBlock(idx, 'start_time', e.target.value)}
                      InputLabelProps={{ shrink: true }}
                    />
                    <TextField
                      size="small"
                      label="End"
                      type="time"
                      value={block.end_time}
                      onChange={e => updateAvailabilityBlock(idx, 'end_time', e.target.value)}
                      InputLabelProps={{ shrink: true }}
                    />
                    <Tooltip title="Remove availability block">
                      <IconButton color="error" onClick={() => removeAvailabilityBlock(idx)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                ))}

                <Button size="small" startIcon={<AddIcon />} onClick={addAvailabilityBlock}>
                  Add Availability Block
                </Button>
              </Box>

              <Divider sx={{ my: 3 }} />

              {/* Coordinator affinities */}
              <Typography variant="subtitle2" color="primary" gutterBottom>Level Affinities (0 – 1)</Typography>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                Higher values make this venue preferred for that year level.
              </Typography>
              <Grid container spacing={1}>
                {[1, 2, 3, 4, 5, 6, 7].map(lvl => (
                  <Grid item xs={6} sm={3} key={lvl}>
                    <TextField
                      label={`Level ${lvl}`} size="small" type="number"
                      value={formData.manual_affinities[`level_${lvl}`] ?? 0}
                      onChange={e => {
                        const val = Math.min(1, Math.max(0, parseFloat(e.target.value) || 0));
                        form('manual_affinities', { ...formData.manual_affinities, [`level_${lvl}`]: val });
                      }}
                      inputProps={{ step: 0.1, min: 0, max: 1 }}
                    />
                  </Grid>
                ))}
              </Grid>

              <Divider sx={{ my: 3 }} />

              <FormControlLabel
                control={<Switch checked={formData.is_blocked} color="error"
                  onChange={e => form('is_blocked', e.target.checked)} />}
                label={<Typography variant="body2" color={formData.is_blocked ? 'error' : 'inherit'}>
                  {formData.is_blocked ? 'Venue is blocked - excluded from scheduling' : 'Venue is active'}
                </Typography>}
              />
            </Box>
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
            <Button onClick={() => void handleSubmit()} variant="contained" disabled={saving}>
              {saving ? 'Saving…' : editingRoom ? 'Update Venue' : 'Create Venue'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* ── Bulk Upload Dialog ── */}
        <Dialog open={openBulkDialog} onClose={() => setOpenBulkDialog(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Bulk Upload Venues</DialogTitle>
          <DialogContent>
            <Alert severity="info" sx={{ mb: 2 }}>
              Upload a <strong>CSV or Excel</strong> file containing your venues.
              <Box component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
                <li>Accepted formats: .csv, .xlsx, .xls (max 5 MB)</li>
                <li>Include venue name, building, and seating capacity</li>
                <li>Equipment details and availability are optional</li>
                <li>Existing venues will be updated; new ones will be created</li>
              </Box>
            </Alert>
            <input
              key={openBulkDialog ? 'open' : 'closed'}
              accept=".csv,.xlsx,.xls" type="file" id="room-bulk-input" style={{ display: 'none' }}
              onChange={e => setSelectedFile(e.target.files?.[0] ?? null)}
            />
            <label htmlFor="room-bulk-input">
              <Button variant="outlined" component="span" fullWidth sx={{ py: 1.5 }}>
                {selectedFile ? selectedFile.name : 'Choose File (CSV / Excel)'}
              </Button>
            </label>
            {uploading && <LinearProgress sx={{ mt: 2 }} />}
            {uploadResult && (
              <Alert severity="success" sx={{ mt: 2 }}>
                 Created <strong>{uploadResult.created}</strong>, updated <strong>{uploadResult.updated}</strong>,
                skipped <strong>{uploadResult.skipped}</strong>
                {uploadResult.errors?.length > 0 && (
                  <Box mt={1}>
                    <Typography variant="caption" color="error">
                      Errors: {uploadResult.errors.join(' | ')}
                    </Typography>
                  </Box>
                )}
              </Alert>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => { setOpenBulkDialog(false); setSelectedFile(null); setUploadResult(null); }}>
              {uploadResult ? 'Done' : 'Cancel'}
            </Button>
            <Button variant="contained" onClick={() => void handleBulkUpload()}
              disabled={!selectedFile || uploading}>
              {uploading ? 'Uploading…' : 'Upload'}
            </Button>
          </DialogActions>
        </Dialog>

      </Box>
    </Fade>
  );
};

export default RoomsPage;
