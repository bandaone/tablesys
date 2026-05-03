import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  AppBar,
  Avatar,
  BottomNavigation,
  BottomNavigationAction,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Drawer,
  FormControl,
  IconButton,
  InputLabel,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Select,
  Skeleton,
  useMediaQuery,
  type SelectChangeEvent,
  Stack,
  Toolbar,
  Typography,
} from '@mui/material';
import {
  AddToHomeScreen as AddToHomeScreenIcon,
  ArrowForwardRounded as ArrowForwardIcon,
  GroupsRounded as GroupsIcon,
  HomeRounded as HomeRoundedIcon,
  MenuBookRounded as MenuBookRoundedIcon,
  MenuRounded as MenuIcon,
  RefreshRounded as RefreshRoundedIcon,
  SchoolRounded as SchoolIcon,
  SearchRounded as SearchRoundedIcon,
  SwapHorizRounded as SwapHorizIcon,
  TodayRounded as TodayRoundedIcon,
  ViewWeekRounded as ViewWeekRoundedIcon,
  DashboardRounded as DashboardIcon,
  CalendarTodayRounded as CalendarTodayIcon,
  SearchRounded as SearchIcon,
  DateRangeRounded as DateRangeIcon,
  AutoStoriesRounded as AutoStoriesIcon,
  CampaignRounded as CampaignIcon,
  PlaceOutlined as PlaceOutlinedIcon,
} from '@mui/icons-material';
import dayjs from 'dayjs';
import { alpha, useTheme } from '@mui/material/styles';
import { useSearchParams } from 'react-router-dom';
import { useBranding } from '../contexts/BrandingContext';
import { studentPortalApi, type EtagFetchSource } from '../studentPortalApi';
import {
  StudentHomePanel,
  StudentMorePanel,
  StudentSearchPanel,
  StudentTodayPanel,
  StudentWeekPanel,
  StudentQuickActionCard,
  type SessionFilter,
} from '../components/student/StudentPortalPanels';
import { formatDepartmentName, formatGroupLabel, formatGroupName } from '../utils/displayFormatters';
import type {
  Course,
  FreeRoomsData,
  LookupDetail,
  LookupResult,
  TimetableSlot,
} from '../components/student/types';

// ── Cache keys ─────────────────────────────────────────────────────────────

const STUDENT_TIMETABLE_CACHE_KEY = 'student_portal_timetable';
const STUDENT_DASHBOARD_CACHE_KEY = 'student_portal_dashboard';
const STUDENT_NOW_CACHE_KEY = 'student_portal_now';
const STUDENT_FREE_ROOMS_DEFAULT_CACHE_KEY = 'student_portal_free_rooms_default';
const STUDENT_COURSES_CACHE_KEY = 'student_portal_courses';
const STUDENT_SYNC_CACHE_KEY = 'student_portal_last_synced_at';
const STUDENT_REMINDERS_KEY = 'student_portal_reminders';
const STUDENT_GROUP_META_KEY = 'student_portal_group_meta';
const ETAG_SUFFIX = ':etag';

// ── Types ──────────────────────────────────────────────────────────────────

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

type PortalTab = 'home' | 'today' | 'week' | 'search' | 'more';

interface TimetableData {
  student: {
    group_name?: string;
    group_breadcrumb?: string[];
    level?: number;
    department?: string | null;
  };
  timetable: {
    id?: number;
    name?: string;
    semester?: string;
    year?: number;
    academic_half?: string | null;
    is_active?: boolean;
    department?: string;
  };
  slots: TimetableSlot[];
  total_slots: number;
}

interface DashboardData {
  today_name: string;
  generated_at: string;
  stats: {
    today_total_sessions: number;
    week_total_sessions: number;
  };
  current_session: TimetableSlot | null;
  next_session: TimetableSlot | null;
  today_sessions: TimetableSlot[];
}

interface OnboardingDepartment {
  id: number;
  name: string;
  code: string;
  levels: {
    level: number;
    groups: {
      id: number;
      name: string;
      display_code: string | null;
      size: number;
      group_type: string | null;
      parent_group_id: number | null;
    }[];
  }[];
}

interface GroupMeta {
  group_id: number;
  group_name: string;
  department_name: string;
  level: number;
}

// ── Constants ──────────────────────────────────────────────────────────────

const DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const DAY_LABELS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const PORTAL_TABS: PortalTab[] = ['home', 'today', 'week', 'search', 'more'];
const SESSION_FILTERS: SessionFilter[] = ['all', 'lecture', 'tutorial', 'lab'];

const TAB_META: Record<PortalTab, { label: string; icon: React.ReactElement }> = {
  home: { label: 'Home', icon: <DashboardIcon /> },
  today: { label: 'Today', icon: <CalendarTodayIcon /> },
  week: { label: 'Week', icon: <DateRangeIcon /> },
  search: { label: 'Search', icon: <SearchIcon /> },
  more: { label: 'Courses', icon: <AutoStoriesIcon /> },
};

// ── Pure helpers ───────────────────────────────────────────────────────────

export const normalizeYearLevel = (levelStr?: string | number): string => {
  if (levelStr === undefined || levelStr === null) return '';
  let str = String(levelStr).trim();
  if (str.match(/^[1-9]00$/)) {
    str = String(parseInt(str, 10) / 100);
  }
  return str;
};

const getMinutesFromTime = (value: string): number => {
  const [hours, minutes] = value.split(':').map(Number);
  return hours * 60 + minutes;
};

const formatTimeRange = (slot: TimetableSlot): string => `${slot.start_time} - ${slot.end_time}`;

const formatDuration = (minutes: number): string => {
  if (minutes <= 0) return 'Now';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder === 0 ? `${hours} hr` : `${hours} hr ${remainder} min`;
};

const getDaySortIndex = (day: string): number => {
  const index = DAY_ORDER.indexOf(day);
  return index === -1 ? 999 : index;
};

const getSessionTone = (
  slot: TimetableSlot,
  currentDay: string,
  currentMinutes: number,
): { label: string; color: 'success' | 'warning' | 'default' } => {
  if (slot.day_of_week !== currentDay) return { label: slot.day_of_week, color: 'default' };
  const start = getMinutesFromTime(slot.start_time);
  const end = getMinutesFromTime(slot.end_time);
  if (currentMinutes >= start && currentMinutes < end) return { label: 'Live now', color: 'success' };
  if (start > currentMinutes && start - currentMinutes <= 30)
    return { label: `Starts in ${start - currentMinutes} min`, color: 'warning' };
  return { label: 'Today', color: 'default' };
};

type NormalizedSession = 'lecture' | 'tutorial' | 'lab';

const normalizeSessionType = (value?: string): NormalizedSession => {
  const normalized = (value || '').toLowerCase();
  if (normalized.includes('lab')) return 'lab';
  if (normalized.includes('tutorial')) return 'tutorial';
  return 'lecture';
};

