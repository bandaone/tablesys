import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert,
  AppBar,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Menu,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  WorkRounded as WorkIcon,
  LogoutRounded as LogoutIcon,
  RefreshRounded as RefreshIcon,
  DashboardRounded as DashboardIcon,
  CalendarTodayRounded as CalendarTodayIcon,
  DateRangeRounded as DateRangeIcon,
  AutoStoriesRounded as AutoStoriesIcon,
  SearchRounded as SearchIcon,
} from '@mui/icons-material';
import dayjs from 'dayjs';

import { useBranding } from '../contexts/BrandingContext';
import { lecturerPortalApi } from '../lecturerPortalApi';
import type {
  LecturerCourse,
  LecturerCourseWorkload,
  LecturerDashboardResponse,
  LecturerProfile,
  LecturerTimetableSlot,
} from '../components/lecturer/types';
import {
  LecturerHomePanel,
  LecturerTodayPanel,
  LecturerWeekPanel,
  LecturerSearchPanel,
  LecturerCoursesPanel,
  LecturerExamsPanel,
} from '../components/lecturer/LecturerPortalPanels';
import {
  DAY_ORDER,
  formatDayLabel,
  formatTimeRange,
  type LecturerPortalTab,
} from '../components/lecturer/lecturerUtils';

// ── Constants ──────────────────────────────────────────────────────────────

const PORTAL_TABS: LecturerPortalTab[] = ['home', 'today', 'week', 'search', 'courses', 'exams'];

const TAB_META: Record<LecturerPortalTab, { label: string; icon: React.ReactElement }> = {
  home: { label: 'Home', icon: <DashboardIcon /> },
  today: { label: 'Today', icon: <CalendarTodayIcon /> },
  week: { label: 'Week', icon: <DateRangeIcon /> },
  search: { label: 'Search', icon: <SearchIcon /> },
  courses: { label: 'Courses', icon: <WorkIcon /> },
  exams: { label: 'Exams', icon: <AutoStoriesIcon /> },
};

const DAY_LABELS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// ── DockButton (identical to student portal dock) ──────────────────────────

const DockButton: React.FC<{
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  primaryColor: string;
  isCenter?: boolean;
}> = ({ active, icon, label, onClick, primaryColor }) => (
  <Box
    onClick={onClick}
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minWidth: active ? 72 : 56,
      height: 56,
      borderRadius: 28,
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
    <Box sx={{ fontSize: 22, display: 'flex', alignItems: 'center' }}>{icon}</Box>
    <Typography
      variant="caption"
      sx={{
        fontSize: '0.62rem',
        mt: 0.25,
        fontWeight: active ? 700 : 500,
        lineHeight: 1,
        opacity: active ? 1 : 0.7,
      }}
    >
      {label}
    </Typography>
  </Box>
);

// ── Main LecturerPortal ────────────────────────────────────────────────────

