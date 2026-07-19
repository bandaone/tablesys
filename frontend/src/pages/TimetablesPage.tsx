import React, { useState, useEffect, useRef } from 'react';
import {
  Box, Button, Paper, Typography, Dialog, DialogTitle, DialogContent,
  DialogActions, TextField, Alert, Card, CardContent,
  Grid, Chip, InputLabel, Select, MenuItem, FormGroup, FormControlLabel,
  Checkbox, FormControl, IconButton, Tooltip, Fade, Zoom, Stack,
  Divider, CircularProgress, Switch,
} from '@mui/material';
import {
  Add as AddIcon,
  PlayArrow as PlayIcon,
  Refresh as ReGenerateIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
  Description as DocxIcon,
  History as HistoryIcon,
  Schedule as ScheduleIcon,
  Visibility as ViewIcon,
  ToggleOn as ActivateIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { timetablesAPI, coursesAPI, lecturersAPI, roomsAPI, groupsAPI, schoolsAPI, School as SchoolRecord } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';
import { useNavigate, Navigate } from 'react-router-dom';
import VersionHistory from '../components/VersionHistory';
import api from '../api';

interface GenerationProgress {
  level: number;
  status: string;
  percentage: number;
  message: string;
}

interface GridConfig {
  start_time: string;
  end_time: string;
  lunch_start: string;
  lunch_end: string;
  active_days: string[];
}

interface Timetable {
  id: number;
  name: string;
  semester: string;
  year: number;
  academic_half: string;
  grid_config?: GridConfig;
  is_active: boolean;
  is_generated?: boolean;
  generation_metadata?: {
    generated?: boolean;
    generated_at?: string;
    grid_config?: Partial<GridConfig>;
  };
  min_score?: number;
  max_score?: number;
  avg_score?: number;
  school_id?: number | null;
}

// ── helpers ──────────────────────────────────────────────────────────────────
const isGenerated = (tt: Timetable) =>
  tt.is_generated || tt.generation_metadata?.generated;

const getToken = () =>
  localStorage.getItem('token') || sessionStorage.getItem('token') || '';

const exportUrl = (id: number, format: 'pdf' | 'excel' | 'docx') =>
  `/api/v1/export/timetable/${id}/${format}?token=${getToken()}`;

const ACTIVE_DAY_OPTIONS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const DEFAULT_GRID_CONFIG: GridConfig = {
  start_time: '07:00',
  end_time: '17:00',
  lunch_start: '13:00',
  lunch_end: '14:00',
  active_days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
};

const resolveGridConfig = (tt: Timetable | null): GridConfig => {
  const modelGrid: Partial<GridConfig> = tt?.grid_config ?? {};
  const metadataGrid: Partial<GridConfig> = tt?.generation_metadata?.grid_config ?? {};
  const activeDays = Array.isArray(modelGrid.active_days)
    ? modelGrid.active_days
    : Array.isArray(metadataGrid.active_days)
      ? metadataGrid.active_days
      : DEFAULT_GRID_CONFIG.active_days;

  return {
    start_time: modelGrid.start_time || metadataGrid.start_time || DEFAULT_GRID_CONFIG.start_time,
    end_time: modelGrid.end_time || metadataGrid.end_time || DEFAULT_GRID_CONFIG.end_time,
    lunch_start: modelGrid.lunch_start || metadataGrid.lunch_start || DEFAULT_GRID_CONFIG.lunch_start,
    lunch_end: modelGrid.lunch_end || metadataGrid.lunch_end || DEFAULT_GRID_CONFIG.lunch_end,
    active_days: activeDays,
  };
};

// ─────────────────────────────────────────────────────────────────────────────

const TimetablesPage: React.FC = () => {
  const [timetables, setTimetables] = useState<Timetable[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [stats, setStats] = useState({ courses: 0, lecturers: 0, rooms: 0, groups: 0 });
  const [schools, setSchools] = useState<SchoolRecord[]>([]);

  // Create dialog
  const [openCreate, setOpenCreate] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    semester: 'Semester 1',
    year: new Date().getFullYear(),
    academic_half: 'first_half',
    school_id: undefined as number | undefined,
    grid_config: {
      start_time: DEFAULT_GRID_CONFIG.start_time,
      end_time: DEFAULT_GRID_CONFIG.end_time,
      lunch_start: DEFAULT_GRID_CONFIG.lunch_start,
      lunch_end: DEFAULT_GRID_CONFIG.lunch_end,
      active_days: [...DEFAULT_GRID_CONFIG.active_days],
    },
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  // Generate dialog
  const [openGenerate, setOpenGenerate] = useState(false);
  const [selectedTimetable, setSelectedTimetable] = useState<Timetable | null>(null);
  const [generationProgress, setGenerationProgress] = useState<GenerationProgress | null>(null);
  const [generationComplete, setGenerationComplete] = useState(false);
  const [generationError, setGenerationError] = useState('');
  const [generationWindow, setGenerationWindow] = useState({
    start_time: DEFAULT_GRID_CONFIG.start_time,
    end_time: DEFAULT_GRID_CONFIG.end_time,
    lunch_start: DEFAULT_GRID_CONFIG.lunch_start,
    lunch_end: DEFAULT_GRID_CONFIG.lunch_end,
  });
  const [runInBackground, setRunInBackground] = useState(true);
  const [schedulingProfile, setSchedulingProfile] = useState('balanced');
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Version history dialog
  const [versionOpen, setVersionOpen] = useState(false);
  const [versionTimetable, setVersionTimetable] = useState<Timetable | null>(null);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<Timetable | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { isCoordinator, isTenantAdmin, user } = useAuth();
  const { branding } = useBranding();
  const navigate = useNavigate();

  useEffect(() => {
    void fetchStats();
    void fetchTimetables();
    void fetchSchools();
  }, []);

  const fetchSchools = async () => {
    try {
      const data = await schoolsAPI.getAll();
      setSchools(data);
      if (!isTenantAdmin && user?.school_id) {
        setFormData((prev) => ({ ...prev, school_id: user.school_id || undefined }));
      }
    } catch {}
  };

  const fetchStats = async () => {
    try {
      const [c, l, r, g] = await Promise.all([
        coursesAPI.getAll(),
        lecturersAPI.getAll(),
        roomsAPI.getAll(),
        groupsAPI.getAll(),
      ]);
      setStats({ courses: c.length, lecturers: l.length, rooms: r.length, groups: g.length });
    } catch {}
  };

  const fetchTimetables = async () => {
    setLoadingList(true);
    try {
      const data = await timetablesAPI.getAll();
      setTimetables(data);
    } catch {
      console.error('Failed to load timetables');
    } finally {
      setLoadingList(false);
    }
  };

  if (!isCoordinator) {
    return <Navigate to="/dashboard" replace />;
  }

  // ── Create ────────────────────────────────────────────────────────────────
  const handleCreate = async () => {
    if (!formData.name.trim() || !formData.semester.trim()) {
      setCreateError('Name and Semester are required.');
      return;
    }
    if (!formData.school_id) {
      setCreateError('Select the school that owns this timetable.');
      return;
    }
    if (formData.grid_config.start_time >= formData.grid_config.end_time) {
      setCreateError('Grid start time must be earlier than end time.');
      return;
    }
    if (formData.grid_config.lunch_start >= formData.grid_config.lunch_end) {
      setCreateError('Lunch start must be earlier than lunch end.');
      return;
    }
    setCreating(true);
    setCreateError('');
    try {
      const tt = await timetablesAPI.create(formData);
      setOpenCreate(false);
      await fetchTimetables();
      // Open generate dialog immediately
      openGenerateFor(tt);
    } catch (e: any) {
      setCreateError(e.response?.data?.detail || 'Failed to create timetable.');
    } finally {
      setCreating(false);
    }
  };

  // ── Activate ──────────────────────────────────────────────────────────────
  const handleActivate = async (tt: Timetable) => {
    try {
      await api.post(`/timetables/${tt.id}/activate`);
      await fetchTimetables();
    } catch (e: any) {
      console.error('Activate failed', e);
    }
  };

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await timetablesAPI.delete(deleteTarget.id);
      setDeleteTarget(null);
      await fetchTimetables();
    } catch (e: any) {
      console.error('Delete failed', e);
    } finally {
      setDeleting(false);
    }
  };

  // ── Generate ──────────────────────────────────────────────────────────────
  const resetGenState = () => {
    setGenerationProgress(null);
    setGenerationComplete(false);
    setGenerationError('');
    setCurrentJobId(null);
    if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current as any);
        pollIntervalRef.current = null;
    }
  };

  const openGenerateFor = (tt: Timetable) => {
    const grid = resolveGridConfig(tt);
    setSelectedTimetable(tt);
    setGenerationWindow({
      start_time: grid.start_time,
      end_time: grid.end_time,
      lunch_start: grid.lunch_start,
      lunch_end: grid.lunch_end,
    });
    setSchedulingProfile('balanced');
    resetGenState();
    setOpenGenerate(true);
  };

  const handleGenerateWs = () => {
    if (!selectedTimetable) return;
    resetGenState();

    const selectedComponents = 'lecture';

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = getToken();
    const params = new URLSearchParams({
      components: selectedComponents,
      start_time: generationWindow.start_time,
      end_time: generationWindow.end_time,
      lunch_start: generationWindow.lunch_start,
      lunch_end: generationWindow.lunch_end,
      profile: schedulingProfile,
      token,
    });
    const wsUrl = `${protocol}//${window.location.host}/api/v1/timetables/generate/${selectedTimetable.id}?${params.toString()}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string);

        if (data.level) {
          setGenerationProgress(data);
        }

        if (data.status === 'success') {
          setGenerationComplete(true);
          ws.close();
          setTimeout(() => {
            setOpenGenerate(false);
            void fetchTimetables();
          }, 2000);
        } else if (data.status === 'error') {
          setGenerationError(data.message || 'Generation failed.');
          ws.close();
        }
      } catch {
        // non-JSON frame — ignore
      }
    };

    ws.onerror = () => {
      setGenerationError(
        'Connection to the server was lost. Please check your network and try again.'
      );
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  };

  const handleGenerateAsync = async () => {
    if (!selectedTimetable) return;
    resetGenState();

    const selectedComponents = 'lecture';

    try {
      setGenerationProgress({ level: 0, status: 'started', percentage: 0, message: 'Starting generation...' });
      const response = await api.post(
        `/scheduler/generate/${selectedTimetable.id}`,
        null,
        {
          params: {
            components: selectedComponents,
            start_time: generationWindow.start_time,
            end_time: generationWindow.end_time,
            lunch_start: generationWindow.lunch_start,
            lunch_end: generationWindow.lunch_end,
            profile: schedulingProfile,
          },
        }
      );
      const jobId = response.data.job_id;
      setCurrentJobId(jobId);

      // Start HTTP polling
      pollIntervalRef.current = setInterval(async () => {
        try {
          const statusRes = await api.get(`/scheduler/status/${jobId}`);
          const { state, progress, result } = statusRes.data;

          if (progress && progress.length > 0) {
            const latest = progress[progress.length - 1];
            setGenerationProgress(latest);
          }

          if (state === 'SUCCESS') {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current as any);
              pollIntervalRef.current = null;
            }

            if (result?.status === 'success') {
              setGenerationComplete(true);
              setGenerationProgress((prev) => (
                prev ?? { level: 0, status: 'success', percentage: 100, message: 'Timetable generated successfully.' }
              ));
              setTimeout(() => {
                setOpenGenerate(false);
                void fetchTimetables();
              }, 2000);
            } else if (result?.status === 'degraded') {
              setGenerationComplete(true);
              setGenerationProgress((prev) => (
                prev ?? { level: 0, status: 'warning', percentage: 100, message: 'Timetable generated with some unplaced sessions.' }
              ));
              setTimeout(() => {
                setOpenGenerate(false);
                void fetchTimetables();
              }, 4000);
            } else {
              const savedSlotCount = typeof result?.saved_slot_count === 'number'
                ? result.saved_slot_count
                : null;
              const suffix = savedSlotCount !== null ? ` Saved slots: ${savedSlotCount}.` : '';
              setGenerationError(
                (result?.message || 'Generation finished without producing a timetable.') + suffix
              );
            }
          } else if (state === 'FAILURE' || state === 'REVOKED') {
            setGenerationError('Background task failed or was cancelled.');
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current as any);
              pollIntervalRef.current = null;
            }
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 1500) as any;
    } catch (e: any) {
      setGenerationError(e.response?.data?.detail || 'Failed to start background task.');
    }
  };

  const validateGenerationWindow = () => {
    if (!generationWindow.start_time || !generationWindow.end_time) {
      setGenerationError('Please select both start and end time for generation.');
      return false;
    }

    if (!generationWindow.lunch_start || !generationWindow.lunch_end) {
      setGenerationError('Please select both lunch start and lunch end.');
      return false;
    }

    if (generationWindow.start_time >= generationWindow.end_time) {
      setGenerationError('Start time must be earlier than end time.');
      return false;
    }

    if (generationWindow.lunch_start >= generationWindow.lunch_end) {
      setGenerationError('Lunch start must be earlier than lunch end.');
      return false;
    }

    return true;
  };

  const handleGenerate = () => {
    setGenerationError('');
    if (!validateGenerationWindow()) {
      return;
    }

    if (runInBackground) {
      void handleGenerateAsync();
    } else {
      handleGenerateWs();
    }
  };

  const handleCancelGenerate = async () => {
    wsRef.current?.close();
    if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current as any);
        pollIntervalRef.current = null;
    }
    if (currentJobId) {
        try {
            await api.delete(`/scheduler/cancel/${currentJobId}`);
        } catch (e) {
            console.error(e);
        }
    }
    setOpenGenerate(false);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <Fade in timeout={500}>
      <Box>
        {/* ══ HERO — bold tenant-gradient ══ */}
        <Box
          sx={{
            position: 'relative',
            borderRadius: 4,
            overflow: 'hidden',
            background: `linear-gradient(135deg, ${branding.primary_color || '#1976d2'} 0%, #1976d2 55%, #9c27b0 100%)`,
            boxShadow: `0 12px 40px ${(branding.primary_color || '#1976d2')}55`,
            mb: 5,
            p: { xs: 3, md: 5 },
          }}
        >
          {/* Decorative orbs */}
          <Box sx={{ position: 'absolute', top: -60,  left: -60,   width: 260, height: 260, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />
          <Box sx={{ position: 'absolute', bottom: -80, right: 140, width: 220, height: 220, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.04)', pointerEvents: 'none' }} />
          <Box sx={{ position: 'absolute', top: 20,  right: '34%', width: 80,  height: 80,  borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />

          <Grid container spacing={4} sx={{ position: 'relative', zIndex: 1 }} alignItems="center">
            <Grid item xs={12} md={7}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                <ScheduleIcon sx={{ color: '#fff', fontSize: 32, opacity: 0.9 }} />
                <Typography variant="h4" fontWeight={900} sx={{ color: '#fff', lineHeight: 1.15 }}>
                  Timetables
                </Typography>
              </Box>
              <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.78)', mb: 3, maxWidth: 500, lineHeight: 1.7 }}>
                Prepare clear, reliable lecture timetables from your school’s approved academic data.
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                {[
                  { label: 'Courses', value: stats.courses },
                  { label: 'Lecturers', value: stats.lecturers },
                  { label: 'Rooms', value: stats.rooms },
                  { label: 'Groups', value: stats.groups },
                ].map(item => (
                  <Chip
                    key={item.label}
                    icon={item.value > 0 ? <CheckCircleIcon sx={{ color: '#fff !important', opacity: 0.9 }}/> : <CancelIcon sx={{ color: '#ffcdd2 !important' }} />}
                    label={`${item.label}: ${item.value}`}
                    sx={{ 
                      bgcolor: item.value > 0 ? 'rgba(255,255,255,0.15)' : 'rgba(244, 67, 54, 0.3)', 
                      color: '#fff',
                      fontWeight: 600,
                      backdropFilter: 'blur(10px)',
                      border: '1px solid',
                      borderColor: item.value > 0 ? 'rgba(255,255,255,0.3)' : 'rgba(244, 67, 54, 0.5)'
                    }}
                  />
                ))}
              </Box>
            </Grid>
            <Grid item xs={12} md={5} sx={{ display: 'flex', flexDirection: 'column', alignItems: { xs: 'flex-start', md: 'flex-end' }, gap: 2 }}>
              {(stats.courses > 0 && stats.lecturers > 0 && stats.rooms > 0 && stats.groups > 0) ? (
                <Chip 
                  label="Ready to Generate" 
                  color="success" 
                  icon={<CheckCircleIcon />}
                  sx={{ fontWeight: 'bold', bgcolor: 'rgba(76, 175, 80, 0.9)', color: '#fff', px: 1, py: 2.5 }} 
                />
              ) : (
                <Chip 
                  label="Missing Prerequisites" 
                  color="error" 
                  icon={<CancelIcon />}
                  sx={{ fontWeight: 'bold', bgcolor: 'rgba(244, 67, 54, 0.9)', color: '#fff', px: 1, py: 2.5 }} 
                />
              )}
              
               <Button 
                 variant="contained" 
                 size="large"
                 disabled={!(stats.courses > 0 && stats.lecturers > 0 && stats.rooms > 0 && stats.groups > 0)}
                 startIcon={<AddIcon />}
                 onClick={() => setOpenCreate(true)}
                 sx={{ 
                   bgcolor: '#fff', 
                   color: branding.primary_color || '#1976d2',
                   fontWeight: 'bold',
                   mt: 1,
                   px: 4, 
                   py: 1.5,
                   '&:hover': { bgcolor: 'rgba(255,255,255,0.9)' },
                   '&.Mui-disabled': {
                     bgcolor: 'rgba(255,255,255,0.3)',
                     color: 'rgba(255,255,255,0.5)'
                   }
                 }}
               >
                 Configure New Timetable
               </Button>
            </Grid>
          </Grid>
        </Box>

        {/* ── Timetable cards ───────────────────── */}
        {loadingList ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : timetables.length === 0 ? (
          <Paper
            sx={{
              textAlign: 'center', py: 10, borderRadius: 3,
              border: '2px dashed', borderColor: 'divider',
              background: 'transparent',
            }}
          >
            <ScheduleIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No timetables yet
            </Typography>
            <Typography variant="body2" color="text.disabled" sx={{ mb: 3 }}>
              Create your first timetable to prepare lecture schedules for your school.
            </Typography>
          </Paper>
        ) : (
          <Grid container spacing={3}>
            {timetables.map((tt, idx) => {
              const generated = isGenerated(tt);
              const grid = resolveGridConfig(tt);
              return (
                <Grid item xs={12} md={6} lg={4} key={tt.id}>
                  <Zoom in timeout={300 + idx * 80}>
                    <Card
                      sx={{
                        height: '100%', borderRadius: 3,
                        border: '1px solid',
                        borderColor: tt.is_active ? 'success.main' : 'divider',
                        boxShadow: tt.is_active ? '0 0 0 2px rgba(46,125,50,0.15)' : '0 2px 8px rgba(0,0,0,0.06)',
                        transition: 'all 0.25s ease',
                        '&:hover': { transform: 'translateY(-3px)', boxShadow: '0 8px 24px rgba(0,0,0,0.1)' },
                      }}
                    >
                      <CardContent sx={{ p: 2.5 }}>
                        {/* Title row */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                          <Typography variant="h6" fontWeight="bold" sx={{ lineHeight: 1.3 }}>
                            {tt.name}
                          </Typography>
                          <Stack direction="row" spacing={0.5}>
                            {tt.is_active && <Chip label="Active" color="success" size="small" />}
                            {generated
                              ? <Chip label="Generated" color="primary" size="small" variant="outlined" />
                              : <Chip label="Draft" size="small" variant="outlined" />}
                          </Stack>
                        </Box>

                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                          {tt.semester} · {tt.year} · {tt.academic_half?.replace('_', ' ')}
                        </Typography>

                        {(tt.grid_config || tt.generation_metadata?.grid_config) && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                            Grid: {grid.start_time}-{grid.end_time} · Lunch {grid.lunch_start}-{grid.lunch_end} · {grid.active_days.length} active day(s)
                          </Typography>
                        )}

                        <Divider sx={{ mb: 2 }} />

                        {/* Action buttons */}
                        <Stack spacing={1}>
                          {/* View timetable */}
                          {generated && (
                            <Button
                              size="small" variant="contained" fullWidth
                              startIcon={<ViewIcon />}
                              onClick={() => navigate(`/timetables/${tt.id}/view`)}
                              sx={{ background: `linear-gradient(135deg, ${(window as any).__PRIMARY_COLOR || '#1976d2'} 0%, #115293 100%)` }}
                            >
                              View Timetable
                            </Button>
                          )}

                          {/* Generate / Re-generate */}
                          {isCoordinator && (
                            <Button
                              size="small"
                              variant={generated ? 'outlined' : 'contained'}
                              fullWidth
                              startIcon={generated ? <ReGenerateIcon /> : <PlayIcon />}
                              onClick={() => openGenerateFor(tt)}
                              color={generated ? 'secondary' : 'primary'}
                            >
                              {generated ? 'Re-Generate' : 'Generate Timetable'}
                            </Button>
                          )}

                          {/* Activate */}
                          {/* Delete timetable */}
                          {isCoordinator && (
                            <Button
                              size="small" variant="outlined" fullWidth
                              startIcon={<DeleteIcon />}
                              onClick={() => setDeleteTarget(tt)}
                              color="error"
                            >
                              Delete Timetable
                            </Button>
                          )}

                          {isCoordinator && (
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={tt.is_active}
                                  onChange={() => !tt.is_active && handleActivate(tt)}
                                  color="success"
                                />
                              }
                              label={tt.is_active ? "Activated" : "Set as Active"}
                              sx={{
                                border: '1px solid',
                                borderColor: tt.is_active ? 'success.main' : 'divider',
                                borderRadius: 1,
                                m: 0,
                                py: 0.5,
                                justifyContent: 'center',
                                width: '100%',
                              }}
                            />
                          )}

                          {/* Exports */}
                          {generated && (
                            <Box>
                              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                                Export
                              </Typography>
                              <Stack direction="row" spacing={1}>
                                <Tooltip title="Download PDF">
                                  <IconButton size="small" color="error"
                                    onClick={() => window.open(exportUrl(tt.id, 'pdf'), '_blank')}>
                                    <PdfIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>

                                <Tooltip title="Download Word">
                                  <IconButton size="small" color="primary"
                                    onClick={() => window.open(exportUrl(tt.id, 'docx'), '_blank')}>
                                    <DocxIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title="Version History">
                                  <IconButton size="small"
                                    onClick={() => { setVersionTimetable(tt); setVersionOpen(true); }}>
                                    <HistoryIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Stack>
                            </Box>
                          )}
                        </Stack>
                      </CardContent>
                    </Card>
                  </Zoom>
                </Grid>
              );
            })}
          </Grid>
        )}

        {/* ── Create Dialog ─────────────────────── */}
        <Dialog open={openCreate} onClose={() => setOpenCreate(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Create New Timetable</DialogTitle>
          <DialogContent>
            {createError && <Alert severity="error" sx={{ mb: 2 }}>{createError}</Alert>}
            <TextField
              autoFocus margin="dense" label="Name" fullWidth required
              placeholder="e.g. 2025/2026 Semester 1"
              value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
            />
            <TextField
              margin="dense" label="Semester" fullWidth
              placeholder="e.g. Semester 1"
              value={formData.semester}
              onChange={e => setFormData({ ...formData, semester: e.target.value })}
            />
            <TextField
              margin="dense" label="Year" type="number" fullWidth
              value={formData.year}
              onChange={e => setFormData({ ...formData, year: parseInt(e.target.value) })}
              inputProps={{ min: 2020, max: 2035 }}
            />
            <FormControl fullWidth margin="dense">
              <InputLabel>Academic Half</InputLabel>
              <Select
                value={formData.academic_half} label="Academic Half"
                onChange={e => setFormData({ ...formData, academic_half: e.target.value })}
              >
                <MenuItem value="first_half">First Half</MenuItem>
                <MenuItem value="second_half">Second Half</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth margin="dense" required>
              <InputLabel>School</InputLabel>
              <Select
                value={formData.school_id || ''}
                label="School"
                onChange={e => setFormData({ ...formData, school_id: e.target.value ? Number(e.target.value) : undefined })}
                disabled={!isTenantAdmin}
              >
                {schools.map((school) => (
                  <MenuItem key={school.id} value={school.id}>
                    {school.name} ({school.code})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
              Time Grid Configuration
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <TextField
                margin="dense"
                label="Start Time"
                type="time"
                fullWidth
                value={formData.grid_config.start_time}
                onChange={e => setFormData({
                  ...formData,
                  grid_config: { ...formData.grid_config, start_time: e.target.value },
                })}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                margin="dense"
                label="End Time"
                type="time"
                fullWidth
                value={formData.grid_config.end_time}
                onChange={e => setFormData({
                  ...formData,
                  grid_config: { ...formData.grid_config, end_time: e.target.value },
                })}
                InputLabelProps={{ shrink: true }}
              />
            </Stack>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <TextField
                margin="dense"
                label="Lunch Start"
                type="time"
                fullWidth
                value={formData.grid_config.lunch_start}
                onChange={e => setFormData({
                  ...formData,
                  grid_config: { ...formData.grid_config, lunch_start: e.target.value },
                })}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                margin="dense"
                label="Lunch End"
                type="time"
                fullWidth
                value={formData.grid_config.lunch_end}
                onChange={e => setFormData({
                  ...formData,
                  grid_config: { ...formData.grid_config, lunch_end: e.target.value },
                })}
                InputLabelProps={{ shrink: true }}
              />
            </Stack>
            <FormControl fullWidth margin="dense">
              <InputLabel>Active Days</InputLabel>
              <Select
                multiple
                value={formData.grid_config.active_days}
                label="Active Days"
                onChange={e => setFormData({
                  ...formData,
                  grid_config: {
                    ...formData.grid_config,
                    active_days: e.target.value as string[],
                  },
                })}
              >
                {ACTIVE_DAY_OPTIONS.map(day => (
                  <MenuItem key={day} value={day}>{day}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Typography variant="caption" color="text.secondary">
              This controls generator day/time boundaries for this timetable instance.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOpenCreate(false)}>Cancel</Button>
            <Button onClick={() => void handleCreate()} variant="contained" disabled={creating || !formData.school_id}>
              {creating ? <CircularProgress size={18} /> : 'Create & Configure'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* ── Generate Dialog ───────────────────── */}
        <Dialog
          open={openGenerate}
          onClose={() => { if (!generationProgress && !generationComplete) handleCancelGenerate(); }}
          maxWidth="sm" fullWidth
        >
          <DialogTitle>
            Prepare Lectures: {selectedTimetable?.name}
          </DialogTitle>
          <DialogContent>
            <Box sx={{ mt: 1 }}>

              {/* Pre-generation options */}
              {!generationProgress && !generationComplete && !generationError && (
                <>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    This run prepares <strong>lecture sessions only</strong>. Lab and tutorial schedules are managed separately.
                  </Alert>
                  <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                    Execution Mode
                  </Typography>
                  <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
                    <FormGroup>
                      <FormControlLabel
                        control={<Checkbox checked={runInBackground}
                          onChange={e => setRunInBackground(e.target.checked)} />}
                        label="Run in background (Recommended)"
                      />
                    </FormGroup>
                  </Paper>

                  <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                    Scheduling Profile
                  </Typography>
                  <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
                    <FormControl fullWidth size="small">
                      <Select
                        value={schedulingProfile}
                        onChange={(e) => setSchedulingProfile(e.target.value)}
                      >
                        <MenuItem value="balanced">Balanced (Default)</MenuItem>
                        <MenuItem value="compact">Compact Week (Prioritize free days)</MenuItem>
                        <MenuItem value="wellbeing">Student Wellbeing (Limit daily load & fatigue)</MenuItem>
                      </Select>
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                        Choose the timetable style that best fits your school’s teaching week.
                      </Typography>
                    </FormControl>
                  </Paper>

                  <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                    Generation Time Window
                  </Typography>
                  <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                      <TextField
                        label="Start Time"
                        type="time"
                        fullWidth
                        value={generationWindow.start_time}
                        onChange={e => setGenerationWindow({
                          ...generationWindow,
                          start_time: e.target.value,
                        })}
                        InputLabelProps={{ shrink: true }}
                      />
                      <TextField
                        label="End Time"
                        type="time"
                        fullWidth
                        value={generationWindow.end_time}
                        onChange={e => setGenerationWindow({
                          ...generationWindow,
                          end_time: e.target.value,
                        })}
                        InputLabelProps={{ shrink: true }}
                      />
                    </Stack>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 1.5 }}>
                      <TextField
                        label="Lunch Start"
                        type="time"
                        fullWidth
                        value={generationWindow.lunch_start}
                        onChange={e => setGenerationWindow({
                          ...generationWindow,
                          lunch_start: e.target.value,
                        })}
                        InputLabelProps={{ shrink: true }}
                      />
                      <TextField
                        label="Lunch End"
                        type="time"
                        fullWidth
                        value={generationWindow.lunch_end}
                        onChange={e => setGenerationWindow({
                          ...generationWindow,
                          lunch_end: e.target.value,
                        })}
                        InputLabelProps={{ shrink: true }}
                      />
                    </Stack>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                      This run enforces the selected day window and lunch break, then stores them on the timetable.
                    </Typography>
                  </Paper>
                </>
              )}

              {/* Live progress */}
              {generationProgress && !generationComplete && !generationError && (
                <Box
                  sx={{
                    position: 'relative',
                    overflow: 'hidden',
                    borderRadius: 4,
                    px: { xs: 2.5, sm: 4 },
                    py: 4.5,
                    textAlign: 'center',
                    color: '#fff',
                    background: 'linear-gradient(135deg, #0f4c81 0%, #276fd1 52%, #7651c8 100%)',
                    boxShadow: '0 18px 40px rgba(41, 91, 173, 0.28)',
                    '@keyframes timetableGlow': {
                      '0%, 100%': { transform: 'scale(0.92)', opacity: 0.38 },
                      '50%': { transform: 'scale(1.12)', opacity: 0.68 },
                    },
                    '@keyframes timetableDrift': {
                      '0%': { transform: 'translateX(-30%) rotate(0deg)' },
                      '100%': { transform: 'translateX(30%) rotate(360deg)' },
                    },
                  }}
                >
                  <Box sx={{ position: 'absolute', width: 260, height: 260, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.10)', top: -145, left: -80, animation: 'timetableGlow 4s ease-in-out infinite', pointerEvents: 'none' }} />
                  <Box sx={{ position: 'absolute', width: 190, height: 190, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.18)', bottom: -125, right: -25, animation: 'timetableDrift 18s linear infinite', pointerEvents: 'none' }} />
                  <Box sx={{ position: 'relative', zIndex: 1, mx: 'auto', width: 76, height: 76, display: 'grid', placeItems: 'center', borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.13)', border: '1px solid rgba(255,255,255,0.28)', boxShadow: '0 0 0 10px rgba(255,255,255,0.05)', mb: 2.5 }}>
                    <CircularProgress size={50} thickness={3.2} sx={{ color: '#fff' }} />
                  </Box>
                  <Typography variant="h6" fontWeight={800} sx={{ letterSpacing: '-0.01em' }}>
                    {generationProgress.percentage < 20
                      ? 'Preparing your lecture timetable'
                      : generationProgress.percentage < 70
                        ? 'Arranging your teaching week'
                        : 'Adding the finishing touches'}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1, color: 'rgba(255,255,255,0.78)' }}>
                    Please keep this page open while we prepare your schedule.
                  </Typography>
                  <Box sx={{ mt: 3.5, mx: 'auto', maxWidth: 370, height: 8, overflow: 'hidden', borderRadius: 99, bgcolor: 'rgba(255,255,255,0.18)' }}>
                    <Box sx={{ width: `${Math.max(6, generationProgress.percentage)}%`, height: '100%', borderRadius: 99, background: 'linear-gradient(90deg, #d8efff, #ffffff)', transition: 'width 700ms cubic-bezier(0.22, 1, 0.36, 1)', boxShadow: '0 0 18px rgba(255,255,255,0.75)' }} />
                  </Box>
                </Box>
              )}

              {/* Success */}
              {generationComplete && (
                <Alert severity="success" icon={<CheckIcon />} sx={{ mt: 1 }}>
                  <strong>Done!</strong> Timetable generated for all year levels.
                </Alert>
              )}

              {/* Error */}
              {generationError && (
                <Alert severity="error" icon={<ErrorIcon />} sx={{ mt: 1 }}>
                  <strong>Error:</strong> {generationError}
                </Alert>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            {!generationProgress && !generationComplete && (
              <>
                <Button onClick={handleCancelGenerate}>Cancel</Button>
                <Button
                  onClick={handleGenerate}
                  variant="contained"
                  startIcon={<PlayIcon />}
                  sx={{ background: 'linear-gradient(135deg, #1976d2 0%, #115293 100%)' }}
                >
                  Prepare Lectures
                </Button>
              </>
            )}
            {/* During generation — show only cancel */}
            {generationProgress && !generationComplete && !generationError && (
              <Button onClick={handleCancelGenerate} color="error">Cancel Generation</Button>
            )}
            {(generationComplete || generationError) && (
              <Button onClick={() => setOpenGenerate(false)} variant="contained">Close</Button>
            )}
          </DialogActions>
        </Dialog>

        {/* ── Version History Dialog ────────────── */}
        <Dialog open={versionOpen} onClose={() => setVersionOpen(false)} maxWidth="md" fullWidth>
          <DialogTitle>
            Version History — {versionTimetable?.name}
            <Typography variant="caption" color="text.secondary" display="block">
              {versionTimetable?.semester} {versionTimetable?.year}
            </Typography>
          </DialogTitle>
          <DialogContent>
            {versionTimetable && (
              <VersionHistory
                timetableId={versionTimetable.id}
                timetableName={versionTimetable.name}
                onVersionRestored={() => { void fetchTimetables(); setVersionOpen(false); }}
              />
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setVersionOpen(false)}>Close</Button>
          </DialogActions>
        </Dialog>

        {/* ── Delete Confirmation Dialog ─────────── */}
        <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
          <DialogTitle sx={{ color: 'error.main' }}>Delete Timetable</DialogTitle>
          <DialogContent>
            <Alert severity="warning" sx={{ mb: 2 }}>
              This will permanently delete <strong>{deleteTarget?.name}</strong> and all its generated slots, versions, and overrides. This action cannot be undone.
            </Alert>
            <Typography variant="body2" color="text.secondary">
              {deleteTarget?.semester} · {deleteTarget?.year}
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteTarget(null)} disabled={deleting}>Cancel</Button>
            <Button
              onClick={() => void handleDelete()}
              variant="contained"
              color="error"
              disabled={deleting}
              startIcon={deleting ? <CircularProgress size={16} /> : <DeleteIcon />}
            >
              {deleting ? 'Deleting…' : 'Delete Permanently'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Fade>
  );
};

export default TimetablesPage;
