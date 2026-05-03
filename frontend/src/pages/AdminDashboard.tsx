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
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  TrendingUp as TrendingUpIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import api from '../api';
import DashboardSkeleton from '../components/skeletons/DashboardSkeleton';

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
  by_department: Record<string, number>;
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

interface DepartmentSummary {
  id: number;
  name: string;
  code: string;
  courses: number;
  lecturers: number;
  groups: number;
  timetables: number;
  hod: string | null;
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
  departments: DepartmentSummary[];
  system_health: SystemHealth;
  weekly_stats: WeeklyStats;
  recent_activity: RecentActivity;
  timestamp: string;
}

const AdminDashboard: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchDashboardData = async () => {
    try {
      setRefreshing(true);
      const response = await api.get('/dashboard/');
      setData(response.data);
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
  }, []);

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

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          Admin Dashboard
        </Typography>
        <Tooltip title="Refresh Dashboard">
          <IconButton onClick={fetchDashboardData} disabled={refreshing}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>he
      </Box>

      {/* System Health Banner */}
      <Card sx={{ mb: 3, borderLeft: 4, borderColor: getHealthColor(data.system_health.status) }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={3}>
              <Typography variant="h6" gutterBottom>
                System Health
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                  <CircularProgress
                    variant="determinate"
                    value={data.system_health.health_score}
                    size={80}
                    sx={{ color: getHealthColor(data.system_health.status) }}
                  />
                  <Box
                    sx={{
                      top: 0,
                      left: 0,
                      bottom: 0,
                      right: 0,
                      position: 'absolute',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Typography variant="h6" component="div" color="text.secondary">
                      {data.system_health.health_score}
                    </Typography>
                  </Box>
                </Box>
                <Box>
                  <Chip
                    label={data.system_health.status.toUpperCase()}
                    color={
                      data.system_health.status === 'healthy'
                        ? 'success'
                        : data.system_health.status === 'warning'
                        ? 'warning'
                        : 'error'
                    }
                    size="small"
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {data.system_health.total_issues} Issues • {data.system_health.total_warnings} Warnings
                  </Typography>
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} md={9}>
              {data.system_health.issues.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" color="error" gutterBottom>
                    Critical Issues:
                  </Typography>
                  {data.system_health.issues.map((issue, idx) => (
                    <Alert key={idx} severity="error" sx={{ mb: 1 }}>
                      {issue.message}
                    </Alert>
                  ))}
                </Box>
              )}
              {data.system_health.warnings.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" color="warning.main" gutterBottom>
                    Warnings:
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ gap: 1 }}>
                    {data.system_health.warnings.slice(0, 3).map((warning, idx) => (
                      <Chip
                        key={idx}
                        icon={getSeverityIcon(warning.severity)}
                        label={warning.message}
                        size="small"
                        variant="outlined"
                      />
                    ))}
                  </Stack>
                </Box>
              )}
              {data.system_health.issues.length === 0 && data.system_health.warnings.length === 0 && (
                <Alert severity="success">All systems operational. No issues detected.</Alert>
              )}
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Overview Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: '#1976d2', color: 'white' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="h4" fontWeight="bold">
                    {data.overview.total_users}
                  </Typography>
                  <Typography variant="body2">Total Users</Typography>
                  <Typography variant="caption">
                    {data.overview.active_users} active
                  </Typography>
                </Box>
                <PeopleIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: '#2e7d32', color: 'white' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="h4" fontWeight="bold">
                    {data.overview.total_courses}
                  </Typography>
                  <Typography variant="body2">Courses</Typography>
                  <Typography variant="caption">
                    {data.overview.total_departments} departments
                  </Typography>
                </Box>
                <BookIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: '#ed6c02', color: 'white' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="h4" fontWeight="bold">
                    {data.overview.generated_timetables}
                  </Typography>
                  <Typography variant="body2">Generated Timetables</Typography>
                  <Typography variant="caption">
                    {data.overview.draft_timetables} drafts
                  </Typography>
                </Box>
                <CalendarIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: '#9c27b0', color: 'white' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="h4" fontWeight="bold">
                    {data.overview.total_lecturers}
                  </Typography>
                  <Typography variant="body2">Lecturers</Typography>
                  <Typography variant="caption">
                    {data.resources.lecturers.assigned} assigned
                  </Typography>
                </Box>
                <PersonIcon sx={{ fontSize: 48, opacity: 0.7 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Weekly Statistics & Resource Utilization */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                This Week
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="h5" color="primary" fontWeight="bold">
                      {data.weekly_stats.timetables_generated}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Timetables Generated
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="h5" color="primary" fontWeight="bold">
                      {data.weekly_stats.users_created}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      New Users
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="h5" color="primary" fontWeight="bold">
                      {data.weekly_stats.courses_added}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Courses Added
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="h5" color="primary" fontWeight="bold">
                      {data.weekly_stats.notifications_sent}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Notifications Sent
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Resource Utilization
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">
                    <RoomIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                    Room Utilization
                  </Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {data.resources.rooms.utilization_percent}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={data.resources.rooms.utilization_percent}
                  sx={{ height: 8, borderRadius: 1 }}
                />
                <Typography variant="caption" color="text.secondary">
                  {data.resources.rooms.in_use}/{data.resources.rooms.total} rooms in use • Avg capacity:{' '}
                  {data.resources.rooms.avg_capacity_usage}%
                </Typography>
              </Box>
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">
                    <PersonIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                    Lecturer Assignment
                  </Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {((data.resources.lecturers.assigned / data.resources.lecturers.total) * 100).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={(data.resources.lecturers.assigned / data.resources.lecturers.total) * 100}
                  sx={{ height: 8, borderRadius: 1 }}
                  color="secondary"
                />
                <Typography variant="caption" color="text.secondary">
                  {data.resources.lecturers.assigned}/{data.resources.lecturers.total} lecturers assigned • Avg hours:{' '}
                  {data.resources.lecturers.avg_hours}h/week
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Users by Role */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Users by Role
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Grid container spacing={2}>
                {Object.entries(data.users.by_role).map(([role, count]) => (
                  <Grid item xs={6} key={role}>
                    <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                      <Typography variant="h4" color="primary" fontWeight="bold">
                        {count}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
                        {role}s
                      </Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
              <Box sx={{ mt: 2, p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                <Typography variant="body2">
                  <TrendingUpIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5, color: 'success.main' }} />
                  {data.users.recent_signups} new users in the last 30 days
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Timetable Statistics
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1, textAlign: 'center' }}>
                    <Typography variant="h4" color="primary" fontWeight="bold">
                      {data.timetables.total_slots}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Slots
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1, textAlign: 'center' }}>
                    <Typography variant="h4" color="primary" fontWeight="bold">
                      {data.timetables.total_versions}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Versions
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12}>
                  <Box sx={{ p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="body2">
                      <CheckCircleIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5, color: 'success.main' }} />
                      {data.timetables.recent_generations} timetables generated in the last 7 days
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Department Summary Table */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Department Summary
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                  <TableCell><strong>Department</strong></TableCell>
                  <TableCell align="center"><strong>Code</strong></TableCell>
                  <TableCell align="center"><strong>Courses</strong></TableCell>
                  <TableCell align="center"><strong>Lecturers</strong></TableCell>
                  <TableCell align="center"><strong>Groups</strong></TableCell>
                  <TableCell align="center"><strong>Timetables</strong></TableCell>
                  <TableCell><strong>HOD</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.departments.map((dept) => (
                  <TableRow key={dept.id} hover>
                    <TableCell>{dept.name}</TableCell>
                    <TableCell align="center">
                      <Chip label={dept.code} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell align="center">{dept.courses}</TableCell>
                    <TableCell align="center">{dept.lecturers}</TableCell>
                    <TableCell align="center">{dept.groups}</TableCell>
                    <TableCell align="center">{dept.timetables}</TableCell>
                    <TableCell>{dept.hod || '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Timetables
              </Typography>
              <Divider sx={{ mb: 1 }} />
              <List dense>
                {data.recent_activity.timetables.slice(0, 5).map((tt) => (
                  <ListItem key={tt.id}>
                    <ListItemIcon>
                      {tt.is_generated ? (
                        <CheckCircleIcon color="success" fontSize="small" />
                      ) : (
                        <CalendarIcon color="disabled" fontSize="small" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={tt.name}
                      secondary={`${tt.department || 'N/A'} • ${formatDate(tt.updated_at)}`}
                      primaryTypographyProps={{ fontSize: 14 }}
                      secondaryTypographyProps={{ fontSize: 11 }}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Users
              </Typography>
              <Divider sx={{ mb: 1 }} />
              <List dense>
                {data.recent_activity.users.slice(0, 5).map((user) => (
                  <ListItem key={user.id}>
                    <ListItemIcon>
                      <PeopleIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={user.username}
                      secondary={`${user.role} • ${formatDate(user.created_at)}`}
                      primaryTypographyProps={{ fontSize: 14 }}
                      secondaryTypographyProps={{ fontSize: 11 }}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Notifications
              </Typography>
              <Divider sx={{ mb: 1 }} />
              <List dense>
                {data.recent_activity.notifications.slice(0, 5).map((notif) => (
                  <ListItem key={notif.id}>
                    <ListItemIcon>
                      {getSeverityIcon(notif.type)}
                    </ListItemIcon>
                    <ListItemText
                      primary={notif.title}
                      secondary={formatDate(notif.created_at)}
                      primaryTypographyProps={{ fontSize: 14 }}
                      secondaryTypographyProps={{ fontSize: 11 }}
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
        <Typography variant="caption" color="text.secondary">
          Last updated: {formatDate(data.timestamp)}
        </Typography>
      </Box>
    </Box>
  );
};

export default AdminDashboard;
