import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Tooltip,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  Add as AddIcon,
  AirlineSeatReclineNormal as SeatingIcon,
  AnalyticsRounded as DiagnosticsIcon,
  AutoAwesome as GenerateIcon,
  CheckCircleRounded as HealthyIcon,
  DeleteOutlineRounded as DeleteIcon,
  EventAvailable as PublishIcon,
  FactCheck as ExamIcon,
  FilterAltOffRounded as ClearIcon,
  FlagRounded as FlagIcon,
  LayersClearRounded as ClearDraftIcon,
  LibraryBooksRounded as CatalogIcon,
  MeetingRoom as RoomIcon,
  RefreshRounded as SyncIcon,
  Schedule as WindowIcon,
  SearchRounded as SearchIcon,
  WarningAmberRounded as WarningIcon,
} from '@mui/icons-material';
import { Navigate } from 'react-router-dom';

import {
  coursesAPI,
  ExamPaper,
  ExamPaperCandidate,
  ExamPeriod,
  ExamSeatingProfile,
  examTimetablesAPI,
  groupsAPI,
  roomsAPI,
} from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';

interface CourseOption {
  id: number;
  code: string;
  name: string;
  level: number;
  preferred_room_type?: string | null;
}

interface GroupOption {
  id: number;
  name: string;
  size: number;
  level: number;
}

interface RoomOption {
  id: number;
  name: string;
  building: string;
  capacity: number;
  room_type: string;
  is_blocked?: boolean;
}

const todayYear = new Date().getFullYear();

const initialPeriodForm = {
  name: '',
  semester: 'Semester 1',
  year: todayYear,
  start_date: '',
  end_date: '',
  preferred_max_papers_per_day: 1,
  hard_max_papers_per_day: 2,
  min_gap_hours: 24,
  allow_same_day_multiple_papers: true,
};

const initialWindowForm = {
  name: 'Morning',
  start_time: '08:00:00',
  end_time: '12:00:00',
  display_order: 1,
  allow_weekends: false,
  is_active: true,
};

const initialProfileForm = {
  name: '',
  description: '',
  capacity_factor: 100,
  fixed_capacity: '',
  requires_computers: false,
  spacing_strategy: 'standard',
  is_default: false,
};

const initialPaperForm = {
  paper_code: '',
  paper_name: '',
  course_id: '',
  duration_minutes: 180,
  candidate_count: '',
  group_ids: [] as number[],
  preferred_room_type: 'lecture_hall',
  preferred_seating_profile_id: '',
  max_rooms: 1,
  allow_custom_window: false,
};

const formatDateLabel = (value?: string | null) => {
  if (!value) return 'Not set';
  return new Date(value).toLocaleDateString();
};

const formatTimeLabel = (value?: string | null) => {
  if (!value) return '--';
  return value.slice(0, 5);
};

const startCaseFlag = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (match) => match.toUpperCase());

const formatDiagnosticReason = (value: string) => {
  const labels: Record<string, string> = {
    window_too_short: 'Session windows too short',
    group_time_conflict: 'Group time conflicts',
    hard_daily_limit: 'Daily load cap reached',
    minimum_spacing: 'Minimum spacing blocked',
    rooms_unavailable: 'Rooms unavailable',
    capacity_insufficient: 'Capacity insufficient',
    too_many_rooms_required: 'Too many rooms required',
    room_bundle_unavailable: 'No valid room bundle',
  };
  return labels[value] || startCaseFlag(value);
};

const normalizeLevelLabel = (level: number) => {
  const resolved = level >= 100 ? Math.round(level / 100) : level;
  return `Year ${resolved}`;
};

const effectiveCapacityForProfile = (room: RoomOption, profile?: ExamSeatingProfile | null) => {
  if (profile?.fixed_capacity) return profile.fixed_capacity;
  const factor = Math.max(0, Math.min(100, profile?.capacity_factor ?? 100));
  return Math.floor(room.capacity * (factor / 100));
};

