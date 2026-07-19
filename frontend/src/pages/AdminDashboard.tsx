import React, { useEffect, useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  IconButton,
  Tooltip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Stack
} from '@mui/material';
import {
  People as PeopleIcon,
  Book as BookIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  CalendarMonth as CalendarIcon,
  Business as BusinessIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  TrendingUp as TrendingUpIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import api from '../api';
import DashboardSkeleton from '../components/skeletons/DashboardSkeleton';
import {
  DataTableShell,
  MetricCard,
  TenantPageHero,
} from '../components/tenant/TenantAdminUI';
import { useBranding } from '../contexts/BrandingContext';

interface OverviewStats {
  total_users: number;
  total_departments: number;
  total_courses: number;
  total_lecturers: number;
  total_rooms: number;
  total_groups: number;
  total_timetables: number;
  generated_timetables: number;
  draft_timetables: number;
  active_users: number;
}

interface UserStats {
  by_role: Record<string, number>;
  recent_signups: number;
  total_active: number;
}

interface TimetableStats {
  total_timetables: number;
  generated_timetables: number;
  draft_timetables: number;
  by_school: Record<string, number>;
  recent_generations: number;
  total_slots: number;
  total_versions: number;
}

interface ResourceStats {
  rooms: {
    total: number;
    in_use: number;
    utilization_percent: number;
    avg_capacity_usage: number;
  };
  lecturers: {
    total: number;
    assigned: number;
    unassigned: number;
    avg_hours: number;
  };
}

interface SchoolSummary {
  id: number;
  name: string;
  code: string;
  departments_count: number;
  courses: number;
  lecturers: number;
  groups: number;
  timetables: number;
  coordinator: string | null;
}

interface SystemHealth {
  health_score: number;
  status: 'healthy' | 'warning' | 'critical';
  issues: Array<{
    type: string;
    severity: string;
    count: number;
    message: string;
  }>;
  warnings: Array<{
    type: string;
    severity: string;
    count: number;
    message: string;
  }>;
  total_issues: number;
  total_warnings: number;
}

interface WeeklyStats {
  timetables_generated: number;
  users_created: number;
  courses_added: number;
  notifications_sent: number;
  period_start: string;
  period_end: string;
}

interface ViewerAnalyticsSummary {
  student_unique_viewers_7d: number;
  lecturer_unique_viewers_7d: number;
  viewer_requests_7d: number;
  avg_response_ms_7d: number;
  active_student_groups_7d: number;
  total_student_groups: number;
  inactive_student_groups_7d: number;
  group_coverage_percent_7d: number;
  estimated_student_reach_percent_7d: number;
  estimated_students_reached_7d: number;
  total_student_capacity: number;
  requests_per_viewer_7d: number;
  request_growth_percent: number;
}

interface ViewerTrendPoint {
  date: string;
  requests: number;
  student_unique_viewers: number;
  lecturer_unique_viewers: number;
}

interface ViewerTopGroup {
  group_id: number;
  group_name: string;
  size: number | null;
  requests: number;
  unique_viewers: number;
  adoption_percent: number;
}

interface ViewerTopRoute {
  route: string;
  requests: number;
}

interface ViewerAdoptionSegment {
  group_id: number;
  group_name: string;
  size: number;
  unique_viewers: number;
  adoption_percent: number;
  status: 'active' | 'inactive';
}

interface ViewerAnalytics {
  summary: ViewerAnalyticsSummary;
  daily_trend: ViewerTrendPoint[];
  top_student_groups: ViewerTopGroup[];
  adoption_segments: ViewerAdoptionSegment[];
  top_routes: ViewerTopRoute[];
  school_options: ViewerSchoolOption[];
  school_summaries: ViewerSchoolSummary[];
  by_school: Record<string, ViewerAnalyticsScope>;
}

interface ViewerAnalyticsScope {
  summary: ViewerAnalyticsSummary;
  daily_trend: ViewerTrendPoint[];
  top_student_groups: ViewerTopGroup[];
  adoption_segments: ViewerAdoptionSegment[];
  top_routes: ViewerTopRoute[];
}

interface ViewerSchoolOption {
  id: number;
  name: string;
  code: string | null;
}

interface ViewerSchoolSummary {
  school_id: number;
  school_name: string;
  school_code: string | null;
  viewer_requests_7d: number;
  active_student_groups_7d: number;
  total_student_groups: number;
  estimated_students_reached_7d: number;
  group_coverage_percent_7d: number;
}

interface RecentActivity {
  timetables: Array<{
    id: number;
    name: string;
    department: string | null;
    is_generated: boolean;
    updated_at: string | null;
  }>;
  users: Array<{
    id: number;
    username: string;
    email: string;
    role: string;
    created_at: string | null;
  }>;
  notifications: Array<{
    id: number;
    title: string;
    type: string;
    user_id: number;
    created_at: string;
  }>;
}

interface DashboardData {
  overview: OverviewStats;
  users: UserStats;
  timetables: TimetableStats;
  resources: ResourceStats;
  schools: SchoolSummary[];
  system_health: SystemHealth;
  weekly_stats: WeeklyStats;
  viewer_analytics: ViewerAnalytics;
  recent_activity: RecentActivity;
  timestamp: string;
}

const defaultViewerAnalytics: ViewerAnalytics = {
  summary: {
    student_unique_viewers_7d: 0,
    lecturer_unique_viewers_7d: 0,
    viewer_requests_7d: 0,
    avg_response_ms_7d: 0,
    active_student_groups_7d: 0,
    total_student_groups: 0,
    inactive_student_groups_7d: 0,
    group_coverage_percent_7d: 0,
    estimated_student_reach_percent_7d: 0,
    estimated_students_reached_7d: 0,
    total_student_capacity: 0,
    requests_per_viewer_7d: 0,
    request_growth_percent: 0,
  },
  daily_trend: [],
  top_student_groups: [],
  adoption_segments: [],
  top_routes: [],
  school_options: [],
  school_summaries: [],
  by_school: {},
};

// Animated live clock
const LiveClock: React.FC<{ color?: string }> = ({ color = '#ffffff' }) => {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <Typography
      fontWeight={800}
      fontFamily="monospace"
      sx={{
        fontSize: { xs: '2.6rem', md: '3.6rem' },
        letterSpacing: 6,
        color,
        lineHeight: 1,
        textShadow: '0 2px 24px rgba(0,0,0,0.20)',
      }}
    >
      {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
    </Typography>
  );
};

const buildSmoothPath = (values: number[], width: number, height: number) => {
  if (values.length === 0) {
    return '';
  }

  const maxValue = Math.max(...values, 1);
  const stepX = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((value, index) => ({
    x: index * stepX,
    y: height - (value / maxValue) * height,
  }));

  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`;
  }

  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    const controlX = (current.x + next.x) / 2;
    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
  }
  return path;
};

const buildAreaPath = (values: number[], width: number, height: number) => {
  const linePath = buildSmoothPath(values, width, height);
  if (!linePath) {
    return '';
  }
  return `${linePath} L ${width} ${height} L 0 ${height} Z`;
};

const GaugeCard: React.FC<{
  label: string;
  value: number;
  total?: number;
  subtitle: string;
  accent: string;
}> = ({ label, value, total, subtitle, accent }) => {
  const safePercent = Math.max(0, Math.min(total && total > 0 ? (value / total) * 100 : value, 100));
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (safePercent / 100) * circumference;

  return (
    <Box
      sx={{
        p: 2.5,
        borderRadius: 4,
        bgcolor: '#fff',
        border: '1px solid rgba(15, 23, 42, 0.06)',
        boxShadow: '0 18px 42px rgba(15, 23, 42, 0.08)',
        height: '100%',
      }}
    >
      <Typography variant="overline" sx={{ color: 'text.secondary', fontWeight: 700, letterSpacing: 1.4 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5, mt: 1.5 }}>
        <Box sx={{ position: 'relative', width: 96, height: 96 }}>
          <svg width="96" height="96" viewBox="0 0 96 96">
            <circle cx="48" cy="48" r={radius} fill="none" stroke="rgba(148, 163, 184, 0.18)" strokeWidth="10" />
            <circle
              cx="48"
              cy="48"
              r={radius}
              fill="none"
              stroke={accent}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              transform="rotate(-90 48 48)"
            />
          </svg>
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography variant="h5" fontWeight={900} sx={{ color: accent, lineHeight: 1 }}>
              {Math.round(safePercent)}%
            </Typography>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>
              adoption
            </Typography>
          </Box>
        </Box>

        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" fontWeight={900} sx={{ color: '#0f172a', lineHeight: 1 }}>
            {value}
          </Typography>
          {typeof total === 'number' && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              of {total} possible
            </Typography>
          )}
          <Typography variant="body2" sx={{ mt: 1.5, color: '#334155', fontWeight: 600 }}>
            {subtitle}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

const TrendPanel: React.FC<{ trend: ViewerTrendPoint[] }> = ({ trend }) => {
  const requests = trend.map((point) => point.requests);
  const students = trend.map((point) => point.student_unique_viewers);
  const lecturers = trend.map((point) => point.lecturer_unique_viewers);
  const width = 420;
  const height = 140;

  return (
    <Box
      sx={{
        p: 3,
        borderRadius: 4,
        background: 'linear-gradient(180deg, #0f172a 0%, #111827 100%)',
        color: '#fff',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <Box sx={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at top right, rgba(56, 189, 248, 0.22), transparent 38%)' }} />
      <Box sx={{ position: 'relative' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, mb: 2 }}>
          <Box>
            <Typography variant="overline" sx={{ color: 'rgba(255,255,255,0.68)', letterSpacing: 1.5 }}>
              Viewer Trend
            </Typography>
            <Typography variant="h6" fontWeight={900}>
              Smooth 7-day activity pulse
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip size="small" label="Requests" sx={{ bgcolor: 'rgba(14, 165, 233, 0.16)', color: '#7dd3fc', fontWeight: 700 }} />
            <Chip size="small" label="Students" sx={{ bgcolor: 'rgba(34, 197, 94, 0.16)', color: '#86efac', fontWeight: 700 }} />
            <Chip size="small" label="Lecturers" sx={{ bgcolor: 'rgba(251, 146, 60, 0.16)', color: '#fdba74', fontWeight: 700 }} />
          </Stack>
        </Box>

        <Box sx={{ width: '100%', overflowX: 'auto', pb: 1 }}>
          <Box sx={{ minWidth: width }}>
            <svg width="100%" height="190" viewBox={`0 0 ${width} 190`} preserveAspectRatio="none">
              {[0, 1, 2, 3].map((line) => (
                <line
                  key={line}
                  x1="0"
                  x2={width}
                  y1={24 + line * 32}
                  y2={24 + line * 32}
                  stroke="rgba(255,255,255,0.08)"
                  strokeDasharray="4 8"
                />
              ))}
              <path d={buildAreaPath(requests, width, height)} fill="rgba(14, 165, 233, 0.16)" transform="translate(0 16)" />
              <path d={buildSmoothPath(requests, width, height)} fill="none" stroke="#38bdf8" strokeWidth="4" strokeLinecap="round" transform="translate(0 16)" />
              <path d={buildSmoothPath(students, width, height)} fill="none" stroke="#4ade80" strokeWidth="3" strokeLinecap="round" transform="translate(0 16)" />
              <path d={buildSmoothPath(lecturers, width, height)} fill="none" stroke="#fb923c" strokeWidth="3" strokeLinecap="round" transform="translate(0 16)" />
              {trend.map((point, index) => {
                const stepX = trend.length > 1 ? width / (trend.length - 1) : width;
                const x = index * stepX;
                const reqMax = Math.max(...requests, 1);
                const y = 16 + height - (point.requests / reqMax) * height;
                return <circle key={point.date} cx={x} cy={y} r="4.5" fill="#38bdf8" stroke="#0f172a" strokeWidth="2" />;
              })}
            </svg>
          </Box>
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${Math.max(trend.length, 1)}, minmax(0, 1fr))`, gap: 1.25, mt: 1.5 }}>
          {trend.map((point) => (
            <Box
              key={point.date}
              sx={{
                px: 1,
                py: 1.25,
                borderRadius: 2.5,
                bgcolor: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.06)',
                minWidth: 0,
              }}
            >
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.65)' }}>
                {new Date(point.date).toLocaleDateString([], { month: 'short', day: 'numeric' })}
              </Typography>
              <Typography variant="body2" fontWeight={800} sx={{ mt: 0.5 }}>
                {point.requests} requests
              </Typography>
              <Typography variant="caption" sx={{ color: '#86efac', display: 'block', mt: 0.5 }}>
                {point.student_unique_viewers} student devices
              </Typography>
              <Typography variant="caption" sx={{ color: '#fdba74', display: 'block' }}>
                {point.lecturer_unique_viewers} lecturers
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  );
};