const matchesSessionFilter = (slot: TimetableSlot, filter: SessionFilter): boolean => {
  if (filter === 'all') return true;
  return normalizeSessionType(slot.session_type) === filter;
};

const getSessionTypeChipColor = (value?: string): 'primary' | 'secondary' | 'success' | 'warning' => {
  switch (normalizeSessionType(value)) {
    case 'lab':
      return 'success';
    case 'tutorial':
      return 'warning';
    default:
      return 'primary';
  }
};

const formatSessionTypeLabel = (value?: string): string => {
  const normalized = normalizeSessionType(value);
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
};

const getNextSlot = (
  slots: TimetableSlot[],
  currentDayIndex: number,
  currentMinutes: number,
): TimetableSlot | null => {
  if (!slots.length) return null;
  const enriched = slots
    .map((slot) => ({
      slot,
      dayIndex: getDaySortIndex(slot.day_of_week),
      startMinutes: getMinutesFromTime(slot.start_time),
    }))
    .sort((a, b) => (a.dayIndex !== b.dayIndex ? a.dayIndex - b.dayIndex : a.startMinutes - b.startMinutes));

  const upcoming = enriched.find(
    ({ dayIndex, startMinutes }) =>
      dayIndex > currentDayIndex || (dayIndex === currentDayIndex && startMinutes > currentMinutes),
  );
  return upcoming?.slot || enriched[0]?.slot || null;
};