const ExamTimetablesPage: React.FC = () => {
  const { isCoordinator, isHOD } = useAuth();
  const { branding } = useBranding();
  const theme = useTheme();

  const primaryColor = branding.primary_color || theme.palette.primary.main;
  const secondaryColor = branding.secondary_color || '#ff8c00';
  const [activeTab, setActiveTab] = useState<'overview' | 'papers' | 'timetable' | 'diagnostics'>('overview');

  const [periods, setPeriods] = useState<ExamPeriod[]>([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<ExamPeriod | null>(null);
  const [seatingProfiles, setSeatingProfiles] = useState<ExamSeatingProfile[]>([]);
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [groups, setGroups] = useState<GroupOption[]>([]);
  const [rooms, setRooms] = useState<RoomOption[]>([]);
  const [paperCandidates, setPaperCandidates] = useState<ExamPaperCandidate[]>([]);
  const [selectedCourseIds, setSelectedCourseIds] = useState<number[]>([]);

  const [loading, setLoading] = useState(true);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [pageError, setPageError] = useState('');
  const [pageSuccess, setPageSuccess] = useState('');

  const [periodDialogOpen, setPeriodDialogOpen] = useState(false);
  const [windowDialogOpen, setWindowDialogOpen] = useState(false);
  const [profileDialogOpen, setProfileDialogOpen] = useState(false);
  const [paperDialogOpen, setPaperDialogOpen] = useState(false);

  const [periodForm, setPeriodForm] = useState(initialPeriodForm);
  const [windowForm, setWindowForm] = useState(initialWindowForm);
  const [profileForm, setProfileForm] = useState(initialProfileForm);
  const [paperForm, setPaperForm] = useState(initialPaperForm);

  const [candidateSearch, setCandidateSearch] = useState('');
  const [candidateFilter, setCandidateFilter] = useState<'all' | 'selected' | 'included' | 'notIncluded'>('all');
  const [syncDefaults, setSyncDefaults] = useState({
    default_duration_minutes: 180,
    default_max_rooms: 2,
    preferred_seating_profile_id: '',
    allow_custom_window: false,
  });

  const selectedSlots = selectedPeriod?.slots ?? [];
  const selectedWindows = selectedPeriod?.session_windows ?? [];
  const selectedPapers = selectedPeriod?.papers ?? [];
  const selectedConstraints = selectedPeriod?.constraint_settings;
  const generationMetadata = selectedPeriod?.generation_metadata ?? null;
  const unscheduledPapers = selectedPeriod?.generation_metadata?.unscheduled_papers ?? [];
  const scheduledFlags = selectedPeriod?.generation_metadata?.scheduled_flags ?? [];
  const diagnosticsSummary = selectedPeriod?.generation_metadata?.diagnostics_summary ?? null;

  const groupLookup = useMemo(() => new Map(groups.map((group) => [group.id, group])), [groups]);

  const defaultSeatingProfile = useMemo(
    () => seatingProfiles.find((profile) => profile.is_default) ?? seatingProfiles[0] ?? null,
    [seatingProfiles],
  );

  const selectedSyncProfile = useMemo(
    () => seatingProfiles.find((profile) => profile.id === Number(syncDefaults.preferred_seating_profile_id))
      ?? defaultSeatingProfile,
    [defaultSeatingProfile, seatingProfiles, syncDefaults.preferred_seating_profile_id],
  );

  const availableRooms = useMemo(
    () => rooms.filter((room) => room.is_blocked !== true),
    [rooms],
  );

  const roomUtilizationSummary = useMemo(() => {
    const usedRoomIds = new Set<number>();
    selectedSlots.forEach((slot) => {
      slot.room_allocations.forEach((allocation) => usedRoomIds.add(allocation.room_id));
    });
    return {
      totalRooms: availableRooms.length,
      usedRooms: usedRoomIds.size,
      rawCapacity: availableRooms.reduce((sum, room) => sum + Number(room.capacity || 0), 0),
      effectiveCapacity: availableRooms.reduce(
        (sum, room) => sum + effectiveCapacityForProfile(room, selectedSyncProfile),
        0,
      ),
    };
  }, [availableRooms, selectedSlots, selectedSyncProfile]);

  const candidateLookup = useMemo(
    () => new Map(paperCandidates.map((candidate) => [candidate.course_id, candidate])),
    [paperCandidates],
  );

  const manageableCandidates = useMemo(
    () => paperCandidates.filter((candidate) => candidate.can_manage),
    [paperCandidates],
  );

  const manageableCandidateIds = useMemo(
    () => manageableCandidates.map((candidate) => candidate.course_id),
    [manageableCandidates],
  );

  const canConfigurePeriod = isCoordinator;
  const canGenerateOrPublish = isCoordinator;
  const canMarkPapers = isHOD;

  const selectedCandidateCount = useMemo(
    () => selectedCourseIds.reduce((sum, courseId) => sum + (candidateLookup.get(courseId)?.candidate_count ?? 0), 0),
    [candidateLookup, selectedCourseIds],
  );

  const alreadyIncludedCount = useMemo(
    () => paperCandidates.filter((candidate) => candidate.already_included).length,
    [paperCandidates],
  );

  const allocatedDraftSeats = useMemo(
    () => selectedSlots.reduce((sum, slot) => sum + Number(slot.total_allocated_capacity ?? 0), 0),
    [selectedSlots],
  );

  const draftDiagnosticsCards = useMemo(
    () => ([
      {
        label: 'Scheduled cleanly',
        value: Math.max(0, selectedSlots.length - scheduledFlags.length),
        tone: 'success' as const,
        note: 'Placements without follow-up flags',
      },
      {
        label: 'Needs review',
        value: scheduledFlags.length,
        tone: scheduledFlags.length > 0 ? ('warning' as const) : ('success' as const),
        note: 'Draft slots with fit, spacing, or load signals',
      },
      {
        label: 'Unscheduled',
        value: unscheduledPapers.length,
        tone: unscheduledPapers.length > 0 ? ('warning' as const) : ('success' as const),
        note: 'Papers still waiting for a valid placement',
      },
    ]),
    [scheduledFlags.length, selectedSlots.length, unscheduledPapers.length],
  );

  const draftHealthTone = useMemo(() => {
    if (unscheduledPapers.length > 0) return 'warning';
    if (scheduledFlags.length > 0) return 'info';
    return 'success';
  }, [scheduledFlags.length, unscheduledPapers.length]);

  const draftHealthLabel = useMemo(() => {
    if (unscheduledPapers.length > 0) return 'Draft needs attention';
    if (scheduledFlags.length > 0) return 'Draft is usable with review notes';
    if (selectedSlots.length > 0) return 'Draft looks balanced';
    return 'No draft yet';
  }, [scheduledFlags.length, selectedSlots.length, unscheduledPapers.length]);

  const seatDemandRatio = useMemo(() => {
    if (roomUtilizationSummary.effectiveCapacity <= 0) return 0;
    return Math.min(100, Math.round((selectedCandidateCount / roomUtilizationSummary.effectiveCapacity) * 100));
  }, [roomUtilizationSummary.effectiveCapacity, selectedCandidateCount]);

  const filteredCandidates = useMemo(() => {
    const search = candidateSearch.trim().toLowerCase();
    return paperCandidates.filter((candidate) => {
      if (candidateFilter === 'selected' && !selectedCourseIds.includes(candidate.course_id)) return false;
      if (candidateFilter === 'included' && !candidate.already_included) return false;
      if (candidateFilter === 'notIncluded' && candidate.already_included) return false;

      if (!search) return true;
      const groupText = candidate.groups.map((group) => group.name).join(' ').toLowerCase();
      return [
        candidate.course_code,
        candidate.course_name,
        normalizeLevelLabel(candidate.course_level),
        groupText,
      ].join(' ').toLowerCase().includes(search);
    });
  }, [candidateFilter, candidateSearch, paperCandidates, selectedCourseIds]);

  const refreshReferenceData = async () => {
    const [profileList, courseList, groupList, roomList] = await Promise.all([
      examTimetablesAPI.getSeatingProfiles(),
      coursesAPI.getAll(),
      groupsAPI.getAll(),
      roomsAPI.getAll(),
    ]);
    setSeatingProfiles(profileList);
    setCourses(courseList);
    setGroups(groupList);
    setRooms(roomList);
  };

  const loadPaperCandidates = async (periodId: number) => {
    setCandidateLoading(true);
    try {
      const candidates = await examTimetablesAPI.getPaperCandidates(periodId);
      setPaperCandidates(candidates);
      setSelectedCourseIds((current) => {
        const validCurrent = current.filter((courseId) => {
          const candidate = candidates.find((item) => item.course_id === courseId);
          return candidate && candidate.can_manage;
        });
        if (validCurrent.length > 0) return validCurrent;
        const includedIds = candidates
          .filter((candidate) => candidate.already_included && candidate.can_manage)
          .map((candidate) => candidate.course_id);
        return includedIds.length > 0
          ? includedIds
          : candidates.filter((candidate) => candidate.can_manage).map((candidate) => candidate.course_id);
      });
    } finally {
      setCandidateLoading(false);
    }
  };

  const refreshPeriods = async (keepSelection: boolean = true) => {
    const periodList = await examTimetablesAPI.getPeriods();
    setPeriods(periodList);

    const fallbackId = keepSelection
      ? selectedPeriodId ?? periodList[0]?.id ?? null
      : periodList[0]?.id ?? null;
    const nextSelectedId = periodList.some((period) => period.id === fallbackId) ? fallbackId : periodList[0]?.id ?? null;
    setSelectedPeriodId(nextSelectedId);

    if (nextSelectedId) {
      const period = await examTimetablesAPI.getPeriod(nextSelectedId);
      setSelectedPeriod(period);
      await loadPaperCandidates(nextSelectedId);
    } else {
      setSelectedPeriod(null);
      setPaperCandidates([]);
      setSelectedCourseIds([]);
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setPageError('');
      try {
        await Promise.all([refreshReferenceData(), refreshPeriods(false)]);
      } catch (error: any) {
        setPageError(error?.response?.data?.detail || error?.message || 'Failed to load exam scheduling workspace.');
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const selectPeriod = async (periodId: number) => {
    setSelectedPeriodId(periodId);
    setBusyAction('load-period');
    setPageError('');
    try {
      const period = await examTimetablesAPI.getPeriod(periodId);
      setSelectedPeriod(period);
      await loadPaperCandidates(periodId);
    } catch (error: any) {
      setPageError(error?.response?.data?.detail || error?.message || 'Failed to load exam period.');
    } finally {
      setBusyAction(null);
    }
  };

  const resetMessages = () => {
    setPageError('');
    setPageSuccess('');
  };

  const withAction = async (actionKey: string, action: () => Promise<void>) => {
    setBusyAction(actionKey);
    resetMessages();
    try {
      await action();
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setPageError(detail.map((item: any) => item.message || JSON.stringify(item)).join(' | '));
      } else if (typeof detail === 'object' && detail?.message) {
        setPageError(detail.message);
      } else {
        setPageError(detail || error?.message || 'The requested action failed.');
      }
    } finally {
      setBusyAction(null);
    }
  };

  const handleCreatePeriod = async () => {
    await withAction('create-period', async () => {
      const created = await examTimetablesAPI.createPeriod({
        name: periodForm.name,
        semester: periodForm.semester,
        year: Number(periodForm.year),
        start_date: periodForm.start_date,
        end_date: periodForm.end_date,
        constraint_settings: {
          preferred_max_papers_per_day: Number(periodForm.preferred_max_papers_per_day),
          hard_max_papers_per_day: Number(periodForm.hard_max_papers_per_day),
          min_gap_hours: Number(periodForm.min_gap_hours),
          allow_same_day_multiple_papers: periodForm.allow_same_day_multiple_papers,
        },
      });
      setPeriodDialogOpen(false);
      setPeriodForm(initialPeriodForm);
      setSelectedPeriodId(created.id);
      await refreshPeriods();
      setPageSuccess(`Created exam period "${created.name}".`);
    });
  };

  const handleDeletePeriod = async (period: ExamPeriod) => {
    if (!window.confirm(`Delete exam period "${period.name}"?`)) return;

    await withAction('delete-period', async () => {
      await examTimetablesAPI.deletePeriod(period.id);
      const wasSelected = selectedPeriodId === period.id;
      if (wasSelected) {
        setSelectedPeriodId(null);
        setSelectedPeriod(null);
        setPaperCandidates([]);
        setSelectedCourseIds([]);
      }
      await refreshPeriods(!wasSelected);
      setPageSuccess(`Deleted exam period "${period.name}".`);
    });
  };

  const handleCreateWindow = async () => {
    if (!selectedPeriod) return;
    await withAction('create-window', async () => {
      await examTimetablesAPI.createSessionWindow(selectedPeriod.id, {
        ...windowForm,
        display_order: Number(windowForm.display_order),
      });
      setWindowDialogOpen(false);
      setWindowForm({
        ...initialWindowForm,
        display_order: selectedWindows.length + 1,
      });
      await selectPeriod(selectedPeriod.id);
      setPageSuccess('Session window added.');
    });
  };

  const handleCreateProfile = async () => {
    await withAction('create-profile', async () => {
      await examTimetablesAPI.createSeatingProfile({
        name: profileForm.name,
        description: profileForm.description || null,
        capacity_factor: Number(profileForm.capacity_factor),
        fixed_capacity: profileForm.fixed_capacity ? Number(profileForm.fixed_capacity) : null,
        requires_computers: profileForm.requires_computers,
        spacing_strategy: profileForm.spacing_strategy,
        is_default: profileForm.is_default,
      });
      setProfileDialogOpen(false);
      setProfileForm(initialProfileForm);
      await refreshReferenceData();
      if (selectedPeriodId) {
        await selectPeriod(selectedPeriodId);
      }
      setPageSuccess('Seating profile saved.');
    });
  };

  const handleCreatePaper = async () => {
    if (!selectedPeriod) return;
    await withAction('create-paper', async () => {
      await examTimetablesAPI.createPaper(selectedPeriod.id, {
        paper_code: paperForm.paper_code,
        paper_name: paperForm.paper_name,
        course_id: paperForm.course_id ? Number(paperForm.course_id) : null,
        duration_minutes: Number(paperForm.duration_minutes),
        candidate_count: paperForm.candidate_count ? Number(paperForm.candidate_count) : null,
        group_ids: paperForm.group_ids,
        preferred_room_type: paperForm.preferred_room_type,
        preferred_seating_profile_id: paperForm.preferred_seating_profile_id ? Number(paperForm.preferred_seating_profile_id) : null,
        max_rooms: Number(paperForm.max_rooms),
        allow_custom_window: paperForm.allow_custom_window,
      });
      setPaperDialogOpen(false);
      setPaperForm(initialPaperForm);
      await selectPeriod(selectedPeriod.id);
      setPageSuccess('Manual exam paper added.');
    });
  };

  const handleSyncPapers = async () => {
    if (!selectedPeriod) return;
    await withAction('sync-papers', async () => {
      const result = await examTimetablesAPI.syncPapers(selectedPeriod.id, {
        course_ids: selectedCourseIds,
        default_duration_minutes: Number(syncDefaults.default_duration_minutes),
        default_max_rooms: Number(syncDefaults.default_max_rooms),
        preferred_seating_profile_id: syncDefaults.preferred_seating_profile_id
          ? Number(syncDefaults.preferred_seating_profile_id)
          : null,
        allow_custom_window: syncDefaults.allow_custom_window,
      });
      await selectPeriod(selectedPeriod.id);
      setPageSuccess(
        `Paper list synchronized. ${result.created_count} created, ${result.updated_count} refreshed, ${result.removed_count} removed.`,
      );
    });
  };

  const handleGenerate = async () => {
    if (!selectedPeriod) return;
    await withAction('generate', async () => {
      const result = await examTimetablesAPI.generate(selectedPeriod.id, true);
      await selectPeriod(selectedPeriod.id);
      setPageSuccess(
        result.unscheduled_count > 0
          ? `Generation finished with ${result.scheduled_count} scheduled paper(s) and ${result.unscheduled_count} unscheduled paper(s).`
          : `Generation finished successfully with ${result.scheduled_count} scheduled paper(s).`,
      );
    });
  };

  const handleClearDraft = async () => {
    if (!selectedPeriod) return;
    if (!window.confirm(`Clear the current draft timetable for "${selectedPeriod.name}"?`)) return;

    await withAction('clear-draft', async () => {
      await examTimetablesAPI.clearDraft(selectedPeriod.id);
      await selectPeriod(selectedPeriod.id);
      setPageSuccess(`Cleared the current draft timetable for "${selectedPeriod.name}".`);
    });
  };

  const handlePublish = async () => {
    if (!selectedPeriod) return;
    await withAction('publish', async () => {
      const period = await examTimetablesAPI.publish(selectedPeriod.id, true);
      setSelectedPeriod(period);
      await refreshPeriods();
      setPageSuccess(`Published and locked "${period.name}".`);
    });
  };

  const toggleCourseSelection = (courseId: number) => {
    const candidate = candidateLookup.get(courseId);
    if (!candidate?.can_manage) return;
    setSelectedCourseIds((current) => (
      current.includes(courseId)
        ? current.filter((item) => item !== courseId)
        : [...current, courseId]
    ));
  };

  const handleCourseSelectedForManualPaper = (courseId: string) => {
    const course = courses.find((item) => item.id === Number(courseId));
    const candidate = paperCandidates.find((item) => item.course_id === Number(courseId));
    setPaperForm((current) => ({
      ...current,
      course_id: courseId,
      paper_code: course?.code || current.paper_code,
      paper_name: course?.name || current.paper_name,
      preferred_room_type: candidate?.preferred_room_type || course?.preferred_room_type || current.preferred_room_type,
      group_ids: candidate?.group_ids ?? current.group_ids,
      candidate_count: candidate?.candidate_count ? String(candidate.candidate_count) : current.candidate_count,
    }));
  };

  if (!isHOD) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: `radial-gradient(ellipse at top, ${alpha(secondaryColor, 0.12)} 0%, transparent 38%), linear-gradient(180deg, ${alpha(primaryColor, 0.06)} 0%, #f8f4ef 35%, #eef2f7 100%)`,
        p: { xs: 2, md: 4 },
      }}
    >
      <Stack spacing={3}>
        {/* ── Hero Card ── */}
        <Card
          sx={{
            borderRadius: 5,
            overflow: 'hidden',
            color: '#fff',
            background: `linear-gradient(145deg, ${primaryColor} 0%, ${alpha(primaryColor, 0.88)} 52%, ${secondaryColor} 100%)`,
            boxShadow: `0 24px 60px ${alpha(primaryColor, 0.28)}`,
          }}
        >
          <CardContent sx={{ p: { xs: 2.5, md: 3 } }}>
            <Stack direction={{ xs: 'column', lg: 'row' }} justifyContent="space-between" spacing={2} alignItems={{ xs: 'flex-start', lg: 'center' }}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="overline" sx={{ letterSpacing: '0.14em', opacity: 0.78, display: 'block' }}>
                  {branding.short_name || branding.name || 'TABLESYS'} · Exam Workspace
                </Typography>
                <Typography variant="h4" fontWeight={800} color="inherit" sx={{ lineHeight: 1.2, mt: 0.4 }}>
                  {selectedPeriod ? selectedPeriod.name : 'Exam Timetable Planning'}
                </Typography>
                <Typography sx={{ mt: 0.75, opacity: 0.82, maxWidth: 640 }}>
                  {selectedPeriod
                    ? `${selectedPeriod.semester} ${selectedPeriod.year} · ${formatDateLabel(selectedPeriod.start_date)} – ${formatDateLabel(selectedPeriod.end_date)}`
                    : 'Build one exam cycle at a time: set scheduling rules, sync papers, generate the draft, then publish.'}
                </Typography>
                {selectedPeriod && (
                  <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                    {selectedPeriod.is_published && <Chip label="Published" size="small" sx={{ bgcolor: alpha('#fff', 0.22), color: '#fff', fontWeight: 700 }} />}
                    {selectedPeriod.is_locked && <Chip label="Locked" size="small" sx={{ bgcolor: alpha('#fff', 0.18), color: '#fff', fontWeight: 700 }} />}
                    {!selectedPeriod.is_published && !selectedPeriod.is_locked && <Chip label="Draft" size="small" sx={{ bgcolor: alpha('#fff', 0.15), color: '#fff', fontWeight: 700 }} />}
                  </Stack>
                )}
              </Box>
              <Stack direction="row" spacing={1.5} flexWrap="wrap" alignItems="center">
                {selectedPeriod
                  ? (
                    ([['Papers', selectedPapers.length], ['Slots', selectedSlots.length], ['Windows', selectedWindows.length], ['Venues', availableRooms.length]] as [string, number][]).map(([label, val]) => (
                      <Paper key={label} elevation={0} sx={{ p: 1.5, borderRadius: 2.5, bgcolor: alpha('#fff', 0.15), color: '#fff', minWidth: 72, textAlign: 'center', backdropFilter: 'blur(8px)' }}>
                        <Typography variant="h5" fontWeight={800}>{val}</Typography>
                        <Typography variant="caption" sx={{ opacity: 0.82 }}>{label}</Typography>
                      </Paper>
                    ))
                  ) : (
                    <>
                      <Chip label={`${periods.length} period${periods.length === 1 ? '' : 's'}`} sx={{ bgcolor: alpha('#fff', 0.18), color: '#fff', fontWeight: 600 }} />
                      <Chip label={`${availableRooms.length} venues`} sx={{ bgcolor: alpha('#fff', 0.18), color: '#fff', fontWeight: 600 }} />
                      {canConfigurePeriod && (
                        <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setPeriodDialogOpen(true)} sx={{ borderColor: alpha('#fff', 0.5), color: '#fff', fontWeight: 700, '&:hover': { borderColor: '#fff', bgcolor: alpha('#fff', 0.1) } }}>
                          New Period
                        </Button>
                      )}
                    </>
                  )}
              </Stack>
            </Stack>
            {/* Tab nav strip */}
            <Stack direction="row" spacing={0.5} sx={{ mt: 2.5, pt: 2, borderTop: `1px solid ${alpha('#fff', 0.2)}`, flexWrap: 'wrap', gap: 0.5 }}>
              {(['overview', 'papers', 'timetable', 'diagnostics'] as const).map((tab) => {
                const labels: Record<string, string> = { overview: 'Overview', papers: 'Papers', timetable: 'Timetable', diagnostics: 'Diagnostics' };
                const active = activeTab === tab;
                return (
                  <Button key={tab} size="small" onClick={() => setActiveTab(tab)} sx={{ borderRadius: 99, px: 2.25, py: 0.6, fontWeight: 700, textTransform: 'none', whiteSpace: 'nowrap', bgcolor: active ? alpha('#fff', 0.22) : 'transparent', color: '#fff', border: `1px solid ${active ? alpha('#fff', 0.5) : alpha('#fff', 0.2)}`, '&:hover': { bgcolor: alpha('#fff', 0.15) } }}>
                    {labels[tab]}
                  </Button>
                );
              })}
            </Stack>
          </CardContent>
        </Card>

        {pageError && <Alert severity="error" onClose={() => setPageError('')}>{pageError}</Alert>}
        {pageSuccess && <Alert severity="success" onClose={() => setPageSuccess('')}>{pageSuccess}</Alert>}

        {!selectedPeriod && periods.length === 0 ? (
          <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: alpha(primaryColor, 0.1), bgcolor: alpha('#fffdf8', 0.98) }}>
            <CardContent sx={{ p: { xs: 2.5, md: 3 } }}>
              <Grid container spacing={2.5}>
                <Grid item xs={12} md={5}>
                  <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3, height: '100%', borderColor: alpha(primaryColor, 0.14), bgcolor: alpha(primaryColor, 0.03) }}>
                    <Typography variant="h5" fontWeight={800}>Create the first exam period</Typography>
                    <Typography color="text.secondary" sx={{ mt: 1 }}>Once created, add session windows, seating rules, sync papers, and generate the draft.</Typography>
                    <Stack direction="row" spacing={1.25} sx={{ mt: 2.5 }} flexWrap="wrap">
                      <Button variant="contained" startIcon={<AddIcon />} onClick={() => setPeriodDialogOpen(true)} disabled={!canConfigurePeriod}>New Exam Period</Button>
                      <Button variant="outlined" startIcon={<SeatingIcon />} onClick={() => setProfileDialogOpen(true)} disabled={!canConfigurePeriod}>Seating Profiles</Button>
                    </Stack>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={7}>
                  <Grid container spacing={1.25}>
                    {['Create the exam period with dates and spacing rules', 'Add session windows the generator may use', 'Set seating profiles and confirm venue capacity', 'Select and sync the papers for this cycle', 'Generate the draft and review the placements'].map((step, i) => (
                      <Grid item xs={12} sm={6} key={step}>
                        <Paper variant="outlined" sx={{ p: 1.75, borderRadius: 2.5, height: '100%', display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                          <Box sx={{ width: 26, height: 26, borderRadius: '50%', bgcolor: alpha(primaryColor, 0.12), color: primaryColor, display: 'grid', placeItems: 'center', flexShrink: 0, fontWeight: 800, fontSize: '0.78rem' }}>{i + 1}</Box>
                          <Typography variant="body2" fontWeight={600}>{step}</Typography>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        ) : (
          <Grid container spacing={3}>
            <Grid item xs={12} lg={3.3}>
              <Stack spacing={3}>
                <Paper
                  sx={{
                    borderRadius: 3,
                    border: '1px solid',
                    borderColor: alpha(primaryColor, 0.1),
                    bgcolor: alpha('#fffdf8', 0.98),
                    boxShadow: `0 8px 24px ${alpha(primaryColor, 0.07)}`,
                  }}
                >
                  <Box sx={{ p: 2.5, borderBottom: '1px solid', borderColor: alpha(primaryColor, 0.08), background: `linear-gradient(135deg, ${alpha(primaryColor, 0.06)} 0%, transparent 100%)` }}>
                    <Typography variant="h6" fontWeight={800}>Exam Periods</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Choose the cycle you want to configure and publish.
                    </Typography>
                  </Box>
                  {loading ? (
                    <Box sx={{ p: 3 }}>
                      <Typography color="text.secondary">Loading exam periods...</Typography>
                    </Box>
                  ) : periods.length === 0 ? (
                    <Box sx={{ p: 3 }}>
                      <Typography fontWeight={700}>No exam periods yet</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        Create a period to begin loading papers, venues, and session windows.
                      </Typography>
                    </Box>
                  ) : (
                    <List disablePadding>
                      {periods.map((period) => (
                        <Box
                          key={period.id}
                          sx={{
                            display: 'flex',
                            alignItems: 'stretch',
                            borderLeft: period.id === selectedPeriodId ? `4px solid ${primaryColor}` : '4px solid transparent',
                            bgcolor: period.id === selectedPeriodId ? alpha(primaryColor, 0.06) : alpha('#ffffff', 0.94),
                          }}
                        >
                          <ListItemButton
                            selected={period.id === selectedPeriodId}
                            onClick={() => void selectPeriod(period.id)}
                            sx={{
                              py: 1.8,
                              alignItems: 'flex-start',
                              pr: 1,
                            }}
                          >
                            <ListItemText
                              primary={(
                                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                                  <Typography fontWeight={800}>{period.name}</Typography>
                                  {period.is_published && <Chip size="small" color="success" label="Published" />}
                                  {period.is_locked && <Chip size="small" color="warning" label="Locked" />}
                                </Stack>
                              )}
                              secondary={(
                                <Box sx={{ mt: 0.75 }}>
                                  <Typography variant="body2" color="text.secondary">
                                    {period.semester} {period.year}
                                  </Typography>
                                  <Typography variant="caption" color="text.secondary">
                                    {formatDateLabel(period.start_date)} to {formatDateLabel(period.end_date)}
                                  </Typography>
                                </Box>
                              )}
                            />
                          </ListItemButton>
                          {canConfigurePeriod && (
                            <Tooltip title="Delete period">
                              <IconButton
                                size="small"
                                onClick={() => void handleDeletePeriod(period)}
                                sx={{
                                  alignSelf: 'center',
                                  mr: 1,
                                  color: 'text.secondary',
                                  '&:hover': {
                                    color: theme.palette.error.main,
                                    bgcolor: alpha(theme.palette.error.main, 0.08),
                                  },
                                }}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Box>
                      ))}
                    </List>
                  )}
                  {canConfigurePeriod && (
                    <Box sx={{ p: 2, borderTop: '1px solid', borderColor: alpha(primaryColor, 0.08) }}>
                      <Button fullWidth variant="contained" startIcon={<AddIcon />} onClick={() => setPeriodDialogOpen(true)}>
                        New Exam Period
                      </Button>
                    </Box>
                  )}
                </Paper>
              </Stack>
            </Grid>

            <Grid item xs={12} lg={8.7}>
              {!selectedPeriod ? (
                <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: alpha(primaryColor, 0.1), bgcolor: alpha('#fffdf8', 0.98) }}>
                  <CardContent sx={{ p: { xs: 2.5, md: 3 } }}>
                    <Typography variant="h5" fontWeight={800}>Select an exam period</Typography>
                    <Typography color="text.secondary" sx={{ mt: 1 }}>Pick a period from the left to continue with setup, paper selection, generation, and final review.</Typography>
                  </CardContent>
                </Card>
              ) : (
                <Stack spacing={3}>
                  {/* Quick-action strip */}
                  <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 3, bgcolor: alpha('#fff', 0.85) }}>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center" justifyContent="space-between" flexWrap="wrap">
                      <Stack direction="row" spacing={1} flexWrap="wrap">
                        <Chip size="small" icon={<WindowIcon />} label={`${selectedWindows.length} Windows`} variant="outlined" />
                        <Chip size="small" icon={<CatalogIcon />} label={`${selectedPapers.length} Papers`} variant="outlined" />
                        <Chip size="small" icon={<RoomIcon />} label={`${roomUtilizationSummary.effectiveCapacity} Seats`} variant="outlined" />
                        <Chip size="small" icon={selectedSlots.length > 0 ? <HealthyIcon /> : <DiagnosticsIcon />} label={`${selectedSlots.length} Slots`} color={draftHealthTone === 'success' ? 'success' : 'default'} variant="outlined" />
                      </Stack>
                      <Stack direction="row" spacing={1} flexWrap="wrap" justifyContent="flex-end">
                        <Button size="small" variant="outlined" startIcon={<WindowIcon />} onClick={() => setWindowDialogOpen(true)} disabled={selectedPeriod.is_locked || !canConfigurePeriod}>Window</Button>
                        <Button size="small" variant="outlined" startIcon={<SeatingIcon />} onClick={() => setProfileDialogOpen(true)} disabled={!canConfigurePeriod}>Profile</Button>
                        <Button size="small" variant="outlined" startIcon={<ExamIcon />} onClick={() => setPaperDialogOpen(true)} disabled={selectedPeriod.is_locked || !canConfigurePeriod}>Manual Paper</Button>
                      </Stack>
                    </Stack>
                  </Paper>


                  <Grid container spacing={3}>
                    <Grid item xs={12} xl={4.1} sx={{ display: activeTab !== 'overview' ? 'none' : undefined }}>
                      <Stack spacing={3}>
                        <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: alpha(primaryColor, 0.1), bgcolor: alpha('#fffdf8', 0.98) }}>
                          <CardContent>
                            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 2.25 }}>
                              <Box>
                                <Typography variant="h6" fontWeight={800}>Scheduling Rules</Typography>
                                <Typography variant="body2" color="text.secondary">
                                  The core inputs the generator needs before it can build a draft.
                                </Typography>
                              </Box>
                              <WindowIcon color="action" />
                            </Stack>

                            <Stack spacing={1.25}>
                              <Paper variant="outlined" sx={{ p: 1.6, borderRadius: 3, bgcolor: '#fff' }}>
                                <Typography variant="caption" color="text.secondary">Exam dates</Typography>
                                <Typography fontWeight={800} sx={{ mt: 0.35 }}>
                                  {formatDateLabel(selectedPeriod.start_date)} to {formatDateLabel(selectedPeriod.end_date)}
                                </Typography>
                              </Paper>
                              <Paper variant="outlined" sx={{ p: 1.6, borderRadius: 3, bgcolor: '#fff' }}>
                                <Typography variant="caption" color="text.secondary">Spacing parameters</Typography>
                                <Grid container spacing={1} sx={{ mt: 0.4 }}>
                                  {[
                                    { label: 'Preferred max/day', value: selectedConstraints?.preferred_max_papers_per_day ?? 'Not set' },
                                    { label: 'Hard cap/day', value: selectedConstraints?.hard_max_papers_per_day ?? 'Not set' },
                                    { label: 'Minimum gap', value: `${selectedConstraints?.min_gap_hours ?? 'Not set'} hours` },
                                    { label: 'Same-day fallback', value: selectedConstraints?.allow_same_day_multiple_papers ? 'Allowed' : 'Not allowed' },
                                  ].map((item) => (
                                    <Grid item xs={12} sm={6} key={item.label}>
                                      <Box sx={{ px: 1.1, py: 0.95, borderRadius: 2, bgcolor: alpha(primaryColor, 0.035) }}>
                                        <Typography variant="caption" color="text.secondary">{item.label}</Typography>
                                        <Typography variant="body2" fontWeight={700}>{item.value}</Typography>
                                      </Box>
                                    </Grid>
                                  ))}
                                </Grid>
                              </Paper>
                              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ pt: 0.5 }}>
                                <Typography fontWeight={800}>Session windows</Typography>
                                <Button size="small" onClick={() => setWindowDialogOpen(true)} disabled={selectedPeriod.is_locked || !canConfigurePeriod}>
                                  Add
                                </Button>
                              </Stack>
                              {selectedWindows.length === 0 ? (
                                <Paper variant="outlined" sx={{ p: 1.75, borderRadius: 3, bgcolor: '#fff' }}>
                                  <Typography fontWeight={700}>No session windows configured yet.</Typography>
                                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.6 }}>
                                    Add a morning and afternoon window so papers can be placed into valid sessions.
                                  </Typography>
                                </Paper>
                              ) : (
                                selectedWindows.map((window) => (
                                  <Paper
                                    key={window.id}
                                    variant="outlined"
                                    sx={{
                                      p: 1.4,
                                      borderRadius: 3,
                                      borderColor: alpha(primaryColor, 0.14),
                                      bgcolor: '#fff',
                                    }}
                                  >
                                    <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="center">
                                      <Box>
                                        <Typography fontWeight={800}>{window.name}</Typography>
                                        <Typography variant="body2" color="text.secondary">
                                          {formatTimeLabel(window.start_time)} - {formatTimeLabel(window.end_time)}
                                        </Typography>
                                      </Box>
                                      <Chip
                                        size="small"
                                        label={window.allow_weekends ? 'Weekends allowed' : 'Weekdays only'}
                                        variant="outlined"
                                      />
                                    </Stack>
                                  </Paper>
                                ))
                              )}
                            </Stack>
                          </CardContent>
                        </Card>

                        <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: alpha(primaryColor, 0.1), bgcolor: alpha('#fffdf8', 0.98) }}>
                          <CardContent>
                            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 2 }}>
                              <Box>
                                <Typography variant="h6" fontWeight={800}>Seating And Capacity</Typography>
                                <Typography variant="body2" color="text.secondary">
                                  Capacity rules and venue readiness for this cycle.
                                </Typography>
                              </Box>
                              <RoomIcon color="action" />
                            </Stack>

                            <Stack spacing={1.5}>
                              <Paper
                                variant="outlined"
                                sx={{
                                  p: 1.75,
                                  borderRadius: 3,
                                  bgcolor: '#fff',
                                  borderColor: alpha(primaryColor, 0.14),
                                }}
                              >
                                <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="flex-start">
                                  <Box>
                                    <Typography fontWeight={800}>Seat demand</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                      {selectedCandidateCount} students selected for synchronization
                                    </Typography>
                                  </Box>
                                  <Box sx={{ textAlign: 'right' }}>
                                    <Typography variant="h6" fontWeight={900}>{seatDemandRatio}%</Typography>
                                    <Typography variant="caption" color="text.secondary">capacity used</Typography>
                                  </Box>
                                </Stack>
                                <LinearProgress
                                  variant="determinate"
                                  value={seatDemandRatio}
                                  color={selectedCandidateCount > roomUtilizationSummary.effectiveCapacity ? 'warning' : 'primary'}
                                  sx={{ mt: 1.25, height: 8, borderRadius: 999 }}
                                />
                                <Grid container spacing={1} sx={{ mt: 1.1 }}>
                                  <Grid item xs={6}>
                                    <Box sx={{ px: 1.1, py: 0.9, borderRadius: 2, bgcolor: alpha(primaryColor, 0.035) }}>
                                      <Typography variant="caption" color="text.secondary">Effective seats</Typography>
                                      <Typography variant="body2" fontWeight={700}>{roomUtilizationSummary.effectiveCapacity}</Typography>
                                    </Box>
                                  </Grid>
                                  <Grid item xs={6}>
                                    <Box sx={{ px: 1.1, py: 0.9, borderRadius: 2, bgcolor: alpha(primaryColor, 0.035) }}>
                                      <Typography variant="caption" color="text.secondary">Profile in use</Typography>
                                      <Typography variant="body2" fontWeight={700}>{selectedSyncProfile?.name || 'Default profile'}</Typography>
                                    </Box>
                                  </Grid>
                                </Grid>
                              </Paper>

                              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ pt: 0.25 }}>
                                <Typography fontWeight={800}>Seating profiles</Typography>
                                <Button size="small" onClick={() => setProfileDialogOpen(true)} disabled={!canConfigurePeriod}>
                                  Add
                                </Button>
                              </Stack>

                              <Stack spacing={1.1}>
                                {seatingProfiles.length === 0 ? (
                                  <Paper variant="outlined" sx={{ p: 1.6, borderRadius: 3 }}>
                                    <Typography fontWeight={700}>No seating profiles configured yet.</Typography>
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.6 }}>
                                      Add at least one profile so venue capacity matches real exam spacing rules.
                                    </Typography>
                                  </Paper>
                                ) : (
                                  seatingProfiles.map((profile) => (
                                    <Paper key={profile.id} variant="outlined" sx={{ p: 1.45, borderRadius: 3, bgcolor: '#fff' }}>
                                      <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="flex-start">
                                        <Box sx={{ minWidth: 0 }}>
                                          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                                            <Typography fontWeight={800}>{profile.name}</Typography>
                                            {profile.is_default && <Chip size="small" color="primary" label="Default" />}
                                          </Stack>
                                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>
                                            Capacity factor {profile.capacity_factor}%
                                            {profile.fixed_capacity ? ` | Fixed ${profile.fixed_capacity}` : ''}
                                          </Typography>
                                        </Box>
                                        <Chip size="small" variant="outlined" label={profile.spacing_strategy.replace(/_/g, ' ')} />
                                      </Stack>
                                    </Paper>
                                  ))
                                )}
                              </Stack>

                              <Paper variant="outlined" sx={{ p: 1.6, borderRadius: 3, bgcolor: '#fff' }}>
                                <Grid container spacing={1}>
                                  <Grid item xs={6}>
                                    <Typography variant="caption" color="text.secondary">Active venues</Typography>
                                    <Typography fontWeight={800}>{availableRooms.length}</Typography>
                                  </Grid>
                                  <Grid item xs={6}>
                                    <Typography variant="caption" color="text.secondary">Raw seats</Typography>
                                    <Typography fontWeight={800}>{roomUtilizationSummary.rawCapacity}</Typography>
                                  </Grid>
                                  <Grid item xs={12}>
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>
                                      Current draft occupies {roomUtilizationSummary.usedRooms} of {roomUtilizationSummary.totalRooms} active rooms.
                                    </Typography>
                                  </Grid>
                                </Grid>
                              </Paper>
                            </Stack>
                          </CardContent>
                        </Card>
                      </Stack>
                    </Grid>

                    <Grid item xs={12} xl={activeTab === 'overview' ? 0 : 12} sx={{ display: activeTab === 'overview' ? 'none' : undefined }}>
                      <Stack spacing={3}>
                        <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: alpha(primaryColor, 0.1), bgcolor: alpha('#fffdf8', 0.98), display: activeTab !== 'papers' ? 'none' : undefined }}>
                          <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
                            <Stack
                              direction={{ xs: 'column', lg: 'row' }}
                              justifyContent="space-between"
                              spacing={2}
                              sx={{ mb: 2.5 }}
                            >
                              <Box>
                                <Stack direction="row" spacing={1} alignItems="center">
                                  <CatalogIcon color="action" />
                                  <Typography variant="h6" fontWeight={800}>Paper Selection</Typography>
                                </Stack>
                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 760 }}>
                                  Pull mapped courses, keep only examinable ones, then synchronize the approved paper list into this cycle.
                                </Typography>
                              </Box>
                              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.2}>
                                <Button
                                  variant="outlined"
                                  startIcon={<SyncIcon />}
                                  onClick={() => selectedPeriod && void loadPaperCandidates(selectedPeriod.id)}
                                  disabled={candidateLoading}
                                >
                                  Refresh Pull
                                </Button>
                                <Button
                                  variant="contained"
                                  startIcon={<SyncIcon />}
                                  onClick={() => void handleSyncPapers()}
                                  disabled={!canMarkPapers || selectedPeriod.is_locked || busyAction === 'sync-papers' || candidateLoading}
                                >
                                  {busyAction === 'sync-papers' ? 'Synchronizing...' : 'Sync Selected Papers'}
                                </Button>
                              </Stack>
                            </Stack>

                            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} alignItems={{ xs: 'stretch', md: 'center' }} sx={{ mb: 2 }}>
                              <Chip label={`${selectedCourseIds.length} selected`} color="primary" variant="outlined" />
                              <Chip
                                label={`${selectedCandidateCount} students`}
                                color={selectedCandidateCount > roomUtilizationSummary.effectiveCapacity ? 'warning' : 'success'}
                                variant="outlined"
                              />
                              <Chip label={`${alreadyIncludedCount} already synced`} variant="outlined" />
                              <Chip label={`${manageableCandidates.length} manageable by you`} variant="outlined" />
                            </Stack>

                            <Paper
                              variant="outlined"
                              sx={{
                                p: 1.5,
                                mb: 2,
                                borderRadius: 3,
                                bgcolor: '#fff',
                                borderColor: alpha(primaryColor, 0.08),
                              }}
                            >
                              <Grid container spacing={1.5} alignItems="center">
                              <Grid item xs={12} md={4.1}>
                                <TextField
                                  fullWidth
                                  label="Search course, group, or year"
                                  value={candidateSearch}
                                  onChange={(event) => setCandidateSearch(event.target.value)}
                                  InputProps={{ startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} /> }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={6} md={2.1}>
                                <FormControl fullWidth>
                                  <InputLabel id="candidate-filter-label">View</InputLabel>
                                  <Select
                                    labelId="candidate-filter-label"
                                    label="View"
                                    value={candidateFilter}
                                    onChange={(event) => setCandidateFilter(event.target.value as typeof candidateFilter)}
                                  >
                                    <MenuItem value="all">All mapped</MenuItem>
                                    <MenuItem value="selected">Selected only</MenuItem>
                                    <MenuItem value="included">Already included</MenuItem>
                                    <MenuItem value="notIncluded">Not yet included</MenuItem>
                                  </Select>
                                </FormControl>
                              </Grid>
                              <Grid item xs={12} sm={6} md={1.7}>
                                <TextField
                                  fullWidth
                                  label="Duration"
                                  type="number"
                                  value={syncDefaults.default_duration_minutes}
                                  onChange={(event) => setSyncDefaults((current) => ({
                                    ...current,
                                    default_duration_minutes: Number(event.target.value),
                                  }))}
                                />
                              </Grid>
                              <Grid item xs={12} sm={6} md={1.6}>
                                <TextField
                                  fullWidth
                                  label="Max rooms"
                                  type="number"
                                  value={syncDefaults.default_max_rooms}
                                  onChange={(event) => setSyncDefaults((current) => ({
                                    ...current,
                                    default_max_rooms: Number(event.target.value),
                                  }))}
                                />
                              </Grid>
                              <Grid item xs={12} sm={6} md={2.5}>
                                <FormControl fullWidth>
                                  <InputLabel id="sync-profile-label">Seating profile</InputLabel>
                                  <Select
                                    labelId="sync-profile-label"
                                    label="Seating profile"
                                    value={syncDefaults.preferred_seating_profile_id}
                                    onChange={(event) => setSyncDefaults((current) => ({
                                      ...current,
                                      preferred_seating_profile_id: event.target.value,
                                    }))}
                                  >
                                    <MenuItem value="">Use paper/default profile</MenuItem>
                                    {seatingProfiles.map((profile) => (
                                      <MenuItem key={profile.id} value={profile.id}>
                                        {profile.name}
                                      </MenuItem>
                                    ))}
                                  </Select>
                                </FormControl>
                              </Grid>
                              </Grid>
                            </Paper>

                            <Stack
                              direction={{ xs: 'column', lg: 'row' }}
                              spacing={1.25}
                              alignItems={{ xs: 'stretch', lg: 'center' }}
                              justifyContent="space-between"
                              sx={{ mb: 1.75 }}
                            >
                              <FormControlLabel
                                control={(
                                  <Switch
                                    checked={syncDefaults.allow_custom_window}
                                    onChange={(event) => setSyncDefaults((current) => ({
                                      ...current,
                                      allow_custom_window: event.target.checked,
                                    }))}
                                  />
                                )}
                                label="Allow custom session window overrides on synced papers"
                              />

                              <Stack direction="row" spacing={1} flexWrap="wrap">
                                <Button
                                  size="small"
                                  variant="text"
                                  onClick={() => setSelectedCourseIds(manageableCandidateIds)}
                                >
                                  Select all
                                </Button>
                                <Button
                                  size="small"
                                  variant="text"
                                  onClick={() => setSelectedCourseIds(
                                    paperCandidates
                                      .filter((candidate) => candidate.already_included && candidate.can_manage)
                                      .map((candidate) => candidate.course_id),
                                  )}
                                >
                                  Included only
                                </Button>
                                <Button
                                  size="small"
                                  variant="text"
                                  startIcon={<ClearIcon />}
                                  onClick={() => setSelectedCourseIds([])}
                                >
                                  Clear
                                </Button>
                              </Stack>
                            </Stack>

                            {candidateLoading ? (
                              <Typography color="text.secondary">Loading mapped course audiences...</Typography>
                            ) : filteredCandidates.length === 0 ? (
                              <Alert severity="info">
                                No mapped courses matched this filter. Check course enrolment mapping if you expected papers here.
                              </Alert>
                            ) : (
                              <Box sx={{ overflowX: 'auto', borderRadius: 3, border: '1px solid', borderColor: alpha(primaryColor, 0.08) }}>
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell padding="checkbox" />
                                      <TableCell>Course</TableCell>
                                      <TableCell>Audience</TableCell>
                                      <TableCell>Exam Setup</TableCell>
                                      <TableCell>Status</TableCell>
                                      <TableCell align="right">Candidates</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {filteredCandidates.map((candidate) => (
                                      <TableRow key={candidate.course_id} hover selected={selectedCourseIds.includes(candidate.course_id)}>
                                        <TableCell padding="checkbox">
                                          <Checkbox
                                            checked={selectedCourseIds.includes(candidate.course_id)}
                                            onChange={() => toggleCourseSelection(candidate.course_id)}
                                            disabled={selectedPeriod.is_locked || !candidate.can_manage}
                                          />
                                        </TableCell>
                                        <TableCell>
                                          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                                            <Typography fontWeight={800}>{candidate.course_code}</Typography>
                                            <Chip
                                              size="small"
                                              label={candidate.ownership_kind === 'owner' ? 'Your department' : 'Shared view'}
                                              color={candidate.ownership_kind === 'owner' ? 'primary' : 'default'}
                                              variant="outlined"
                                            />
                                          </Stack>
                                          <Typography variant="body2">{candidate.course_name}</Typography>
                                          <Typography variant="caption" color="text.secondary">
                                            {normalizeLevelLabel(candidate.course_level)}
                                            {candidate.department_name ? ` | ${candidate.department_name}` : ''}
                                          </Typography>
                                        </TableCell>
                                        <TableCell>
                                          <Typography variant="body2">
                                            {candidate.groups.map((group) => group.name).join(', ')}
                                          </Typography>
                                          <Typography variant="caption" color="text.secondary">
                                            {candidate.groups.length} group(s)
                                          </Typography>
                                        </TableCell>
                                        <TableCell>
                                          <Typography variant="body2">
                                            {(candidate.preferred_room_type || 'any').replace(/_/g, ' ')}
                                          </Typography>
                                          <Typography variant="caption" color="text.secondary">
                                            {selectedSyncProfile ? `${selectedSyncProfile.name} seating` : 'Default seating'}
                                          </Typography>
                                        </TableCell>
                                        <TableCell>
                                          {candidate.already_included ? (
                                            <Stack spacing={0.25}>
                                              <Chip size="small" color="success" label="Included" sx={{ width: 'fit-content' }} />
                                              <Typography variant="caption" color="text.secondary">
                                                {candidate.existing_paper_code || candidate.course_code}
                                                {candidate.existing_duration_minutes ? ` | ${candidate.existing_duration_minutes} mins` : ''}
                                              </Typography>
                                            </Stack>
                                          ) : (
                                            <Chip size="small" variant="outlined" label="Not yet included" />
                                          )}
                                          {!candidate.can_manage && (
                                            <Typography variant="caption" color="text.secondary" display="block">
                                              View only
                                            </Typography>
                                          )}
                                        </TableCell>
                                        <TableCell align="right">
                                          <Typography fontWeight={800}>{candidate.candidate_count}</Typography>
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </Box>
                            )}
                          </CardContent>
                        </Card>

                        <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: alpha(primaryColor, 0.1), bgcolor: alpha('#fffdf8', 0.98), display: activeTab !== 'timetable' ? 'none' : undefined }}>
                          <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
                            <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={1.5} sx={{ mb: 2 }}>
                              <Box>
                                <Typography variant="h6" fontWeight={800}>Generate And Review</Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                  Generate the draft, then review how papers were placed across dates, sessions, and rooms.
                                </Typography>
                              </Box>
                              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} flexWrap="wrap">
                                <Button
                                  variant="outlined"
                                  color="warning"
                                  startIcon={<ClearDraftIcon />}
                                  onClick={() => void handleClearDraft()}
                                  disabled={!canGenerateOrPublish || busyAction === 'clear-draft' || selectedPeriod.is_locked || selectedPeriod.is_published || selectedSlots.length === 0}
                                >
                                  {busyAction === 'clear-draft' ? 'Clearing...' : 'Clear Draft'}
                                </Button>
                                <Button
                                  variant="contained"
                                  startIcon={<GenerateIcon />}
                                  onClick={() => void handleGenerate()}
                                  disabled={!canGenerateOrPublish || busyAction === 'generate' || selectedPeriod.is_locked || selectedPapers.length === 0 || selectedWindows.length === 0}
                                >
                                  {busyAction === 'generate' ? 'Generating...' : 'Generate Draft'}
                                </Button>
                                <Button
                                  variant="contained"
                                  color="success"
                                  startIcon={<PublishIcon />}
                                  onClick={() => void handlePublish()}
                                  disabled={!canGenerateOrPublish || busyAction === 'publish' || selectedSlots.length === 0 || selectedPeriod.is_published}
                                >
                                  {busyAction === 'publish' ? 'Publishing...' : 'Publish'}
                                </Button>
                              </Stack>
                            </Stack>

                            <Paper
                              variant="outlined"
                              sx={{
                                p: { xs: 1.8, md: 2.1 },
                                mb: 2,
                                borderRadius: 3.5,
                                bgcolor:
                                  draftHealthTone === 'success'
                                    ? alpha('#eff9f2', 0.92)
                                    : draftHealthTone === 'warning'
                                      ? alpha('#fff4e5', 0.92)
                                      : alpha(primaryColor, 0.045),
                                borderColor:
                                  draftHealthTone === 'success'
                                    ? alpha(theme.palette.success.main, 0.18)
                                    : draftHealthTone === 'warning'
                                      ? alpha(theme.palette.warning.main, 0.2)
                                      : alpha(primaryColor, 0.12),
                              }}
                            >
                              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between">
                                <Stack direction="row" spacing={1.4} alignItems="flex-start">
                                  <Box
                                    sx={{
                                      width: 44,
                                      height: 44,
                                      borderRadius: 2.5,
                                      display: 'grid',
                                      placeItems: 'center',
                                      bgcolor:
                                        draftHealthTone === 'success'
                                          ? alpha(theme.palette.success.main, 0.12)
                                          : draftHealthTone === 'warning'
                                            ? alpha(theme.palette.warning.main, 0.14)
                                            : alpha(primaryColor, 0.12),
                                      color:
                                        draftHealthTone === 'success'
                                          ? theme.palette.success.dark
                                          : draftHealthTone === 'warning'
                                            ? theme.palette.warning.dark
                                            : primaryColor,
                                    }}
                                  >
                                    {draftHealthTone === 'success' ? <HealthyIcon /> : draftHealthTone === 'warning' ? <WarningIcon /> : <DiagnosticsIcon />}
                                  </Box>
                                  <Box>
                                    <Typography variant="overline" sx={{ letterSpacing: '0.12em', color: 'text.secondary', fontWeight: 700 }}>
                                      Draft Quality
                                    </Typography>
                                    <Typography variant="h6" fontWeight={800} sx={{ mt: 0.3 }}>
                                      {draftHealthLabel}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.65, maxWidth: 780 }}>
                                      {generationMetadata?.strategy || 'The generator prioritizes constrained papers first, fits the smallest viable room bundle, and highlights spacing or load pressure for review.'}
                                    </Typography>
                                  </Box>
                                </Stack>
                                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} flexWrap="wrap" alignItems={{ xs: 'stretch', sm: 'center' }}>
                                  <Chip icon={<GenerateIcon />} label={`${selectedSlots.length} placed`} color={selectedSlots.length > 0 ? 'primary' : 'default'} variant="outlined" />
                                  <Chip icon={<FlagIcon />} label={`${scheduledFlags.length} flagged`} color={scheduledFlags.length > 0 ? 'warning' : 'success'} variant="outlined" />
                                  <Chip icon={<WarningIcon />} label={`${unscheduledPapers.length} unscheduled`} color={unscheduledPapers.length > 0 ? 'warning' : 'success'} variant="outlined" />
                                </Stack>
                              </Stack>
                            </Paper>

                            <Grid container spacing={1.25} sx={{ mb: 2 }}>
                              {[
                                { label: 'Draft slots', value: selectedSlots.length, note: 'Placed exam papers' },
                                { label: 'Allocated seats', value: allocatedDraftSeats, note: 'Seats committed in the draft' },
                                { label: 'Avg rooms / slot', value: diagnosticsSummary?.average_rooms_per_slot ?? 0, note: 'How dense the room bundles are' },
                              ].map((item) => (
                                <Grid item xs={12} sm={4} key={item.label}>
                                  <Paper variant="outlined" sx={{ p: 1.45, borderRadius: 2.8, bgcolor: '#fff' }}>
                                    <Typography variant="caption" color="text.secondary">{item.label}</Typography>
                                    <Typography fontWeight={800} sx={{ mt: 0.35 }}>{item.value}</Typography>
                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.35 }}>
                                      {item.note}
                                    </Typography>
                                  </Paper>
                                </Grid>
                              ))}
                            </Grid>

                            <Grid container spacing={1.25} sx={{ mb: 2.4 }}>
                              {draftDiagnosticsCards.map((item) => (
                                <Grid item xs={12} md={4} key={item.label}>
                                  <Paper
                                    variant="outlined"
                                    sx={{
                                      p: 1.55,
                                      borderRadius: 3,
                                      bgcolor: '#fff',
                                      borderColor:
                                        item.tone === 'warning'
                                          ? alpha(theme.palette.warning.main, 0.22)
                                          : alpha(theme.palette.success.main, 0.18),
                                    }}
                                  >
                                    <Stack direction="row" justifyContent="space-between" spacing={1}>
                                      <Box>
                                        <Typography variant="caption" color="text.secondary">{item.label}</Typography>
                                        <Typography variant="h6" fontWeight={800} sx={{ mt: 0.2 }}>{item.value}</Typography>
                                      </Box>
                                      {item.tone === 'warning' ? <WarningIcon color="warning" /> : <HealthyIcon color="success" />}
                                    </Stack>
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.7 }}>
                                      {item.note}
                                    </Typography>
                                  </Paper>
                                </Grid>
                              ))}
                            </Grid>

                            {selectedPeriod.is_published ? (
                              <Alert severity="success" sx={{ mb: 2 }}>
                                This exam period is published and locked. The current draft is now the live operating timetable.
                              </Alert>
                            ) : (
                              <Alert severity="info" sx={{ mb: 2 }}>
                                This period is still in draft mode. You can still adjust session windows, seating rules, and included papers.
                              </Alert>
                            )}

                            {(scheduledFlags.length > 0 || unscheduledPapers.length > 0 || diagnosticsSummary?.unscheduled_reasons) && (
                              <Grid container spacing={1.5} sx={{ mb: 2.4 }}>
                                <Grid item xs={12} lg={7}>
                                  <Paper
                                    variant="outlined"
                                    sx={{
                                      p: 1.7,
                                      borderRadius: 3,
                                      bgcolor: '#fff',
                                      borderColor: alpha(primaryColor, 0.08),
                                      height: '100%',
                                    }}
                                  >
                                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.4 }}>
                                      <FlagIcon color="action" />
                                      <Typography fontWeight={800}>Placement Review Notes</Typography>
                                    </Stack>
                                    {scheduledFlags.length === 0 ? (
                                      <Typography variant="body2" color="text.secondary">
                                        No draft placements are currently flagged for review.
                                      </Typography>
                                    ) : (
                                      <Stack spacing={1}>
                                        {scheduledFlags.slice(0, 6).map((flag) => (
                                          <Paper
                                            key={`${flag.slot_id}-${flag.paper_id}`}
                                            variant="outlined"
                                            sx={{
                                              p: 1.25,
                                              borderRadius: 2.5,
                                              bgcolor:
                                                flag.severity === 'warning'
                                                  ? alpha('#fff7ea', 0.95)
                                                  : alpha(primaryColor, 0.03),
                                              borderColor:
                                                flag.severity === 'warning'
                                                  ? alpha(theme.palette.warning.main, 0.2)
                                                  : alpha(primaryColor, 0.08),
                                            }}
                                          >
                                            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between">
                                              <Box>
                                                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                                                  <Typography fontWeight={800}>{flag.paper_code}</Typography>
                                                  <Chip
                                                    size="small"
                                                    label={flag.severity === 'warning' ? 'Review' : 'Info'}
                                                    color={flag.severity === 'warning' ? 'warning' : 'default'}
                                                    variant="outlined"
                                                  />
                                                </Stack>
                                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.45 }}>
                                                  {flag.summary}
                                                </Typography>
                                              </Box>
                                              <Stack direction="row" spacing={0.75} flexWrap="wrap">
                                                {flag.flags.map((flagCode) => (
                                                  <Chip
                                                    key={flagCode}
                                                    size="small"
                                                    label={startCaseFlag(flagCode)}
                                                    variant="outlined"
                                                  />
                                                ))}
                                              </Stack>
                                            </Stack>
                                          </Paper>
                                        ))}
                                      </Stack>
                                    )}
                                  </Paper>
                                </Grid>
                                <Grid item xs={12} lg={5}>
                                  <Paper
                                    variant="outlined"
                                    sx={{
                                      p: 1.7,
                                      borderRadius: 3,
                                      bgcolor: '#fff',
                                      borderColor: alpha(primaryColor, 0.08),
                                      height: '100%',
                                    }}
                                  >
                                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.4 }}>
                                      <DiagnosticsIcon color="action" />
                                      <Typography fontWeight={800}>Constraint Diagnostics</Typography>
                                    </Stack>
                                    <Stack spacing={1}>
                                      {Object.entries(diagnosticsSummary?.unscheduled_reasons || {}).length === 0 ? (
                                        <Typography variant="body2" color="text.secondary">
                                          No dominant blocking pattern has been recorded for this draft yet.
                                        </Typography>
                                      ) : (
                                        Object.entries(diagnosticsSummary?.unscheduled_reasons || {}).map(([reason, count]) => (
                                          <Box
                                            key={reason}
                                            sx={{
                                              px: 1.2,
                                              py: 1,
                                              borderRadius: 2.5,
                                              bgcolor: alpha(primaryColor, 0.035),
                                            }}
                                          >
                                            <Stack direction="row" justifyContent="space-between" spacing={1}>
                                              <Typography variant="body2" fontWeight={700}>{formatDiagnosticReason(reason)}</Typography>
                                              <Chip size="small" label={count} variant="outlined" />
                                            </Stack>
                                          </Box>
                                        ))
                                      )}
                                    </Stack>
                                  </Paper>
                                </Grid>
                              </Grid>
                            )}

                            {unscheduledPapers.length > 0 && (
                              <Paper
                                variant="outlined"
                                sx={{
                                  p: 1.7,
                                  mb: 2.2,
                                  borderRadius: 3,
                                  bgcolor: alpha('#fff6ea', 0.94),
                                  borderColor: alpha(theme.palette.warning.main, 0.18),
                                }}
                              >
                                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.35 }}>
                                  <WarningIcon color="warning" />
                                  <Typography fontWeight={800}>Unscheduled Papers</Typography>
                                </Stack>
                                <Grid container spacing={1.2}>
                                  {unscheduledPapers.map((paper) => (
                                    <Grid item xs={12} md={6} key={paper.paper_id}>
                                      <Paper variant="outlined" sx={{ p: 1.3, borderRadius: 2.5, bgcolor: '#fff' }}>
                                        <Stack direction="row" justifyContent="space-between" spacing={1}>
                                          <Box>
                                            <Typography fontWeight={800}>{paper.paper_code}</Typography>
                                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.35 }}>
                                              {paper.reason}
                                            </Typography>
                                          </Box>
                                          <Chip size="small" color="warning" label={`${paper.candidate_count ?? 0} seats`} />
                                        </Stack>
                                        <Stack direction="row" spacing={0.75} flexWrap="wrap" sx={{ mt: 1 }}>
                                          {Object.entries(paper.diagnostics || {}).slice(0, 3).map(([reason, count]) => (
                                            <Chip
                                              key={reason}
                                              size="small"
                                              variant="outlined"
                                              label={`${formatDiagnosticReason(reason)} (${count})`}
                                            />
                                          ))}
                                        </Stack>
                                      </Paper>
                                    </Grid>
                                  ))}
                                </Grid>
                              </Paper>
                            )}

                            {selectedSlots.length === 0 ? (
                              <Paper
                                variant="outlined"
                                sx={{
                                  p: 2,
                                  borderRadius: 3,
                                  bgcolor: alpha(primaryColor, 0.02),
                                  borderColor: alpha(primaryColor, 0.1),
                                }}
                              >
                                <Typography fontWeight={700}>No exam slots generated yet.</Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                  Once session windows and papers are ready, generate a draft to review room allocations here.
                                </Typography>
                              </Paper>
                            ) : (
                              <Box sx={{ overflowX: 'auto', borderRadius: 3, border: '1px solid', borderColor: alpha(primaryColor, 0.08) }}>
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell>Date</TableCell>
                                      <TableCell>Session</TableCell>
                                      <TableCell>Paper</TableCell>
                                      <TableCell>Groups</TableCell>
                                      <TableCell>Rooms</TableCell>
                                      <TableCell align="right">Allocated Seats</TableCell>
                                      <TableCell>Review</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {selectedSlots
                                      .slice()
                                      .sort((left, right) => `${left.exam_date}${left.start_time}`.localeCompare(`${right.exam_date}${right.start_time}`))
                                      .map((slot) => (
                                        <TableRow key={slot.id} hover>
                                          <TableCell>{formatDateLabel(slot.exam_date)}</TableCell>
                                          <TableCell>
                                            <Typography fontWeight={800}>{slot.session_window?.name || 'Session'}</Typography>
                                            <Typography variant="caption" color="text.secondary">
                                              {formatTimeLabel(slot.start_time)} - {formatTimeLabel(slot.end_time)}
                                            </Typography>
                                          </TableCell>
                                          <TableCell>
                                            <Typography fontWeight={800}>{slot.paper?.paper_code || `Paper #${slot.exam_paper_id}`}</Typography>
                                            <Typography variant="caption" color="text.secondary">
                                              {slot.paper?.paper_name || 'Unnamed paper'}
                                            </Typography>
                                          </TableCell>
                                          <TableCell>
                                            {(slot.paper?.group_ids || []).map((groupId) => groupLookup.get(groupId)?.name || `Group ${groupId}`).join(', ')}
                                          </TableCell>
                                          <TableCell>
                                            <Stack spacing={0.4}>
                                              {slot.room_allocations.map((allocation) => (
                                                <Typography key={allocation.id} variant="caption">
                                                  {(allocation.room?.name || `Room ${allocation.room_id}`)} | {allocation.allocated_capacity} seats
                                                </Typography>
                                              ))}
                                            </Stack>
                                          </TableCell>
                                          <TableCell align="right">{slot.total_allocated_capacity ?? 0}</TableCell>
                                          <TableCell>
                                            <Stack spacing={0.7} alignItems="flex-start">
                                              <Chip
                                                size="small"
                                                label={slot.status === 'published' ? 'Published' : 'Draft'}
                                                color={slot.status === 'published' ? 'success' : 'default'}
                                                variant={slot.status === 'published' ? 'filled' : 'outlined'}
                                              />
                                              {slot.notes ? (
                                                <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 240 }}>
                                                  {slot.notes}
                                                </Typography>
                                              ) : (
                                                <Typography variant="caption" color="text.secondary">
                                                  Clean placement
                                                </Typography>
                                              )}
                                            </Stack>
                                          </TableCell>
                                        </TableRow>
                                      ))}
                                  </TableBody>
                                </Table>
                              </Box>
                            )}
                          </CardContent>
                        </Card>
                      </Stack>
                    </Grid>
                   {/* ── Diagnostics Tab ── */}
                   {activeTab === 'diagnostics' && selectedPeriod && (
                    <Grid item xs={12}>
                      <Stack spacing={2.5}>
                        <Grid container spacing={2}>
                          {draftDiagnosticsCards.map((card) => (
                            <Grid item xs={12} sm={4} key={card.label}>
                              <Paper variant="outlined" sx={{ p: 2, borderRadius: 3, textAlign: 'center', borderColor: card.tone === 'warning' ? alpha(theme.palette.warning.main, 0.3) : alpha(theme.palette.success.main, 0.22), bgcolor: card.tone === 'warning' ? alpha('#fff7ea', 0.8) : alpha('#f0faf4', 0.8) }}>
                                <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>{card.label}</Typography>
                                <Typography variant="h3" fontWeight={800} sx={{ mt: 0.5, color: card.tone === 'warning' ? theme.palette.warning.dark : theme.palette.success.dark }}>{card.value}</Typography>
                                <Typography variant="caption" color="text.secondary">{card.note}</Typography>
                              </Paper>
                            </Grid>
                          ))}
                        </Grid>
                        {scheduledFlags.length > 0 && (
                          <Card sx={{ borderRadius: 3, border: '1px solid', borderColor: alpha(theme.palette.warning.main, 0.2) }}>
                            <CardContent>
                              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                                <FlagIcon color="warning" />
                                <Typography variant="h6" fontWeight={800}>Placement Review Notes ({scheduledFlags.length})</Typography>
                              </Stack>
                              <Stack spacing={1}>
                                {scheduledFlags.map((flag) => (
                                  <Paper key={`${flag.slot_id}-${flag.paper_id}`} variant="outlined" sx={{ p: 1.5, borderRadius: 2.5, bgcolor: alpha('#fff7ea', 0.9), borderColor: alpha(theme.palette.warning.main, 0.2) }}>
                                    <Stack direction="row" justifyContent="space-between" spacing={1}>
                                      <Box><Typography fontWeight={800}>{flag.paper_code}</Typography><Typography variant="body2" color="text.secondary">{flag.summary}</Typography></Box>
                                      <Stack direction="row" spacing={0.5} flexWrap="wrap">{flag.flags.map((f) => <Chip key={f} size="small" label={startCaseFlag(f)} variant="outlined" />)}</Stack>
                                    </Stack>
                                  </Paper>
                                ))}
                              </Stack>
                            </CardContent>
                          </Card>
                        )}
                        {unscheduledPapers.length > 0 && (
                          <Card sx={{ borderRadius: 3, border: '1px solid', borderColor: alpha(theme.palette.warning.main, 0.22) }}>
                            <CardContent>
                              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}><WarningIcon color="warning" /><Typography variant="h6" fontWeight={800}>Unscheduled Papers ({unscheduledPapers.length})</Typography></Stack>
                              <Grid container spacing={1.5}>
                                {unscheduledPapers.map((paper) => (
                                  <Grid item xs={12} sm={6} key={paper.paper_id}>
                                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2.5 }}>
                                      <Stack direction="row" justifyContent="space-between">
                                        <Box><Typography fontWeight={800}>{paper.paper_code}</Typography><Typography variant="body2" color="text.secondary">{paper.reason}</Typography></Box>
                                        <Chip size="small" color="warning" label={`${paper.candidate_count ?? 0} seats`} />
                                      </Stack>
                                    </Paper>
                                  </Grid>
                                ))}
                              </Grid>
                            </CardContent>
                          </Card>
                        )}
                        <Card sx={{ borderRadius: 3, border: '1px solid', borderColor: alpha(primaryColor, 0.1) }}>
                          <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}><DiagnosticsIcon color="action" /><Typography variant="h6" fontWeight={800}>Constraint Diagnostics</Typography></Stack>
                            {Object.entries(diagnosticsSummary?.unscheduled_reasons || {}).length === 0 ? (
                              <Alert severity="info">No constraint violations recorded yet. Run generation first.</Alert>
                            ) : (
                              <Stack spacing={1}>
                                {Object.entries(diagnosticsSummary?.unscheduled_reasons || {}).map(([reason, count]) => (
                                  <Box key={reason} sx={{ px: 1.5, py: 1, borderRadius: 2.5, bgcolor: alpha(primaryColor, 0.04) }}>
                                    <Stack direction="row" justifyContent="space-between"><Typography variant="body2" fontWeight={700}>{formatDiagnosticReason(reason)}</Typography><Chip size="small" label={count} variant="outlined" /></Stack>
                                  </Box>
                                ))}
                              </Stack>
                            )}
                          </CardContent>
                        </Card>
                      </Stack>
                    </Grid>
                  )}
                  </Grid>
                </Stack>
              )}
            </Grid>
          </Grid>
        )}
      </Stack>

      <Dialog open={periodDialogOpen} onClose={() => setPeriodDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Create Exam Period</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Name" value={periodForm.name} onChange={(e) => setPeriodForm((current) => ({ ...current, name: e.target.value }))} fullWidth />
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField label="Semester" value={periodForm.semester} onChange={(e) => setPeriodForm((current) => ({ ...current, semester: e.target.value }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField label="Year" type="number" value={periodForm.year} onChange={(e) => setPeriodForm((current) => ({ ...current, year: Number(e.target.value) }))} fullWidth />
              </Grid>
            </Grid>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField label="Start date" type="date" InputLabelProps={{ shrink: true }} value={periodForm.start_date} onChange={(e) => setPeriodForm((current) => ({ ...current, start_date: e.target.value }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField label="End date" type="date" InputLabelProps={{ shrink: true }} value={periodForm.end_date} onChange={(e) => setPeriodForm((current) => ({ ...current, end_date: e.target.value }))} fullWidth />
              </Grid>
            </Grid>
            <Divider />
            <Typography variant="subtitle2" fontWeight={700}>Spacing rules</Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <TextField label="Preferred max/day" type="number" value={periodForm.preferred_max_papers_per_day} onChange={(e) => setPeriodForm((current) => ({ ...current, preferred_max_papers_per_day: Number(e.target.value) }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField label="Hard cap/day" type="number" value={periodForm.hard_max_papers_per_day} onChange={(e) => setPeriodForm((current) => ({ ...current, hard_max_papers_per_day: Number(e.target.value) }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField label="Min gap hours" type="number" value={periodForm.min_gap_hours} onChange={(e) => setPeriodForm((current) => ({ ...current, min_gap_hours: Number(e.target.value) }))} fullWidth />
              </Grid>
            </Grid>
            <FormControlLabel
              control={(
                <Switch
                  checked={periodForm.allow_same_day_multiple_papers}
                  onChange={(e) => setPeriodForm((current) => ({ ...current, allow_same_day_multiple_papers: e.target.checked }))}
                />
              )}
              label="Allow same-day fallback when spacing becomes too tight"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPeriodDialogOpen(false)}>Cancel</Button>
          <Button onClick={() => void handleCreatePeriod()} variant="contained" disabled={!canConfigurePeriod || busyAction === 'create-period'}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={windowDialogOpen} onClose={() => setWindowDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add Session Window</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Window name" value={windowForm.name} onChange={(e) => setWindowForm((current) => ({ ...current, name: e.target.value }))} fullWidth />
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField label="Start time" type="time" InputLabelProps={{ shrink: true }} value={windowForm.start_time.slice(0, 5)} onChange={(e) => setWindowForm((current) => ({ ...current, start_time: `${e.target.value}:00` }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField label="End time" type="time" InputLabelProps={{ shrink: true }} value={windowForm.end_time.slice(0, 5)} onChange={(e) => setWindowForm((current) => ({ ...current, end_time: `${e.target.value}:00` }))} fullWidth />
              </Grid>
            </Grid>
            <TextField label="Display order" type="number" value={windowForm.display_order} onChange={(e) => setWindowForm((current) => ({ ...current, display_order: Number(e.target.value) }))} fullWidth />
            <FormControlLabel
              control={<Switch checked={windowForm.allow_weekends} onChange={(e) => setWindowForm((current) => ({ ...current, allow_weekends: e.target.checked }))} />}
              label="Allow weekends for this session"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWindowDialogOpen(false)}>Cancel</Button>
          <Button onClick={() => void handleCreateWindow()} variant="contained" disabled={!canConfigurePeriod || busyAction === 'create-window'}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={profileDialogOpen} onClose={() => setProfileDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Create Seating Profile</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Profile name" value={profileForm.name} onChange={(e) => setProfileForm((current) => ({ ...current, name: e.target.value }))} fullWidth />
            <TextField label="Description" value={profileForm.description} onChange={(e) => setProfileForm((current) => ({ ...current, description: e.target.value }))} fullWidth multiline minRows={2} />
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField label="Capacity factor (%)" type="number" value={profileForm.capacity_factor} onChange={(e) => setProfileForm((current) => ({ ...current, capacity_factor: Number(e.target.value) }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField label="Fixed capacity override" type="number" value={profileForm.fixed_capacity} onChange={(e) => setProfileForm((current) => ({ ...current, fixed_capacity: e.target.value }))} fullWidth />
              </Grid>
            </Grid>
            <FormControl fullWidth>
              <InputLabel id="spacing-strategy-label">Spacing strategy</InputLabel>
              <Select
                labelId="spacing-strategy-label"
                label="Spacing strategy"
                value={profileForm.spacing_strategy}
                onChange={(e) => setProfileForm((current) => ({ ...current, spacing_strategy: e.target.value }))}
              >
                <MenuItem value="standard">Standard</MenuItem>
                <MenuItem value="alternate_row">Alternate row</MenuItem>
                <MenuItem value="spaced">Spaced seating</MenuItem>
                <MenuItem value="computer_lab">Computer lab</MenuItem>
              </Select>
            </FormControl>
            <FormControlLabel
              control={<Switch checked={profileForm.requires_computers} onChange={(e) => setProfileForm((current) => ({ ...current, requires_computers: e.target.checked }))} />}
              label="Requires computer-capable rooms"
            />
            <FormControlLabel
              control={<Switch checked={profileForm.is_default} onChange={(e) => setProfileForm((current) => ({ ...current, is_default: e.target.checked }))} />}
              label="Set as default exam seating profile"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProfileDialogOpen(false)}>Cancel</Button>
          <Button onClick={() => void handleCreateProfile()} variant="contained" disabled={!canConfigurePeriod || busyAction === 'create-profile'}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={paperDialogOpen} onClose={() => setPaperDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Add Manual Exam Paper</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="info">
              Use this only for special cases. Normal examinable courses should come from the paper catalogue so the audience stays aligned with course-to-group mapping.
            </Alert>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <TextField label="Paper code" value={paperForm.paper_code} onChange={(e) => setPaperForm((current) => ({ ...current, paper_code: e.target.value }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={8}>
                <TextField label="Paper name" value={paperForm.paper_name} onChange={(e) => setPaperForm((current) => ({ ...current, paper_name: e.target.value }))} fullWidth />
              </Grid>
            </Grid>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="course-select-label">Course</InputLabel>
                  <Select
                    labelId="course-select-label"
                    label="Course"
                    value={paperForm.course_id}
                    onChange={(e) => handleCourseSelectedForManualPaper(e.target.value)}
                  >
                    <MenuItem value="">None</MenuItem>
                    {courses.map((course) => (
                      <MenuItem key={course.id} value={String(course.id)}>{course.code} | {course.name}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="group-select-label">Groups</InputLabel>
                  <Select
                    labelId="group-select-label"
                    label="Groups"
                    multiple
                    value={paperForm.group_ids}
                    onChange={(e) => setPaperForm((current) => ({ ...current, group_ids: e.target.value as number[] }))}
                    renderValue={(selected) => (selected as number[]).map((groupId) => groupLookup.get(groupId)?.name || `Group ${groupId}`).join(', ')}
                  >
                    {groups.map((group) => (
                      <MenuItem key={group.id} value={group.id}>
                        {group.name} | {group.size} students
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={3}>
                <TextField label="Duration (mins)" type="number" value={paperForm.duration_minutes} onChange={(e) => setPaperForm((current) => ({ ...current, duration_minutes: Number(e.target.value) }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField label="Candidate count" type="number" value={paperForm.candidate_count} onChange={(e) => setPaperForm((current) => ({ ...current, candidate_count: e.target.value }))} fullWidth helperText="Leave blank to derive from groups" />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField label="Max rooms" type="number" value={paperForm.max_rooms} onChange={(e) => setPaperForm((current) => ({ ...current, max_rooms: Number(e.target.value) }))} fullWidth />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField label="Preferred room type" value={paperForm.preferred_room_type} onChange={(e) => setPaperForm((current) => ({ ...current, preferred_room_type: e.target.value }))} fullWidth />
              </Grid>
            </Grid>
            <FormControl fullWidth>
              <InputLabel id="seating-profile-select-label">Preferred seating profile</InputLabel>
              <Select
                labelId="seating-profile-select-label"
                label="Preferred seating profile"
                value={paperForm.preferred_seating_profile_id}
                onChange={(e) => setPaperForm((current) => ({ ...current, preferred_seating_profile_id: e.target.value }))}
              >
                <MenuItem value="">Use default</MenuItem>
                {seatingProfiles.map((profile) => (
                  <MenuItem key={profile.id} value={String(profile.id)}>
                    {profile.name} | {profile.capacity_factor}% capacity
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControlLabel
              control={<Switch checked={paperForm.allow_custom_window} onChange={(e) => setPaperForm((current) => ({ ...current, allow_custom_window: e.target.checked }))} />}
              label="Allow custom session window placement later"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPaperDialogOpen(false)}>Cancel</Button>
          <Button onClick={() => void handleCreatePaper()} variant="contained" disabled={!canConfigurePeriod || busyAction === 'create-paper'}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ExamTimetablesPage;