const AdminDashboard: React.FC = () => {
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || '#1565c0';
  const secondaryColor = branding.secondary_color || '#9c27b0';

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [selectedSchoolId, setSelectedSchoolId] = useState<string>('all');

  const fetchDashboardData = async () => {
    try {
      setRefreshing(true);
      const response = await api.get('/dashboard/');
      setData({
        ...response.data,
        viewer_analytics: {
          ...defaultViewerAnalytics,
          ...(response.data?.viewer_analytics || {}),
          summary: {
            ...defaultViewerAnalytics.summary,
            ...(response.data?.viewer_analytics?.summary || {}),
          },
          daily_trend: response.data?.viewer_analytics?.daily_trend || [],
          top_student_groups: response.data?.viewer_analytics?.top_student_groups || [],
          adoption_segments: response.data?.viewer_analytics?.adoption_segments || [],
          top_routes: response.data?.viewer_analytics?.top_routes || [],
          school_options: response.data?.viewer_analytics?.school_options || [],
          school_summaries: response.data?.viewer_analytics?.school_summaries || [],
          by_school: response.data?.viewer_analytics?.by_school || {},
        },
      });
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch dashboard data:', err);
      setError(err.response?.data?.detail || 'Failed to load dashboard data. You may need admin permissions.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(() => {
      fetchDashboardData();
    }, 30000); // Auto-refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!data) return;
    if (selectedSchoolId === 'all') return;
    const stillExists = data.viewer_analytics.school_options.some((school) => String(school.id) === selectedSchoolId);
    if (!stillExists) {
      setSelectedSchoolId('all');
    }
  }, [data, selectedSchoolId]);

  const formatDate = (dateString: string | null): string => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const getHealthColor = (status: string): string => {
    switch (status) {
      case 'healthy':
        return '#4caf50';
      case 'warning':
        return '#ff9800';
      case 'critical':
        return '#f44336';
      default:
        return '#9e9e9e';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'error':
        return <ErrorIcon color="error" />;
      case 'warning':
        return <WarningIcon color="warning" />;
      case 'info':
        return <InfoIcon color="info" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  const formatTrendPercent = (value: number): string => {
    if (value > 0) return `+${value}%`;
    return `${value}%`;
  };

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">No dashboard data available.</Alert>
      </Box>
    );
  }

  const schoolOptions = data.viewer_analytics.school_options;
  const selectedSchoolOption = schoolOptions.find((school) => String(school.id) === selectedSchoolId) || null;
  const detailedAnalytics = selectedSchoolId === 'all'
    ? {
        top_student_groups: data.viewer_analytics.top_student_groups,
        adoption_segments: data.viewer_analytics.adoption_segments,
        top_routes: data.viewer_analytics.top_routes,
      }
    : data.viewer_analytics.by_school[selectedSchoolId] || {
        summary: defaultViewerAnalytics.summary,
        daily_trend: [],
        top_student_groups: [],
        adoption_segments: [],
        top_routes: [],
      };
  const detailScopeLabel = selectedSchoolOption?.name || 'All Schools';
  const showSchoolSelector = schoolOptions.length > 1;
  const hasAggregateViewerActivity = data.viewer_analytics.summary.viewer_requests_7d > 0;
  const hasScopedViewerActivity = selectedSchoolId === 'all'
    ? hasAggregateViewerActivity
    : (data.viewer_analytics.by_school[selectedSchoolId]?.summary.viewer_requests_7d || 0) > 0;

  return (
    <Box sx={{ p: 3 }}>
      <TenantPageHero
        title={branding.name || 'TableSys'}
        description="Institution-wide oversight with clearer operational hierarchy, calmer branded surfaces, and faster access to the exceptions that matter."
        eyebrow="Institution Admin"
        icon={<BusinessIcon />}
        primaryColor={primaryColor}
        actions={(
          <Box sx={{ textAlign: { xs: 'left', md: 'right' } }}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.65)', letterSpacing: 3, textTransform: 'uppercase', mb: 1, display: 'block' }}>
              Current Time
            </Typography>
            <LiveClock color="#ffffff" />
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.82)', mt: 1 }}>
              {new Date().toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </Typography>
          </Box>
        )}
      >
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard label="Total Users" value={data.overview.total_users} helper={`${data.overview.active_users} active`} icon={<PeopleIcon />} tone="info" primaryColor={primaryColor} secondaryColor={secondaryColor} />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard label="Courses" value={data.overview.total_courses} helper={`Across ${data.overview.total_departments} departments`} icon={<BookIcon />} tone="success" primaryColor={primaryColor} secondaryColor={secondaryColor} />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard label="Timetables" value={data.overview.generated_timetables} helper={`${data.overview.draft_timetables} drafts pending`} icon={<CalendarIcon />} tone="warning" primaryColor={primaryColor} secondaryColor={secondaryColor} />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard label="Lecturers" value={data.overview.total_lecturers} helper={`${data.resources.lecturers.assigned} assigned`} icon={<PersonIcon />} tone="default" primaryColor={primaryColor} secondaryColor={secondaryColor} />
          </Grid>
        </Grid>

      </TenantPageHero>

      {/* Weekly Statistics & Resource Utilization */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Card sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom color="text.primary">
                This Week's Activity
              </Typography>
              <Divider sx={{ mb: 3 }} />
              <Grid container spacing={2}>
                {[
                  { value: data.weekly_stats.timetables_generated, label: 'Timetables Generated', color: '#1976d2', icon: <CalendarIcon /> },
                  { value: data.weekly_stats.users_created, label: 'New Users', color: '#4caf50', icon: <PeopleIcon /> },
                  { value: data.weekly_stats.courses_added, label: 'Courses Added', color: '#ff9800', icon: <BookIcon /> },
                  { value: data.weekly_stats.notifications_sent, label: 'Notifications Sent', color: '#9c27b0', icon: <InfoIcon /> }
                ].map((stat, i) => (
                  <Grid item xs={6} key={i}>
                    <Box sx={{ 
                      p: 2.5, 
                      borderRadius: 3, 
                      border: '1px solid', 
                      borderColor: 'grey.100',
                      bgcolor: 'grey.50',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 1,
                      transition: 'transform 0.2s',
                      '&:hover': { transform: 'translateY(-2px)', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', borderColor: `${stat.color}40` }
                    }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: stat.color }}>
                        {React.cloneElement(stat.icon as React.ReactElement, { fontSize: 'small' })}
                        <Typography variant="h5" fontWeight="900">
                          {stat.value}
                        </Typography>
                      </Box>
                      <Typography variant="body2" color="text.secondary" fontWeight={500}>
                        {stat.label}
                      </Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom color="text.primary">
                Resource Utilization
              </Typography>
              <Divider sx={{ mb: 3 }} />
              
              <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5, alignItems: 'center' }}>
                  <Typography variant="body1" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <RoomIcon color="primary" /> Room Utilization
                  </Typography>
                  <Typography variant="h6" fontWeight="900" color="primary.main">
                    {data.resources.rooms.utilization_percent}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={data.resources.rooms.utilization_percent}
                  sx={{ height: 10, borderRadius: 5, bgcolor: 'primary.50', '& .MuiLinearProgress-bar': { borderRadius: 5 } }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                  <Typography variant="caption" color="text.secondary" fontWeight={500}>
                    {data.resources.rooms.in_use} / {data.resources.rooms.total} rooms active
                  </Typography>
                  <Typography variant="caption" color="text.secondary" fontWeight={500}>
                    Avg Capacity: {data.resources.rooms.avg_capacity_usage}%
                  </Typography>
                </Box>
              </Box>

              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5, alignItems: 'center' }}>
                  <Typography variant="body1" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <PersonIcon color="secondary" /> Lecturer Assignment
                  </Typography>
                  <Typography variant="h6" fontWeight="900" color="secondary.main">
                    {((data.resources.lecturers.assigned / data.resources.lecturers.total) * 100).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={(data.resources.lecturers.assigned / data.resources.lecturers.total) * 100}
                  color="secondary"
                  sx={{ height: 10, borderRadius: 5, bgcolor: 'secondary.50', '& .MuiLinearProgress-bar': { borderRadius: 5 } }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                  <Typography variant="caption" color="text.secondary" fontWeight={500}>
                    {data.resources.lecturers.assigned} / {data.resources.lecturers.total} assigned
                  </Typography>
                  <Typography variant="caption" color="text.secondary" fontWeight={500}>
                    Avg Load: {data.resources.lecturers.avg_hours} hrs/week
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={7}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, height: '100%' }}>
            <Card
              sx={{
                borderRadius: 4,
                boxShadow: '0 24px 60px rgba(15, 23, 42, 0.08)',
                border: '1px solid rgba(15, 23, 42, 0.05)',
                overflow: 'hidden',
              }}
            >
              <CardContent sx={{ p: 0 }}>
                <Box
                  sx={{
                    p: 3,
                    background: 'linear-gradient(135deg, #f8fbff 0%, #eef6ff 52%, #fff7ed 100%)',
                    borderBottom: '1px solid rgba(15, 23, 42, 0.06)',
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap' }}>
                    <Box>
                      <Typography variant="overline" sx={{ color: 'primary.main', fontWeight: 800, letterSpacing: 1.5 }}>
                        Tenant Adoption
                      </Typography>
                      <Typography variant="h5" fontWeight={900} color="#0f172a">
                        Viewer Reach, Load & Adoption
                      </Typography>
                      <Typography variant="body2" sx={{ color: '#475569', mt: 0.75, maxWidth: 620 }}>
                        A clean view of how many students and lecturers are actually using the tenant portal, how hard the system is working for them, and where adoption is still missing.
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      <Chip label={`${data.viewer_analytics.summary.viewer_requests_7d} requests`} sx={{ bgcolor: '#dbeafe', color: '#1d4ed8', fontWeight: 800 }} />
                      <Chip label={`${data.viewer_analytics.summary.avg_response_ms_7d} ms avg response`} sx={{ bgcolor: '#dcfce7', color: '#15803d', fontWeight: 800 }} />
                      <Chip
                        label={`${formatTrendPercent(data.viewer_analytics.summary.request_growth_percent)} demand trend`}
                        sx={{
                          bgcolor: data.viewer_analytics.summary.request_growth_percent >= 0 ? '#ffedd5' : '#e0f2fe',
                          color: data.viewer_analytics.summary.request_growth_percent >= 0 ? '#c2410c' : '#0369a1',
                          fontWeight: 800,
                        }}
                      />
                    </Stack>
                  </Box>
                </Box>

                <Box sx={{ p: 3 }}>
                  {!hasAggregateViewerActivity && (
                    <Alert severity="info" sx={{ mb: 3 }}>
                      No recorded viewer activity was captured for this tenant in the last 7 days yet.
                    </Alert>
                  )}

                  <Grid container spacing={2.5}>
                    <Grid item xs={12} md={6}>
                      <GaugeCard
                        label="Student Group Adoption"
                        value={data.viewer_analytics.summary.active_student_groups_7d}
                        total={data.viewer_analytics.summary.total_student_groups}
                        subtitle={`${data.viewer_analytics.summary.inactive_student_groups_7d} groups still quiet in the last 7 days`}
                        accent="#2563eb"
                      />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <GaugeCard
                        label="Estimated Student Reach"
                        value={data.viewer_analytics.summary.estimated_students_reached_7d}
                        total={data.viewer_analytics.summary.total_student_capacity}
                        subtitle={`${data.viewer_analytics.summary.student_unique_viewers_7d} unique student viewer devices seen this week`}
                        accent="#f97316"
                      />
                    </Grid>
                  </Grid>

                  <Grid container spacing={2} sx={{ mt: 0.5, mb: 3 }}>
                    {[
                      {
                        label: 'Student Viewer Devices',
                        value: data.viewer_analytics.summary.student_unique_viewers_7d,
                        note: 'Anonymous devices seen in student portal',
                        color: '#2563eb',
                      },
                      {
                        label: 'Lecturer Viewers',
                        value: data.viewer_analytics.summary.lecturer_unique_viewers_7d,
                        note: 'Authenticated lecturers using viewer flows',
                        color: '#7c3aed',
                      },
                      {
                        label: 'Requests Per Viewer',
                        value: data.viewer_analytics.summary.requests_per_viewer_7d,
                        note: 'Average load per active viewer',
                        color: '#059669',
                      },
                      {
                        label: 'Group Coverage',
                        value: `${data.viewer_analytics.summary.group_coverage_percent_7d}%`,
                        note: `${data.viewer_analytics.summary.active_student_groups_7d} of ${data.viewer_analytics.summary.total_student_groups} groups active`,
                        color: '#ea580c',
                      },
                    ].map((item) => (
                      <Grid item xs={12} sm={6} md={3} key={item.label}>
                        <Box
                          sx={{
                            p: 2.25,
                            borderRadius: 3,
                            bgcolor: '#fff',
                            border: '1px solid rgba(15, 23, 42, 0.06)',
                            height: '100%',
                            boxShadow: '0 12px 30px rgba(15, 23, 42, 0.05)',
                          }}
                        >
                          <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: item.color, mb: 1.25 }} />
                          <Typography variant="h5" fontWeight={900} sx={{ color: '#0f172a', lineHeight: 1.1 }}>
                            {item.value}
                          </Typography>
                          <Typography variant="subtitle2" fontWeight={800} sx={{ mt: 1, color: '#334155' }}>
                            {item.label}
                          </Typography>
                          <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mt: 0.75 }}>
                            {item.note}
                          </Typography>
                        </Box>
                      </Grid>
                    ))}
                  </Grid>

                  {showSchoolSelector && (
                    <Box sx={{ mb: 3 }}>
                      <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ lg: 'center' }}>
                        <Box>
                          <Typography variant="subtitle2" sx={{ fontWeight: 800, color: '#0f172a' }}>
                            School comparison
                          </Typography>
                          <Typography variant="body2" sx={{ color: '#64748b', mt: 0.5 }}>
                            Compare 7-day adoption coverage across schools, then use the filter to inspect detailed hotspots for one school at a time.
                          </Typography>
                        </Box>
                        <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 220 } }}>
                          <InputLabel id="viewer-school-scope-label">School Scope</InputLabel>
                          <Select
                            labelId="viewer-school-scope-label"
                            value={selectedSchoolId}
                            label="School Scope"
                            onChange={(event) => setSelectedSchoolId(event.target.value)}
                          >
                            <MenuItem value="all">All Schools</MenuItem>
                            {schoolOptions.map((school) => (
                              <MenuItem key={school.id} value={String(school.id)}>
                                {school.name}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Stack>

                      <Grid container spacing={1.5} sx={{ mt: 1.5 }}>
                        {data.viewer_analytics.school_summaries.map((school) => (
                          <Grid item xs={12} sm={6} xl={4} key={school.school_id}>
                            <Box
                              sx={{
                                p: 2,
                                borderRadius: 3,
                                border: selectedSchoolId === String(school.school_id)
                                  ? '1px solid rgba(37, 99, 235, 0.3)'
                                  : '1px solid rgba(15, 23, 42, 0.08)',
                                bgcolor: selectedSchoolId === String(school.school_id)
                                  ? 'rgba(219, 234, 254, 0.55)'
                                  : 'rgba(255,255,255,0.72)',
                                boxShadow: selectedSchoolId === String(school.school_id)
                                  ? '0 12px 24px rgba(37, 99, 235, 0.08)'
                                  : 'none',
                              }}
                            >
                              <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="flex-start">
                                <Box sx={{ minWidth: 0 }}>
                                  <Typography variant="subtitle2" sx={{ fontWeight: 800 }} noWrap>
                                    {school.school_name}
                                  </Typography>
                                  <Typography variant="caption" sx={{ color: '#64748b' }}>
                                    {school.school_code || 'School scope'}
                                  </Typography>
                                </Box>
                                <Chip
                                  size="small"
                                  label={`${school.group_coverage_percent_7d}% coverage`}
                                  sx={{ bgcolor: '#eff6ff', color: '#1d4ed8', fontWeight: 800 }}
                                />
                              </Stack>
                              <Stack direction="row" spacing={1.5} sx={{ mt: 1.5 }} useFlexGap flexWrap="wrap">
                                <Typography variant="caption" sx={{ color: '#334155' }}>
                                  {school.viewer_requests_7d} requests
                                </Typography>
                                <Typography variant="caption" sx={{ color: '#334155' }}>
                                  {school.active_student_groups_7d}/{school.total_student_groups} groups active
                                </Typography>
                                <Typography variant="caption" sx={{ color: '#334155' }}>
                                  {school.estimated_students_reached_7d} students reached
                                </Typography>
                              </Stack>
                            </Box>
                          </Grid>
                        ))}
                      </Grid>
                    </Box>
                  )}

                  <TrendPanel trend={data.viewer_analytics.daily_trend} />
                </Box>
              </CardContent>
            </Card>
          </Box>
        </Grid>

        <Grid item xs={12} lg={5}>
          <Card sx={{ borderRadius: 4, boxShadow: '0 24px 60px rgba(15, 23, 42, 0.08)', height: '100%', border: '1px solid rgba(15, 23, 42, 0.05)' }}>
            <CardContent sx={{ p: 3 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="space-between" alignItems={{ sm: 'center' }}>
                <Box>
                  <Typography variant="h6" fontWeight="bold" gutterBottom color="text.primary">
                    Adoption Hotspots
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#64748b' }}>
                    {detailScopeLabel} • last 7 days
                  </Typography>
                </Box>
                {showSchoolSelector && (
                  <Chip
                    size="small"
                    label={selectedSchoolId === 'all' ? 'Aggregate tenant view' : `${detailScopeLabel} detail view`}
                    sx={{ bgcolor: 'rgba(219, 234, 254, 0.72)', color: '#1d4ed8', fontWeight: 800 }}
                  />
                )}
              </Stack>
              <Divider sx={{ mb: 3 }} />
              {!hasScopedViewerActivity && (
                <Alert severity="info" sx={{ mb: 2.5 }}>
                  No recorded viewer activity was captured for {selectedSchoolId === 'all' ? 'this tenant' : detailScopeLabel} in the last 7 days yet.
                </Alert>
              )}
              <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1.5 }}>
                Group Adoption Board
              </Typography>
              <Stack spacing={1.25} sx={{ mb: 3 }}>
                {detailedAnalytics.adoption_segments.length === 0 ? (
                  <Box sx={{ p: 2, borderRadius: 2.5, bgcolor: 'grey.50' }}>
                    <Typography variant="body2" color="text.secondary">
                      No student viewer traffic has been recorded for {selectedSchoolId === 'all' ? 'this tenant' : detailScopeLabel} in the last 7 days yet.
                    </Typography>
                  </Box>
                ) : detailedAnalytics.adoption_segments.map((group) => (
                  <Box
                    key={group.group_id}
                    sx={{
                      p: 1.75,
                      borderRadius: 3,
                      bgcolor: group.status === 'active' ? '#f8fafc' : '#fff7ed',
                      border: '1px solid',
                      borderColor: group.status === 'active' ? 'rgba(37, 99, 235, 0.12)' : 'rgba(249, 115, 22, 0.16)',
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography variant="subtitle2" fontWeight={800} noWrap>
                          {group.group_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {group.unique_viewers} viewers{group.size ? ` of ${group.size} students` : ''} • {group.status === 'active' ? 'active this week' : 'not yet active'}
                        </Typography>
                      </Box>
                      <Chip
                        size="small"
                        label={`${Math.round(group.adoption_percent)}%`}
                        sx={{
                          bgcolor: group.status === 'active' ? '#dbeafe' : '#ffedd5',
                          color: group.status === 'active' ? '#1d4ed8' : '#c2410c',
                          fontWeight: 800,
                        }}
                      />
                    </Box>
                    <Box sx={{ mt: 1.25 }}>
                      <LinearProgress
                        variant="determinate"
                        value={Math.max(0, Math.min(group.adoption_percent, 100))}
                        sx={{
                          height: 8,
                          borderRadius: 999,
                          bgcolor: group.status === 'active' ? 'rgba(37, 99, 235, 0.10)' : 'rgba(249, 115, 22, 0.12)',
                          '& .MuiLinearProgress-bar': {
                            borderRadius: 999,
                            bgcolor: group.status === 'active' ? '#2563eb' : '#f97316',
                          },
                        }}
                      />
                    </Box>
                  </Box>
                ))}
              </Stack>

              <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1.5 }}>
                Highest Traffic Groups
              </Typography>
              <List dense sx={{ mb: 2 }}>
                {detailedAnalytics.top_student_groups.length === 0 ? (
                  <ListItem>
                    <ListItemText primary={`No public student viewer traffic found for ${selectedSchoolId === 'all' ? 'this tenant' : detailScopeLabel} in the last 7 days.`} />
                  </ListItem>
                ) : detailedAnalytics.top_student_groups.map((group) => (
                  <ListItem key={group.group_id} disableGutters>
                    <ListItemText
                      primary={group.group_name}
                      secondary={`${group.unique_viewers} devices • ${group.requests} requests • ${Math.round(group.adoption_percent)}% estimated reach${group.size ? ` • cohort ${group.size}` : ''}`}
                    />
                  </ListItem>
                ))}
              </List>

              <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1.5 }}>
                Most Used Viewer Routes
              </Typography>
              <List dense>
                {detailedAnalytics.top_routes.length === 0 ? (
                  <ListItem>
                    <ListItemText primary={`No viewer route data found for ${selectedSchoolId === 'all' ? 'this tenant' : detailScopeLabel} in the last 7 days.`} />
                  </ListItem>
                ) : detailedAnalytics.top_routes.map((route, index) => (
                  <ListItem key={route.route} disableGutters sx={{ alignItems: 'flex-start' }}>
                    <ListItemIcon sx={{ minWidth: 34, mt: 0.25 }}>
                      <Box sx={{ width: 24, height: 24, borderRadius: 2, bgcolor: '#e0f2fe', color: '#0369a1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', fontWeight: 900 }}>
                        {index + 1}
                      </Box>
                    </ListItemIcon>
                    <ListItemText primary={route.route} secondary={`${route.requests} requests in the last 7 days`} />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Users by Role & Timetables */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Card sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom color="text.primary">
                Registered User Accounts
              </Typography>
              <Divider sx={{ mb: 3 }} />
              <Grid container spacing={2}>
                {Object.entries(data.users.by_role).map(([role, count], idx) => {
                   const colors = ['#3f51b5', '#009688', '#ff9800', '#f44336'];
                   const color = colors[idx % colors.length];
                   return (
                      <Grid item xs={6} key={role}>
                        <Box sx={{ p: 2, borderRadius: 2, borderLeft: '4px solid', borderColor: color, bgcolor: 'grey.50' }}>
                          <Typography variant="h4" fontWeight="900" sx={{ color }}>
                            {count}
                          </Typography>
                          <Typography variant="subtitle2" color="text.secondary" sx={{ textTransform: 'capitalize', mt: 0.5 }}>
                            {role.replace('_', ' ')} Accounts
                          </Typography>
                        </Box>
                      </Grid>
                   );
                })}
              </Grid>
              <Box sx={{ mt: 3, p: 2, bgcolor: 'success.50', borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <TrendingUpIcon color="success" />
                <Typography variant="body2" fontWeight={600} color="success.dark">
                  +{data.users.recent_signups} new accounts registered in the last 30 days
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom color="text.primary">
                Scheduling Engine
              </Typography>
              <Divider sx={{ mb: 3 }} />
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box sx={{ p: 3, borderRadius: 3, bgcolor: 'primary.50', textAlign: 'center', height: '100%' }}>
                    <Typography variant="h3" color="primary.main" fontWeight="900">
                      {data.timetables.total_slots}
                    </Typography>
                    <Typography variant="subtitle2" color="primary.dark" sx={{ mt: 1 }}>
                      Total Time Slots
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ p: 3, borderRadius: 3, bgcolor: 'secondary.50', textAlign: 'center', height: '100%' }}>
                    <Typography variant="h3" color="secondary.main" fontWeight="900">
                      {data.timetables.total_versions}
                    </Typography>
                    <Typography variant="subtitle2" color="secondary.dark" sx={{ mt: 1 }}>
                      Stored Versions
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12}>
                  <Box sx={{ mt: 1, p: 2, bgcolor: 'info.50', borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <CheckCircleIcon color="info" />
                    <Typography variant="body2" fontWeight={600} color="info.dark">
                      {data.timetables.recent_generations} successful generations this week
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Schools Summary Table */}
      <DataTableShell
        title="Schools Summary"
        description="Cross-school operational coverage, coordinator assignment, and scheduling footprint."
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
      >
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow sx={{ bgcolor: 'grey.50' }}>
                  <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>School</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 700, color: 'text.secondary' }}>Code</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 700, color: 'text.secondary' }}>Depts</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 700, color: 'text.secondary' }}>Courses</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 700, color: 'text.secondary' }}>Lecturers</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 700, color: 'text.secondary' }}>Groups</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 700, color: 'text.secondary' }}>Timetables</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: 'text.secondary' }}>Coordinator</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.schools.map((school) => (
                  <TableRow key={school.id} hover sx={{ '&:last-child td': { border: 0 } }}>
                    <TableCell sx={{ fontWeight: 600 }}>{school.name}</TableCell>
                    <TableCell align="center">
                      <Chip label={school.code} size="small" sx={{ fontWeight: 700, bgcolor: 'primary.50', color: 'primary.main' }} />
                    </TableCell>
                    <TableCell align="center">{school.departments_count}</TableCell>
                    <TableCell align="center">{school.courses}</TableCell>
                    <TableCell align="center">{school.lecturers}</TableCell>
                    <TableCell align="center">{school.groups}</TableCell>
                    <TableCell align="center">
                      <Typography fontWeight={600} color="primary">{school.timetables}</Typography>
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{school.coordinator || 'Unassigned'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
      </DataTableShell>

      {/* Recent Activity */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Recent Timetables
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <List disablePadding>
                {data.recent_activity.timetables.slice(0, 5).map((tt, idx) => (
                  <ListItem key={tt.id} divider={idx < 4} sx={{ px: 0, py: 1.5 }}>
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      {tt.is_generated ? (
                        <Box sx={{ p: 1, borderRadius: '50%', bgcolor: 'success.50' }}>
                           <CheckCircleIcon color="success" fontSize="small" />
                        </Box>
                      ) : (
                        <Box sx={{ p: 1, borderRadius: '50%', bgcolor: 'grey.100' }}>
                           <CalendarIcon color="disabled" fontSize="small" />
                        </Box>
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={<Typography variant="subtitle2" fontWeight={600}>{tt.name}</Typography>}
                      secondary={<Typography variant="caption" color="text.secondary">{tt.department || 'N/A'} • {formatDate(tt.updated_at)}</Typography>}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                New Users
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <List disablePadding>
                {data.recent_activity.users.slice(0, 5).map((user, idx) => (
                  <ListItem key={user.id} divider={idx < 4} sx={{ px: 0, py: 1.5 }}>
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      <Box sx={{ p: 1, borderRadius: '50%', bgcolor: 'primary.50' }}>
                         <PersonIcon color="primary" fontSize="small" />
                      </Box>
                    </ListItemIcon>
                    <ListItemText
                      primary={<Typography variant="subtitle2" fontWeight={600}>{user.username}</Typography>}
                      secondary={<Typography variant="caption" color="text.secondary" sx={{ textTransform: 'capitalize' }}>{user.role} • {formatDate(user.created_at)}</Typography>}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                System Notifications
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <List disablePadding>
                {data.recent_activity.notifications.slice(0, 5).map((notif, idx) => (
                  <ListItem key={notif.id} divider={idx < 4} sx={{ px: 0, py: 1.5 }}>
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      <Box sx={{ p: 1, borderRadius: '50%', bgcolor: 'grey.50' }}>
                         {getSeverityIcon(notif.type)}
                      </Box>
                    </ListItemIcon>
                    <ListItemText
                      primary={<Typography variant="subtitle2" fontWeight={600}>{notif.title}</Typography>}
                      secondary={<Typography variant="caption" color="text.secondary">{formatDate(notif.created_at)}</Typography>}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Footer Timestamp */}
      <Box sx={{ mt: 3, textAlign: 'center' }}>
        <Typography variant="caption" color="text.secondary" fontWeight={500}>
          🟢 Dashboard is Live. Data auto-updates every 30 seconds. Last synced: {formatDate(data.timestamp)}
        </Typography>
      </Box>
    </Box>
  );
};

export default AdminDashboard;