const readCachedJson = <T,>(key: string): T | null => {
  const rawValue = localStorage.getItem(key);
  if (!rawValue) return null;
  try {
    return JSON.parse(rawValue) as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// ONBOARDING WIZARD
// ═══════════════════════════════════════════════════════════════════════════

interface OnboardingWizardProps {
  primaryColor: string;
  secondaryColor: string;
  brandingName: string;
  onComplete: (meta: GroupMeta) => void;
}

const OnboardingWizard: React.FC<OnboardingWizardProps> = ({
  primaryColor,
  secondaryColor,
  brandingName,
  onComplete,
}) => {
  const [departments, setDepartments] = useState<OnboardingDepartment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedDeptId, setSelectedDeptId] = useState<string>('');
  const [selectedLevel, setSelectedLevel] = useState<string>('');
  const [selectedGroupId, setSelectedGroupId] = useState<string>('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await studentPortalApi.getOnboardingGroups();
        setDepartments(data.departments || []);
      } catch (err: any) {
        console.error('Failed to load onboarding groups:', err);
        setError('Unable to load available groups. Please try again later.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const selectedDept = useMemo(
    () => departments.find((d) => String(d.id) === selectedDeptId) || null,
    [departments, selectedDeptId],
  );

  const deptOptions = useMemo(
    () =>
      [...departments]
        .map((dept) => ({
          ...dept,
          normalizedName: formatDepartmentName(dept.name),
        }))
        .sort((a, b) => a.normalizedName.localeCompare(b.normalizedName)),
    [departments],
  );

  const levelOptions = useMemo(
    () =>
      [...(selectedDept?.levels || [])].sort((a, b) => Number(a.level) - Number(b.level)),
    [selectedDept],
  );

  const selectedLevelBucket = useMemo(() => {
    if (!selectedDept || !selectedLevel) return null;
    return selectedDept.levels.find((lvl) => String(lvl.level) === selectedLevel) || null;
  }, [selectedDept, selectedLevel]);

  const groupOptions = useMemo(
    () =>
      [...(selectedLevelBucket?.groups || [])].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
      ),
    [selectedLevelBucket],
  );

  const handleDeptChange = (e: SelectChangeEvent) => {
    setSelectedDeptId(e.target.value);
    setSelectedLevel('');
    setSelectedGroupId('');
  };

  const handleLevelChange = (e: SelectChangeEvent) => {
    setSelectedLevel(e.target.value);
    setSelectedGroupId('');
  };

  const handleGroupChange = (e: SelectChangeEvent) => {
    setSelectedGroupId(e.target.value);
  };

  const handleSubmit = () => {
    if (!selectedDept || !selectedLevelBucket) return;
    const selectedGroup = selectedLevelBucket.groups.find((group) => String(group.id) === selectedGroupId);
    if (!selectedGroup) return;

    onComplete({
      group_id: selectedGroup.id,
      group_name: selectedGroup.name,
      department_name: formatDepartmentName(selectedDept.name),
      level: Number(selectedLevel),
    });
  };

  const canSubmit = selectedDeptId !== '' && selectedLevel !== '' && selectedGroupId !== '';

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: `radial-gradient(ellipse at top left, ${alpha(secondaryColor, 0.22)} 0%, transparent 50%), radial-gradient(ellipse at bottom right, ${alpha(primaryColor, 0.18)} 0%, transparent 50%), linear-gradient(160deg, #0f172a 0%, ${alpha(primaryColor, 0.92)} 50%, #0f172a 100%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Container maxWidth="sm">
        <Paper
          elevation={0}
          sx={{
            p: { xs: 3, sm: 4 },
            borderRadius: 6,
            border: `1px solid ${alpha('#ffffff', 0.18)}`,
            background: `linear-gradient(135deg, ${alpha('#ffffff', 0.12)} 0%, ${alpha('#ffffff', 0.06)} 100%)`,
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            boxShadow: `0 32px 80px ${alpha('#000000', 0.35)}, inset 0 1px 0 ${alpha('#ffffff', 0.15)}`,
            color: '#fff',
          }}
        >
          <Stack spacing={3.5}>
            {/* Header */}
            <Box>
              <Stack spacing={1.25} alignItems="center" textAlign="center">
                <Avatar
                  sx={{
                    bgcolor: alpha('#ffffff', 0.15),
                    width: 64,
                    height: 64,
                    backdropFilter: 'blur(8px)',
                    border: `1px solid ${alpha('#ffffff', 0.2)}`,
                  }}
                >
                  <SchoolIcon sx={{ fontSize: 30, color: '#fff' }} />
                </Avatar>
                <Box>
                  <Typography variant="h5" fontWeight={800} sx={{ color: '#fff' }}>
                    Student Timetable
                  </Typography>
                  <Typography variant="body2" sx={{ color: alpha('#ffffff', 0.7) }}>
                    Select your department to get started
                  </Typography>
                </Box>
              </Stack>
            </Box>

            {error && (
              <Alert severity="error" sx={{ borderRadius: 3 }}>
                {error}
              </Alert>
            )}

            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress sx={{ color: '#fff' }} />
              </Box>
            ) : departments.length === 0 ? (
              <Alert severity="info" sx={{ borderRadius: 3 }}>
                No timetable groups are available yet. Please check back once a timetable has been published by your coordinator.
              </Alert>
            ) : (
              <Stack spacing={2.5}>
                {/* Department */}
                <FormControl
                  fullWidth
                  sx={{
                    '& .MuiInputLabel-root': { color: alpha('#ffffff', 0.65) },
                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                    '& .MuiOutlinedInput-root': {
                      color: '#fff',
                      borderRadius: 3,
                      backgroundColor: alpha('#ffffff', 0.06),
                      backdropFilter: 'blur(8px)',
                      '& fieldset': { borderColor: alpha('#ffffff', 0.2) },
                      '&:hover fieldset': { borderColor: alpha('#ffffff', 0.4) },
                      '&.Mui-focused fieldset': { borderColor: '#fff' },
                    },
                    '& .MuiSelect-icon': { color: alpha('#ffffff', 0.6) },
                  }}
                >
                  <InputLabel id="dept-label">Department / School</InputLabel>
                  <Select
                    labelId="dept-label"
                    value={selectedDeptId}
                    label="Department / School"
                    onChange={handleDeptChange}
                    MenuProps={{ PaperProps: { sx: { maxHeight: 280 } } }}
                  >
                    {deptOptions.map((d) => (
                      <MenuItem key={d.id} value={String(d.id)}>
                        {d.normalizedName}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {/* Year */}
                <FormControl
                  fullWidth
                  disabled={!selectedDept}
                  sx={{
                    '& .MuiInputLabel-root': { color: alpha('#ffffff', 0.65) },
                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                    '& .MuiOutlinedInput-root': {
                      color: '#fff',
                      borderRadius: 3,
                      backgroundColor: alpha('#ffffff', 0.06),
                      backdropFilter: 'blur(8px)',
                      '& fieldset': { borderColor: alpha('#ffffff', 0.2) },
                      '&:hover fieldset': { borderColor: alpha('#ffffff', 0.4) },
                      '&.Mui-focused fieldset': { borderColor: '#fff' },
                    },
                    '& .MuiSelect-icon': { color: alpha('#ffffff', 0.6) },
                  }}
                >
                  <InputLabel id="level-label">Year</InputLabel>
                  <Select
                    labelId="level-label"
                    value={selectedLevel}
                    label="Year"
                    onChange={handleLevelChange}
                  >
                    {levelOptions.map((levelBucket) => (
                      <MenuItem key={levelBucket.level} value={String(levelBucket.level)}>
                        Year {normalizeYearLevel(levelBucket.level)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {/* Group */}
                <FormControl
                  fullWidth
                  disabled={!selectedLevelBucket}
                  sx={{
                    '& .MuiInputLabel-root': { color: alpha('#ffffff', 0.65) },
                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                    '& .MuiOutlinedInput-root': {
                      color: '#fff',
                      borderRadius: 3,
                      backgroundColor: alpha('#ffffff', 0.06),
                      backdropFilter: 'blur(8px)',
                      '& fieldset': { borderColor: alpha('#ffffff', 0.2) },
                      '&:hover fieldset': { borderColor: alpha('#ffffff', 0.4) },
                      '&.Mui-focused fieldset': { borderColor: '#fff' },
                    },
                    '& .MuiSelect-icon': { color: alpha('#ffffff', 0.6) },
                  }}
                >
                  <InputLabel id="group-label">Group / Stream</InputLabel>
                  <Select
                    labelId="group-label"
                    value={selectedGroupId}
                    label="Group / Stream"
                    onChange={handleGroupChange}
                    MenuProps={{ PaperProps: { sx: { maxHeight: 280 } } }}
                  >
                    {groupOptions.map((group) => (
                      <MenuItem key={group.id} value={String(group.id)}>
                        {formatGroupLabel(group)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {selectedDept && selectedLevelBucket && groupOptions.length === 0 && (
                  <Typography variant="caption" sx={{ color: alpha('#ffffff', 0.65), mt: -0.5 }}>
                    No groups are available for the selected year.
                  </Typography>
                )}

                {/* Submit */}
                <Button
                  fullWidth
                  variant="contained"
                  size="large"
                  disabled={!canSubmit}
                  onClick={handleSubmit}
                  endIcon={<ArrowForwardIcon />}
                  sx={{
                    py: 1.6,
                    borderRadius: 3,
                    fontWeight: 700,
                    fontSize: '1rem',
                    bgcolor: alpha('#ffffff', 0.18),
                    color: '#fff',
                    backdropFilter: 'blur(8px)',
                    border: `1px solid ${alpha('#ffffff', 0.25)}`,
                    boxShadow: `0 8px 32px ${alpha('#000', 0.2)}`,
                    '&:hover': {
                      bgcolor: alpha('#ffffff', 0.28),
                      boxShadow: `0 12px 40px ${alpha('#000', 0.3)}`,
                    },
                    '&.Mui-disabled': {
                      bgcolor: alpha('#ffffff', 0.06),
                      color: alpha('#ffffff', 0.3),
                      border: `1px solid ${alpha('#ffffff', 0.08)}`,
                    },
                  }}
                >
                  Open My Timetable
                </Button>
              </Stack>
            )}

            <Typography variant="caption" sx={{ color: alpha('#ffffff', 0.45), textAlign: 'center' }}>
              Your selection is saved on this device. No account needed.
            </Typography>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
};

// ═══════════════════════════════════════════════════════════════════════════
// MAIN PORTAL
// ═══════════════════════════════════════════════════════════════════════════

const StudentPortal: React.FC = () => {
  const { branding } = useBranding();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab');

  // Group selection state
  const [groupReady, setGroupReady] = useState<boolean>(() => studentPortalApi.hasGroup());
  const [groupMeta, setGroupMeta] = useState<GroupMeta | null>(() =>
    readCachedJson<GroupMeta>(STUDENT_GROUP_META_KEY),
  );

  // Data state
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timetableData, setTimetableData] = useState<TimetableData | null>(() =>
    readCachedJson<TimetableData>(STUDENT_TIMETABLE_CACHE_KEY),
  );
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(() =>
    readCachedJson<DashboardData>(STUDENT_DASHBOARD_CACHE_KEY),
  );
  const [courses, setCourses] = useState<Course[]>(
    () => readCachedJson<Course[]>(STUDENT_COURSES_CACHE_KEY) || [],
  );
  const [announcements, setAnnouncements] = useState<any[]>(
    () => readCachedJson<any[]>('student_portal_announcements') || [],
  );
  const [activeTab, setActiveTab] = useState<PortalTab>(
    initialTab && PORTAL_TABS.includes(initialTab as PortalTab) ? (initialTab as PortalTab) : 'home',
  );
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(
    localStorage.getItem(STUDENT_SYNC_CACHE_KEY),
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<LookupResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedLookup, setSelectedLookup] = useState<LookupDetail | null>(null);
  const [freeRoomsData, setFreeRoomsData] = useState<FreeRoomsData | null>(null);
  const [freeRoomsLoading, setFreeRoomsLoading] = useState(false);
  const [freeRoomsSource, setFreeRoomsSource] = useState<EtagFetchSource | null>(null);
  const [lastRefreshSource, setLastRefreshSource] = useState<EtagFetchSource | null>(null);
  const [todayFilter, setTodayFilter] = useState<SessionFilter>('all');
  const [weekFilter, setWeekFilter] = useState<SessionFilter>('all');
  const [offlineReady, setOfflineReady] = useState(false);
  const [isOnline, setIsOnline] = useState(() => window.navigator.onLine);
  const [installPromptEvent, setInstallPromptEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [installing, setInstalling] = useState(false);
  const [remindersEnabled, setRemindersEnabled] = useState<boolean>(
    () => localStorage.getItem(STUDENT_REMINDERS_KEY) === 'enabled',
  );
  const [reminderMinutes, setReminderMinutes] = useState<number>(30);

  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#ff8c00';
  const currentDay = dashboardData?.today_name || DAY_LABELS[dayjs().day()];
  const currentDayIndex = getDaySortIndex(currentDay);
  const currentMinutes = dayjs().hour() * 60 + dayjs().minute();
  const brandingName = branding.short_name || branding.name || 'TABLESYS';

  // Derived group display name with strict formatting normalization
  const rawGroupName = groupMeta?.group_name || timetableData?.student?.group_name || 'Unknown Group';
  const rawGroupLevel = groupMeta?.level || timetableData?.student?.level;

  const groupDisplayName = formatGroupName(rawGroupName);
  const groupDepartment = formatDepartmentName(groupMeta?.department_name || timetableData?.student?.department || '');
  const groupLevel = normalizeYearLevel(rawGroupLevel);

  const slots: TimetableSlot[] = timetableData?.slots || [];
  const sortedSlots = useMemo(
    () =>
      [...slots].sort((a, b) => {
        const dayDiff = getDaySortIndex(a.day_of_week) - getDaySortIndex(b.day_of_week);
        return dayDiff !== 0 ? dayDiff : getMinutesFromTime(a.start_time) - getMinutesFromTime(b.start_time);
      }),
    [slots],
  );

  const todaysSlots = dashboardData?.today_sessions?.length
    ? dashboardData.today_sessions
    : sortedSlots.filter((s) => s.day_of_week === currentDay);

  const currentSlot =
    dashboardData?.current_session ||
    todaysSlots.find(
      (s) => currentMinutes >= getMinutesFromTime(s.start_time) && currentMinutes < getMinutesFromTime(s.end_time),
    ) ||
    null;

  const nextSlot = dashboardData?.next_session || getNextSlot(sortedSlots, currentDayIndex, currentMinutes);

  const totalTodayHours = todaysSlots.reduce(
    (total, s) => total + (getMinutesFromTime(s.end_time) - getMinutesFromTime(s.start_time)) / 60,
    0,
  );

  const gapUntilNext =
    nextSlot && nextSlot.day_of_week === currentDay
      ? getMinutesFromTime(nextSlot.start_time) - currentMinutes
      : null;

  const filteredTodaySlots = todaysSlots.filter((s) => matchesSessionFilter(s, todayFilter));

  const groupedSlots = sortedSlots.reduce<Record<string, TimetableSlot[]>>((groups, slot) => {
    const day = slot.day_of_week;
    if (!groups[day]) groups[day] = [];
    groups[day].push(slot);
    return groups;
  }, {});

  const filteredWeekGroups = DAY_ORDER.reduce<Record<string, TimetableSlot[]>>((groups, day) => {
    const daySlots = (groupedSlots[day] || []).filter((s) => matchesSessionFilter(s, weekFilter));
    if (daySlots.length) groups[day] = daySlots;
    return groups;
  }, {});

  const weeklyHours = sortedSlots.reduce(
    (total, s) => total + (getMinutesFromTime(s.end_time) - getMinutesFromTime(s.start_time)) / 60,
    0,
  );

  const firstTodaySlot = todaysSlots[0] || null;
  const lastTodaySlot = todaysSlots[todaysSlots.length - 1] || null;

  // ── Clear all cached data ──────────────────────────────────────────────

  const clearCachedData = useCallback(() => {
    localStorage.removeItem(STUDENT_TIMETABLE_CACHE_KEY);
    localStorage.removeItem(STUDENT_DASHBOARD_CACHE_KEY);
    localStorage.removeItem(STUDENT_NOW_CACHE_KEY);
    localStorage.removeItem(STUDENT_FREE_ROOMS_DEFAULT_CACHE_KEY);
    localStorage.removeItem(STUDENT_COURSES_CACHE_KEY);
    localStorage.removeItem(STUDENT_SYNC_CACHE_KEY);
    localStorage.removeItem(STUDENT_GROUP_META_KEY);
    localStorage.removeItem(`${STUDENT_TIMETABLE_CACHE_KEY}${ETAG_SUFFIX}`);
    localStorage.removeItem(`${STUDENT_DASHBOARD_CACHE_KEY}${ETAG_SUFFIX}`);
    localStorage.removeItem(`${STUDENT_NOW_CACHE_KEY}${ETAG_SUFFIX}`);
    localStorage.removeItem(`${STUDENT_FREE_ROOMS_DEFAULT_CACHE_KEY}${ETAG_SUFFIX}`);

    Object.keys(localStorage)
      .filter((key) => key.startsWith('student_portal_free_rooms_') && key !== STUDENT_FREE_ROOMS_DEFAULT_CACHE_KEY)
      .forEach((key) => {
        localStorage.removeItem(key);
        localStorage.removeItem(`${key}${ETAG_SUFFIX}`);
      });
  }, []);

  // ── Data fetchers ──────────────────────────────────────────────────────

  const fetchDashboard = async (): Promise<EtagFetchSource> => {
    const response = await studentPortalApi.getDashboard();
    const next: DashboardData = {
      today_name: response.data.today_name,
      generated_at: response.data.generated_at,
      stats: response.data.stats,
      current_session: response.data.current_session,
      next_session: response.data.next_session,
      today_sessions: response.data.today_sessions || [],
    };
    setDashboardData(next);
    localStorage.setItem(STUDENT_DASHBOARD_CACHE_KEY, JSON.stringify(next));
    return response.source;
  };

  const fetchTimetable = async (): Promise<EtagFetchSource> => {
    const response = await studentPortalApi.getWeek();
    const next: TimetableData = {
      student: response.data.profile,
      timetable: response.data.timetable,
      slots: response.data.sessions,
      total_slots: response.data.sessions.length,
    };
    const syncedAt = dayjs().format('YYYY-MM-DD HH:mm');
    setTimetableData(next);
    setLastSyncedAt(syncedAt);
    localStorage.setItem(STUDENT_TIMETABLE_CACHE_KEY, JSON.stringify(next));
    localStorage.setItem(STUDENT_SYNC_CACHE_KEY, syncedAt);
    return response.source;
  };

  const fetchCourses = async () => {
    const response = await studentPortalApi.getCourses();
    setCourses(response);
    localStorage.setItem(STUDENT_COURSES_CACHE_KEY, JSON.stringify(response));
  };

  const fetchAnnouncements = async () => {
    try {
      const response = await studentPortalApi.getAnnouncements();
      setAnnouncements(response.data.announcements || []);
      localStorage.setItem('student_portal_announcements', JSON.stringify(response.data.announcements || []));
    } catch {
      // ignore
    }
  };

  const refreshPortalData = useCallback(async () => {
    if (!groupReady) return;
    setPageLoading(true);
    setError(null);
    try {
      const [dashboardSource, timetableSource] = await Promise.all([
        fetchDashboard(),
        fetchTimetable(),
        fetchCourses(),
        fetchAnnouncements(),
      ]);
      setLastRefreshSource(
        dashboardSource === 'cache-304' && timetableSource === 'cache-304' ? 'cache-304' : 'network',
      );
    } catch (err: any) {
      console.error('Failed to refresh student portal:', err);
      setLastRefreshSource(null);
      const hasCached = Boolean(
        localStorage.getItem(STUDENT_TIMETABLE_CACHE_KEY) ||
          localStorage.getItem(STUDENT_COURSES_CACHE_KEY),
      );
      if (!hasCached) {
        setError(err.response?.data?.detail || 'Failed to load your timetable data.');
      }
    } finally {
      setPageLoading(false);
    }
  }, [groupReady]);

  // ── Effects ────────────────────────────────────────────────────────────

  useEffect(() => {
    if (groupReady) {
      refreshPortalData();
    }
  }, [groupReady, refreshPortalData]);

  useEffect(() => {
    const requestedTab = searchParams.get('tab');
    const nextTab =
      requestedTab && PORTAL_TABS.includes(requestedTab as PortalTab) ? (requestedTab as PortalTab) : 'home';
    if (nextTab !== activeTab) setActiveTab(nextTab);
  }, [searchParams]);

  useEffect(() => {
    const nextParams = new URLSearchParams(searchParams);
    if (activeTab === 'home') nextParams.delete('tab');
    else nextParams.set('tab', activeTab);
    const current = searchParams.toString();
    const next = nextParams.toString();
    if (current !== next) setSearchParams(nextParams, { replace: true });
  }, [activeTab, searchParams, setSearchParams]);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      setInstallPromptEvent(event as BeforeInstallPromptEvent);
    };
    const handleInstalled = () => {
      setInstallPromptEvent(null);
      setOfflineReady(true);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleInstalled);

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready
        .then(() => setOfflineReady(true))
        .catch(() => undefined);
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleInstalled);
    };
  }, []);

  const notifiedSlotsRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!remindersEnabled || !('Notification' in window) || Notification.permission !== 'granted') return;

    // Use a 30-second polling interval instead of a static setTimeout which can be paused/killed by mobile browsers.
    const interval = window.setInterval(() => {
      if (!nextSlot || nextSlot.day_of_week !== currentDay) return;

      const nowMinutes = dayjs().hour() * 60 + dayjs().minute();
      const startMinutes = getMinutesFromTime(nextSlot.start_time);
      const diffMinutes = startMinutes - nowMinutes;

      if (diffMinutes > 0 && diffMinutes <= reminderMinutes && !notifiedSlotsRef.current.has(nextSlot.id)) {
        notifiedSlotsRef.current.add(nextSlot.id);
        new Notification(`Upcoming class: ${nextSlot.course_code}`, {
          body: `${nextSlot.course_name} starts at ${nextSlot.start_time}${nextSlot.room_number && nextSlot.room_number !== '0' ? ` in ${nextSlot.room_number}` : ''}.`,
        });
      }
    }, 30000);

    return () => window.clearInterval(interval);
  }, [currentDay, nextSlot, reminderMinutes, remindersEnabled]);

  // ── Search effects ─────────────────────────────────────────────────────

  useEffect(() => {
    let active = true;
    const runLookup = async () => {
      const query = searchQuery.trim();
      if (query.length < 2 || !groupReady) {
        if (active) {
          setSearchResults([]);
          setSearchLoading(false);
        }
        return;
      }
      setSearchLoading(true);
      try {
        const response = await studentPortalApi.lookup(query);
        if (active) setSearchResults(response.results || []);
      } catch {
        if (active) setSearchResults([]);
      } finally {
        if (active) setSearchLoading(false);
      }
    };
    const timeout = window.setTimeout(runLookup, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [searchQuery, groupReady]);

  useEffect(() => {
    if (activeTab === 'search' && groupReady) loadFreeRoomsNow();
  }, [activeTab, groupReady]);

  // ── Handlers ───────────────────────────────────────────────────────────

  const handleOnboardingComplete = (meta: GroupMeta) => {
    studentPortalApi.setGroupId(meta.group_id);
    localStorage.setItem(STUDENT_GROUP_META_KEY, JSON.stringify(meta));
    setGroupMeta(meta);
    setGroupReady(true);
  };

  const handleChangeGroup = () => {
    studentPortalApi.clearGroupId();
    clearCachedData();
    setGroupReady(false);
    setGroupMeta(null);
    setTimetableData(null);
    setDashboardData(null);
    setCourses([]);
    setActiveTab('home');
    setAnchorEl(null);
  };

  const handleInstallApp = async () => {
    if (!installPromptEvent) return;
    setInstalling(true);
    try {
      await installPromptEvent.prompt();
      const result = await installPromptEvent.userChoice;
      if (result.outcome === 'accepted') setInstallPromptEvent(null);
    } catch (error) {
      console.error('Install prompt failed:', error);
    } finally {
      setInstalling(false);
    }
  };

  const openSearchWithPreset = (query: string) => {
    setActiveTab('search');
    setSelectedLookup(null);
    setSearchQuery(query);
  };

  const loadFreeRoomsNow = async () => {
    if (!groupReady) return;
    setFreeRoomsLoading(true);
    try {
      const response = await studentPortalApi.getFreeRoomsNow();
      setFreeRoomsData(response.data);
      setFreeRoomsSource(response.source);
    } catch {
      setFreeRoomsData(null);
      setFreeRoomsSource(null);
    } finally {
      setFreeRoomsLoading(false);
    }
  };

  const exportTimetable = () => {
    if (!timetableData) return;
    const data = JSON.stringify(timetableData, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `timetable_${groupDisplayName.replace(/\s+/g, '_')}.json`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const exportCalendar = () => {
    if (!sortedSlots.length) return;
    const calendarLines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//TABLESYS//Student Timetable//EN',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
    ];
    const baseDate = dayjs().startOf('week').add(1, 'day');
    sortedSlots.forEach((slot) => {
      const dayIndex = Math.max(getDaySortIndex(slot.day_of_week), 0);
      const sessionDate = baseDate.add(dayIndex, 'day');
      const [startHour, startMinute] = slot.start_time.split(':').map(Number);
      const [endHour, endMinute] = slot.end_time.split(':').map(Number);
      const start = sessionDate.hour(startHour).minute(startMinute).second(0);
      const end = sessionDate.hour(endHour).minute(endMinute).second(0);

      calendarLines.push('BEGIN:VEVENT');
      calendarLines.push(`UID:tablesys-student-${slot.id}@tablesys`);
      calendarLines.push(`DTSTAMP:${dayjs().format('YYYYMMDDTHHmmss')}`);
      calendarLines.push(`DTSTART:${start.format('YYYYMMDDTHHmmss')}`);
      calendarLines.push(`DTEND:${end.format('YYYYMMDDTHHmmss')}`);
      calendarLines.push(`SUMMARY:${slot.course_code} ${slot.course_name}`);
      calendarLines.push(`DESCRIPTION:${slot.lecturer_name} | ${formatSessionTypeLabel(slot.session_type)}`);
      calendarLines.push(`LOCATION:${slot.room_number} ${slot.building}`);
      calendarLines.push('END:VEVENT');
    });
    calendarLines.push('END:VCALENDAR');

    const blob = new Blob([calendarLines.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `timetable_${groupDisplayName.replace(/\s+/g, '_')}.ics`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const toggleReminders = async () => {
    if (!('Notification' in window)) {
      setError('This browser does not support timetable reminders.');
      return;
    }
    if (!remindersEnabled) {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setError('Reminder permission was not granted.');
        return;
      }
      localStorage.setItem(STUDENT_REMINDERS_KEY, 'enabled');
      setRemindersEnabled(true);
      return;
    }
    localStorage.removeItem(STUDENT_REMINDERS_KEY);
    setRemindersEnabled(false);
  };

  const handleSelectLookup = async (result: LookupResult) => {
    setSelectedLookup(null);
    setSearchLoading(true);
    try {
      const detail = await studentPortalApi.getLookupDetail(result.type, result.id);
      setSelectedLookup(detail);
    } catch (err) {
      console.error('Failed to load lookup detail:', err);
    } finally {
      setSearchLoading(false);
    }
  };

  const getLookupChipColor = (type: LookupResult['type']): 'primary' | 'secondary' | 'success' | 'warning' => {
    switch (type) {
      case 'course':
        return 'primary';
      case 'lecturer':
        return 'secondary';
      case 'room':
        return 'success';
      case 'group':
        return 'warning';
    }
  };

  // ═════════════════════════════════════════════════════════════════════════
  // RENDER: Onboarding wizard (no group selected)
  // ═════════════════════════════════════════════════════════════════════════

  if (!groupReady) {
    return (
      <OnboardingWizard
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
        brandingName={brandingName}
        onComplete={handleOnboardingComplete}
      />
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // RENDER: Main portal
  // ═════════════════════════════════════════════════════════════════════════

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: `radial-gradient(circle at top, ${alpha(secondaryColor, 0.2)} 0%, transparent 28%), linear-gradient(180deg, ${alpha(primaryColor, 0.06)} 0%, #f6f8fb 30%, #eef2f7 100%)`,
        pb: isDesktop ? 6 : 14,
      }}
    >
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: alpha('#ffffff', 0.9),
          color: 'text.primary',
          backdropFilter: 'blur(16px)',
          borderBottom: '1px solid',
          borderColor: alpha(primaryColor, 0.08),
        }}
      >
        <Toolbar sx={{ minHeight: 72 }}>
          <Typography variant="h6" fontWeight={800} sx={{ flexGrow: 1 }} noWrap>
            {brandingName}
          </Typography>

          <Box
            onClick={(event) => setAnchorEl(event.currentTarget)}
            sx={{
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              gap: 1.5,
              cursor: 'pointer',
              py: 0.5,
              px: 1,
              mr: -1,
              borderRadius: 3,
              transition: 'all 0.2s ease',
              '&:hover': {
                backgroundColor: alpha(primaryColor, 0.06),
              },
              '&:active': {
                transform: 'scale(0.98)',
              },
            }}
          >
            <Box sx={{ minWidth: 0, textAlign: 'right', display: { xs: 'none', sm: 'block' } }}>
              <Typography variant="subtitle2" fontWeight={800} noWrap>
                {groupDisplayName}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                {groupLevel ? `Year ${groupLevel}` : 'Student Portal'}
              </Typography>
            </Box>
            <Avatar
              sx={{
                bgcolor: primaryColor,
                color: '#fff',
                width: 42,
                height: 42,
                boxShadow: `0 12px 24px ${alpha(primaryColor, 0.35)}`,
                transition: 'transform 0.2s ease',
                ...(Boolean(anchorEl) && {
                  transform: 'scale(0.9)',
                }),
              }}
            >
              <SchoolIcon />
            </Avatar>
          </Box>

          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            PaperProps={{
              elevation: 0,
              sx: {
                overflow: 'visible',
                filter: 'drop-shadow(0px 16px 40px rgba(0,0,0,0.12))',
                mt: 1.5,
                borderRadius: 4,
                border: `1px solid ${alpha(primaryColor, 0.1)}`,
                minWidth: 220,
                p: 0.5,
                '& .MuiMenuItem-root': {
                  borderRadius: 2,
                  mx: 0.5,
                  my: 0.25,
                  fontWeight: 600,
                  fontSize: '0.9rem',
                },
              },
            }}
          >
            <MenuItem disabled sx={{ opacity: '1 !important', py: 1 }}>
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Current Selection
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 800, mt: 0.25 }}>
                  {groupDisplayName}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                  {groupDepartment}
                  {groupLevel ? ` · Year ${groupLevel}` : ''}
                </Typography>
              </Box>
            </MenuItem>
            <Divider sx={{ my: 0.5, opacity: 0.6 }} />
            <MenuItem
              onClick={() => {
                refreshPortalData();
                setAnchorEl(null);
              }}
              disabled={pageLoading}
            >
              {pageLoading ? (
                <CircularProgress size={18} sx={{ mr: 1.5, color: primaryColor }} />
              ) : (
                <RefreshRoundedIcon sx={{ mr: 1.5, fontSize: 18, color: primaryColor }} />
              )}
              {pageLoading ? 'Refreshing...' : 'Refresh live data'}
            </MenuItem>
            <MenuItem onClick={handleChangeGroup} sx={{ color: 'error.main' }}>
              <SwapHorizIcon sx={{ mr: 1.5, fontSize: 18 }} />
              Change Group
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Container maxWidth={isDesktop ? 'lg' : 'sm'} sx={{ pt: 2.25 }}>
        <Stack spacing={2}>
          {error && <Alert severity="warning">{error}</Alert>}

          {pageLoading && !timetableData && (
            <Stack spacing={2} sx={{ opacity: 0.8 }}>
              {/* Hero Card Skeleton */}
              <Skeleton variant="rectangular" height={190} sx={{ borderRadius: 5 }} animation="wave" />
              
              {/* Primary Action Skeleton */}
              <Skeleton variant="rectangular" height={110} sx={{ borderRadius: 4 }} animation="wave" />
              
              {/* Timeline Slot Skeletons */}
              <Stack direction="row" spacing={1.5} sx={{ mt: 1 }}>
                <Skeleton variant="circular" width={48} height={48} animation="wave" />
                <Skeleton variant="rectangular" height={80} sx={{ flex: 1, borderRadius: 3 }} animation="wave" />
              </Stack>
              <Stack direction="row" spacing={1.5}>
                <Skeleton variant="circular" width={48} height={48} animation="wave" />
                <Skeleton variant="rectangular" height={80} sx={{ flex: 1, borderRadius: 3 }} animation="wave" />
              </Stack>
              <Stack direction="row" spacing={1.5}>
                <Skeleton variant="circular" width={48} height={48} animation="wave" />
                <Skeleton variant="rectangular" height={80} sx={{ flex: 1, borderRadius: 3 }} animation="wave" />
              </Stack>
            </Stack>
          )}

          {(timetableData || dashboardData) && (
            <>

          {isDesktop && (
            <Paper
              elevation={0}
              sx={{
                p: 1,
                borderRadius: 4,
                border: '1px solid',
                borderColor: alpha(primaryColor, 0.12),
                bgcolor: alpha('#ffffff', 0.8),
                backdropFilter: 'blur(12px)',
              }}
            >
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', justifyContent: 'center' }}>
                {PORTAL_TABS.map((tab) => {
                  const isActive = activeTab === tab;
                  return (
                    <Button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      startIcon={TAB_META[tab].icon}
                      variant={isActive ? 'contained' : 'text'}
                      sx={{
                        borderRadius: 3,
                        px: 2,
                        py: 1,
                        fontWeight: 700,
                        textTransform: 'none',
                        ...(isActive
                          ? {
                              bgcolor: primaryColor,
                              color: '#fff',
                              boxShadow: `0 8px 22px ${alpha(primaryColor, 0.32)}`,
                              '&:hover': { bgcolor: alpha(primaryColor, 0.9) },
                            }
                          : {
                              color: 'text.primary',
                              '&:hover': { bgcolor: alpha(primaryColor, 0.08) },
                            }),
                      }}
                    >
                      {TAB_META[tab].label}
                    </Button>
                  );
                })}
              </Stack>
            </Paper>
          )}

          {installPromptEvent && (
            <Card sx={{ borderRadius: 5 }}>
              <CardContent sx={{ p: 2.25 }}>
                <Stack direction="row" spacing={1.5} alignItems="center" justifyContent="space-between">
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="subtitle2" fontWeight={800}>
                      Install on your phone
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Add this timetable to your home screen for faster access and offline reuse.
                    </Typography>
                  </Box>
                  <Button
                    variant="contained"
                    startIcon={<AddToHomeScreenIcon />}
                    onClick={handleInstallApp}
                    disabled={installing}
                    sx={{ flexShrink: 0 }}
                  >
                    {installing ? 'Installing...' : 'Install'}
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Announcements Card */}
          {announcements.length > 0 && (
            <Card
              sx={{
                borderRadius: 5,
                border: '1px solid',
                borderColor: alpha(secondaryColor, 0.3),
                bgcolor: alpha(secondaryColor, 0.05),
              }}
            >
              <CardContent sx={{ p: 2 }}>
                <Stack direction="row" alignItems="flex-start" spacing={1.5} mb={1}>
                  <Box sx={{ mt: 0.5, p: 1, borderRadius: 2, bgcolor: alpha(secondaryColor, 0.15) }}>
                    <CampaignIcon sx={{ color: secondaryColor }} />
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" fontWeight={800} color={secondaryColor}>
                      Noticeboard
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Important announcements from your lecturers
                    </Typography>
                  </Box>
                </Stack>
                <Stack spacing={1.5} sx={{ mt: 2 }}>
                  {announcements.map((a) => (
                    <Box key={a.id} sx={{ pl: 2, borderLeft: '3px solid', borderColor: a.type === 'class_cancelled' ? 'error.main' : a.type === 'test_scheduled' ? 'secondary.main' : 'divider' }}>
                       <Stack direction="row" spacing={1} alignItems="center" mb={0.25}>
                         <Chip size="small" label={a.type.replace('_', ' ')} color={a.type === 'class_cancelled' ? 'error' : a.type === 'test_scheduled' ? 'secondary' : 'default'} sx={{ height: 20, fontSize: '0.65rem', textTransform: 'capitalize' }} />
                         <Typography variant="body2" fontWeight={700}>{a.title}</Typography>
                       </Stack>
                       <Typography variant="body2" color="text.secondary">{a.message}</Typography>
                       {(a.target_date || a.venue) && (
                         <Stack direction="row" spacing={1.5} sx={{ mt: 0.5, color: a.type === 'class_cancelled' ? 'error.main' : 'secondary.main', '& svg': { fontSize: 16 } }}>
                           {a.target_date && <Typography variant="caption" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><CalendarTodayIcon /> {new Date(a.target_date).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' })}</Typography>}
                           {a.venue && <Typography variant="caption" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><PlaceOutlinedIcon /> {a.venue}</Typography>}
                         </Stack>
                       )}
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Hero card — "Today at a Glance" */}
          <Card
            sx={{
              borderRadius: 5,
              overflow: 'hidden',
              color: '#fff',
              background: `linear-gradient(145deg, ${primaryColor} 0%, ${alpha(primaryColor, 0.92)} 52%, ${secondaryColor} 100%)`,
              boxShadow: `0 24px 60px ${alpha(primaryColor, 0.28)}`,
            }}
          >
            <CardContent sx={{ p: 2.5 }}>
              <Stack spacing={2}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
                  <Box sx={{ flex: 1, minWidth: 0, pr: 1 }}>
                    <Typography variant="overline" sx={{ letterSpacing: 1.3, opacity: 0.78, color: 'inherit' }}>
                      TODAY AT A GLANCE
                    </Typography>
                    <Typography variant="h5" fontWeight={800} color="inherit" sx={{ lineHeight: 1.2 }}>
                      {groupDisplayName}
                    </Typography>
                  </Box>
                  <Chip
                    label={currentSlot ? 'In class' : todaysSlots.length ? 'On schedule' : 'Free day'}
                    sx={{
                      bgcolor: alpha('#ffffff', 0.16),
                      color: '#fff',
                      backdropFilter: 'blur(8px)',
                    }}
                  />
                </Stack>

                <Stack direction="row" spacing={1.2}>
                  <Paper
                    elevation={0}
                    sx={{
                      flex: 1,
                      p: 1.5,
                      borderRadius: 3,
                      bgcolor: alpha('#ffffff', 0.14),
                      color: '#fff',
                    }}
                  >
                    <Typography variant="caption" sx={{ opacity: 0.8 }}>
                      Classes today
                    </Typography>
                    <Typography variant="h6" fontWeight={800}>
                      {todaysSlots.length}
                    </Typography>
                  </Paper>
                  <Paper
                    elevation={0}
                    sx={{
                      flex: 1,
                      p: 1.5,
                      borderRadius: 3,
                      bgcolor: alpha('#ffffff', 0.14),
                      color: '#fff',
                    }}
                  >
                    <Typography variant="caption" sx={{ opacity: 0.8 }}>
                      Contact hours
                    </Typography>
                    <Typography variant="h6" fontWeight={800}>
                      {totalTodayHours ? totalTodayHours.toFixed(1) : '0.0'}h
                    </Typography>
                  </Paper>
                </Stack>
              </Stack>
            </CardContent>
          </Card>

          {activeTab === 'home' && (
            <StudentHomePanel
              currentSlot={currentSlot}
              nextSlot={nextSlot}
              gapUntilNext={gapUntilNext}
              weeklyHours={weeklyHours}
              firstTodaySlot={firstTodaySlot}
              lastTodaySlot={lastTodaySlot}
              currentDay={currentDay}
              currentMinutes={currentMinutes}
              formatDuration={formatDuration}
              formatTimeRange={formatTimeRange}
              exportTimetable={exportTimetable}
              openSearchWithPreset={openSearchWithPreset}
              setActiveTab={setActiveTab as (tab: 'today' | 'week' | 'more' | 'search') => void}
            />
          )}

          {activeTab === 'today' && (
            <StudentTodayPanel
              currentDay={currentDay}
              filters={SESSION_FILTERS}
              todayFilter={todayFilter}
              onFilterChange={setTodayFilter}
              filteredTodaySlots={filteredTodaySlots}
              currentMinutes={currentMinutes}
              formatTimeRange={formatTimeRange}
              getSessionTone={getSessionTone}
              formatSessionTypeLabel={formatSessionTypeLabel}
              getSessionTypeChipColor={getSessionTypeChipColor}
            />
          )}

          {activeTab === 'week' && (
            <StudentWeekPanel
              currentDay={currentDay}
              filters={SESSION_FILTERS}
              weekFilter={weekFilter}
              onFilterChange={setWeekFilter}
              filteredWeekGroups={filteredWeekGroups}
              dayOrder={DAY_ORDER}
              formatTimeRange={formatTimeRange}
              formatSessionTypeLabel={formatSessionTypeLabel}
              getSessionTypeChipColor={getSessionTypeChipColor}
              primaryColor={primaryColor}
            />
          )}

          {activeTab === 'search' && (
            <StudentSearchPanel
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              searchLoading={searchLoading}
              searchResults={searchResults}
              onSelectLookup={handleSelectLookup}
              selectedLookup={selectedLookup}
              getLookupChipColor={getLookupChipColor}
              primaryColor={primaryColor}
              secondaryColor={secondaryColor}
              formatTimeRange={formatTimeRange}
              freeRoomsData={freeRoomsData}
              freeRoomsLoading={freeRoomsLoading}
              freeRoomsSource={freeRoomsSource}
            />
          )}

          {activeTab === 'more' && (
            <StudentMorePanel
              timetableGroup={groupDisplayName}
              timetableSemester={timetableData?.timetable?.semester}
              timetableDepartment={groupDepartment || timetableData?.timetable?.department}
              lastSyncedAt={lastSyncedAt}
              weeklyHours={weeklyHours}
              remindersEnabled={remindersEnabled}
              reminderMinutes={reminderMinutes}
              onReminderToggle={toggleReminders}
              onReminderMinutesChange={setReminderMinutes}
              courses={courses}
              exportTimetable={exportTimetable}
              exportCalendar={exportCalendar}
            />
          )}

          </>
          )}

        </Stack>
      </Container>


      {!isDesktop && (
        <Box
          sx={{
            position: 'fixed',
            bottom: { xs: 24, sm: 32 },
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 0.5,
            px: 1.25,
            py: 0.75,
            height: 72,
            borderRadius: 36,
            background: alpha('#ffffff', 0.25),
            backdropFilter: 'blur(40px) saturate(200%)',
            WebkitBackdropFilter: 'blur(40px) saturate(200%)',
            border: `1px solid ${alpha('#ffffff', 0.4)}`,
            boxShadow: `0 24px 48px ${alpha('#000000', 0.12)}, inset 0 1px 0 ${alpha('#ffffff', 0.5)}`,
            zIndex: 1200,
            width: 'min(92vw, 420px)',
          }}
        >
          <DockButton active={activeTab === 'home'} icon={<DashboardIcon />} label="Home" onClick={() => setActiveTab('home')} primaryColor={primaryColor} />
          <DockButton active={activeTab === 'today'} icon={<CalendarTodayIcon />} label="Today" onClick={() => setActiveTab('today')} primaryColor={primaryColor} />
          <DockButton active={activeTab === 'search'} icon={<SearchIcon />} label="Search" onClick={() => setActiveTab('search')} primaryColor={primaryColor} isCenter />
          <DockButton active={activeTab === 'week'} icon={<DateRangeIcon />} label="Week" onClick={() => setActiveTab('week')} primaryColor={primaryColor} />
          <DockButton active={activeTab === 'more'} icon={<AutoStoriesIcon />} label="Courses" onClick={() => setActiveTab('more')} primaryColor={primaryColor} />
        </Box>
      )}
    </Box>
  );
};

const DockButton: React.FC<{
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  primaryColor: string;
  isCenter?: boolean;
}> = ({ active, icon, label, onClick, primaryColor, isCenter }) => (
  <Box
    onClick={onClick}
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minWidth: active ? 72 : 56, // Expands when active
      height: 56,
      borderRadius: 28, // Inner pill radius
      cursor: 'pointer',
      color: active ? primaryColor : 'text.primary',
      background: active ? alpha(primaryColor, 0.15) : 'transparent',
      transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
      px: active ? 2 : 0.5,
      '&:hover': {
        background: active ? alpha(primaryColor, 0.2) : alpha('#000000', 0.04),
      },
      '&:active': {
        transform: 'scale(0.94)',
      },
    }}
  >
    <Box sx={{ display: 'flex', mb: 0.4, transition: 'transform 0.2s', transform: active ? 'translateY(-1px)' : 'none' }}>
      {React.cloneElement(icon as React.ReactElement, { sx: { fontSize: isCenter ? 28 : (active ? 26 : 24) } })}
    </Box>
    <Typography
      variant="caption"
      sx={{
        fontSize: '0.65rem',
        fontWeight: active ? 800 : 600,
        opacity: active ? 1 : 0.7,
        lineHeight: 1,
        letterSpacing: 0.2,
      }}
    >
      {label}
    </Typography>
  </Box>
);

export default StudentPortal;