const LecturerPortal: React.FC = () => {
  const { branding } = useBranding();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#ff8c00';
  const brandName = branding.short_name || branding.name || 'TABLESYS';

  const currentDay = DAY_LABELS[dayjs().day()];
  const currentMinutes = dayjs().hour() * 60 + dayjs().minute();

  // ── State ──────────────────────────────────────────────────────────────

  const initialTab = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState<LecturerPortalTab>(
    initialTab && PORTAL_TABS.includes(initialTab as LecturerPortalTab)
      ? (initialTab as LecturerPortalTab)
      : 'home',
  );

  const [profile, setProfile] = useState<LecturerProfile | null>(null);
  const [dashboard, setDashboard] = useState<LecturerDashboardResponse | null>(null);
  const [sessions, setSessions] = useState<LecturerTimetableSlot[]>([]);
  const [courses, setCourses] = useState<LecturerCourse[]>([]);
  const [examData, setExamData] = useState<{ period: any; slots: any[] } | null>(null);
  const [examsLoading, setExamsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // ── URL sync ───────────────────────────────────────────────────────────

  useEffect(() => {
    const requested = searchParams.get('tab');
    const next =
      requested && PORTAL_TABS.includes(requested as LecturerPortalTab)
        ? (requested as LecturerPortalTab)
        : 'home';
    if (next !== activeTab) setActiveTab(next);
  }, [searchParams]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (activeTab === 'home') next.delete('tab');
    else next.set('tab', activeTab);
    if (searchParams.toString() !== next.toString())
      setSearchParams(next, { replace: true });
  }, [activeTab, searchParams, setSearchParams]);

  // ── Data Loading ───────────────────────────────────────────────────────

  const loadData = useCallback(async (isRefresh = false) => {
    const token = localStorage.getItem('lecturer_token');
    if (!token) {
      navigate('/lecturer/login');
      return;
    }
    if (isRefresh) setPageLoading(true);
    else setLoading(true);
    setError(null);

    // Load each endpoint independently so a single failure doesn't block everything
    const results = await Promise.allSettled([
      lecturerPortalApi.getMe(),
      lecturerPortalApi.getTimetable(),
      lecturerPortalApi.getCourses(),
      lecturerPortalApi.getDashboard(),
      lecturerPortalApi.getExamTimetable().catch(() => ({ period: null, slots: [] })),
    ]);

    const [meResult, ttResult, courseResult, dashResult, examResult] = results;

    if (meResult.status === 'fulfilled') setProfile(meResult.value);
    if (ttResult.status === 'fulfilled') setSessions(ttResult.value.sessions || []);
    if (courseResult.status === 'fulfilled') setCourses(courseResult.value || []);
    if (dashResult.status === 'fulfilled') setDashboard(dashResult.value);
    if (examResult.status === 'fulfilled') setExamData(examResult.value);

    const allFailed = results.slice(0, 4).every((r) => r.status === 'rejected');
    if (allFailed) {
      console.error('All lecturer API calls failed:', results);
      setError('Failed to load your timetable data. Please try refreshing.');
    }

    setLoading(false);
    setPageLoading(false);
  }, [navigate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Handlers ───────────────────────────────────────────────────────────

  const logout = () => {
    lecturerPortalApi.logout();
    navigate('/lecturer/login');
  };

  const exportTimetable = () => {
    if (!sessions.length) return;
    const data = JSON.stringify({ profile, sessions }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `timetable_${profile?.staff_number ?? 'lecturer'}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  // ── Loading skeleton ───────────────────────────────────────────────────

  if (loading) {
    return (
      <Box
        sx={{
          minHeight: '100vh',
          background: `linear-gradient(180deg, ${alpha(primaryColor, 0.06)} 0%, #f6f8fb 30%, #eef2f7 100%)`,
          pb: 10,
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
            <Typography variant="h6" fontWeight={800} sx={{ flexGrow: 1 }}>
              {brandName}
            </Typography>
            <Skeleton variant="circular" width={42} height={42} />
          </Toolbar>
        </AppBar>
        <Container maxWidth="lg" sx={{ pt: 2.25 }}>
          <Stack spacing={2}>
            <Skeleton variant="rectangular" height={190} sx={{ borderRadius: 5 }} animation="wave" />
            <Skeleton variant="rectangular" height={220} sx={{ borderRadius: 5 }} animation="wave" />
            <Stack direction="row" spacing={1.5}>
              <Skeleton variant="circular" width={48} height={48} animation="wave" />
              <Skeleton variant="rectangular" height={80} sx={{ flex: 1, borderRadius: 3 }} animation="wave" />
            </Stack>
          </Stack>
        </Container>
      </Box>
    );
  }

  // ── Derived values ─────────────────────────────────────────────────────

  const summary = dashboard?.summary ?? null;
  const courseWorkload: LecturerCourseWorkload[] = dashboard?.course_workload ?? [];
  const todaysSlots = sessions.filter((s) => s.day_of_week === currentDay);
  const currentSession =
    todaysSlots.find((s) => {
      const start = parseInt(s.start_time.split(':')[0]) * 60 + parseInt(s.start_time.split(':')[1]);
      const end = parseInt(s.end_time.split(':')[0]) * 60 + parseInt(s.end_time.split(':')[1]);
      return currentMinutes >= start && currentMinutes < end;
    }) || null;

  const staffDisplayName = profile?.full_name || 'Lecturer';
  const staffNumber = profile?.staff_number || '';

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: `radial-gradient(circle at top, ${alpha(secondaryColor, 0.2)} 0%, transparent 28%), linear-gradient(180deg, ${alpha(primaryColor, 0.06)} 0%, #f6f8fb 30%, #eef2f7 100%)`,
        pb: isDesktop ? 6 : 14,
      }}
    >
      {/* AppBar */}
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
            {brandName}
          </Typography>

          <Box
            onClick={(e) => setAnchorEl(e.currentTarget)}
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
              '&:hover': { backgroundColor: alpha(primaryColor, 0.06) },
              '&:active': { transform: 'scale(0.98)' },
            }}
          >
            <Box sx={{ minWidth: 0, textAlign: 'right', display: { xs: 'none', sm: 'block' } }}>
              <Typography variant="subtitle2" fontWeight={800} noWrap>
                {staffDisplayName}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                Lecturer Portal
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
                ...(Boolean(anchorEl) && { transform: 'scale(0.9)' }),
              }}
            >
              <WorkIcon />
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
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.secondary',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}
                >
                  Signed in as
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 800, mt: 0.25 }}>
                  {staffDisplayName}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                  {staffNumber}
                </Typography>
              </Box>
            </MenuItem>
            <Divider sx={{ my: 0.5, opacity: 0.6 }} />
            <MenuItem
              onClick={() => {
                loadData(true);
                setAnchorEl(null);
              }}
              disabled={pageLoading}
            >
              {pageLoading ? (
                <CircularProgress size={18} sx={{ mr: 1.5, color: primaryColor }} />
              ) : (
                <RefreshIcon sx={{ mr: 1.5, fontSize: 18, color: primaryColor }} />
              )}
              {pageLoading ? 'Refreshing…' : 'Refresh live data'}
            </MenuItem>
            <MenuItem onClick={logout} sx={{ color: 'error.main' }}>
              <LogoutIcon sx={{ mr: 1.5, fontSize: 18 }} />
              Sign out
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Main content */}
      <Container maxWidth={isDesktop ? 'lg' : 'sm'} sx={{ pt: 2.25 }}>
        <Stack spacing={2}>
          {error && <Alert severity="warning">{error}</Alert>}

          {pageLoading && sessions.length === 0 && (
            <Stack spacing={2} sx={{ opacity: 0.8 }}>
              <Skeleton variant="rectangular" height={190} sx={{ borderRadius: 5 }} animation="wave" />
              <Skeleton variant="rectangular" height={110} sx={{ borderRadius: 4 }} animation="wave" />
            </Stack>
          )}

          {/* Desktop tab nav */}
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

          {/* Hero card */}
          {(
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
                      <Typography
                        variant="overline"
                        sx={{ letterSpacing: 1.3, opacity: 0.78, color: 'inherit' }}
                      >
                        TODAY AT A GLANCE
                      </Typography>
                      <Typography variant="h5" fontWeight={800} color="inherit" sx={{ lineHeight: 1.2 }}>
                        {staffDisplayName}
                      </Typography>
                    </Box>
                    <Chip
                      label={currentSession ? 'Teaching now' : todaysSlots.length ? 'On schedule' : 'Free today'}
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
                        Sessions today
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
                        {(summary?.daily_teaching_hours ?? 0).toFixed(1)}h
                      </Typography>
                    </Paper>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Tab panels */}
          {activeTab === 'home' && (
            <LecturerHomePanel
              profile={profile}
              summary={summary}
              sessions={sessions}
              courseWorkload={courseWorkload}
              currentDay={currentDay}
              currentMinutes={currentMinutes}
              setActiveTab={setActiveTab}
            />
          )}

          {activeTab === 'today' && (
            <LecturerTodayPanel
              currentDay={currentDay}
              currentMinutes={currentMinutes}
              sessions={sessions}
            />
          )}

          {activeTab === 'week' && (
            <LecturerWeekPanel
              currentDay={currentDay}
              sessions={sessions}
              primaryColor={primaryColor}
            />
          )}

          {activeTab === 'search' && (
            <LecturerSearchPanel
              sessions={sessions}
              courses={courses}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              primaryColor={primaryColor}
            />
          )}

          {activeTab === 'courses' && (
            <LecturerCoursesPanel
              courses={courses}
              courseWorkload={courseWorkload}
              profile={profile}
              summary={summary}
              sessions={sessions}
              exportTimetable={exportTimetable}
            />
          )}

          {activeTab === 'exams' && (
            <LecturerExamsPanel
              loading={examsLoading}
              exams={examData?.slots || []}
              period={examData?.period}
            />
          )}
        </Stack>
      </Container>

      {/* Mobile floating dock */}
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
            width: 'min(96vw, 460px)',
          }}
        >
          <DockButton
            active={activeTab === 'home'}
            icon={<DashboardIcon />}
            label="Home"
            onClick={() => setActiveTab('home')}
            primaryColor={primaryColor}
          />
          <DockButton
            active={activeTab === 'today'}
            icon={<CalendarTodayIcon />}
            label="Today"
            onClick={() => setActiveTab('today')}
            primaryColor={primaryColor}
          />
          <DockButton
            active={activeTab === 'week'}
            icon={<DateRangeIcon />}
            label="Week"
            onClick={() => setActiveTab('week')}
            primaryColor={primaryColor}
            isCenter
          />
          <DockButton
            active={activeTab === 'search'}
            icon={<SearchIcon />}
            label="Search"
            onClick={() => setActiveTab('search')}
            primaryColor={primaryColor}
          />
          <DockButton
            active={activeTab === 'exams'}
            icon={<AutoStoriesIcon />}
            label="Exams"
            onClick={() => setActiveTab('exams')}
            primaryColor={primaryColor}
          />
          <DockButton
            active={activeTab === 'courses'}
            icon={<WorkIcon />}
            label="Courses"
            onClick={() => setActiveTab('courses')}
            primaryColor={primaryColor}
          />
        </Box>
      )}
    </Box>
  );
};

export default LecturerPortal;
