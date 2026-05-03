// OWNER: Agent Delta | PARALLEL_WORKPLAN.md — Analytics & ROI Dashboards
// SCOPE: Read-only. No writes. Only reads GET /api/v1/timetables/active/analytics
//
// TimetableAnalytics.tsx
// ────────────────────────────────────────────────────────────────────────────
// Premium analytics dashboard for the active timetable.
// Renders inside DashboardPage when a timetable is active.
//
// Data source: GET /api/v1/timetables/active/analytics
// All data is read-only — no mutations performed here.

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Chip,
  Paper,
  alpha,
  Alert,
  IconButton,
  Tooltip,
  Divider,
  Stack,
} from '@mui/material';
import {
  School as SchoolIcon,
  MeetingRoom as RoomIcon,
  Person as PersonIcon,
  TrendingUp as TrendingUpIcon,
  AccessTime as AccessTimeIcon,
  Refresh as RefreshIcon,
  AutoGraph as AutoGraphIcon,
  Groups as GroupsIcon,
  Schedule as ScheduleIcon,
  Lightbulb as InsightIcon,
  CheckCircleOutline as OkIcon,
  WarningAmber as WarnIcon,
  ErrorOutline as ErrIcon,
  MenuBook as CourseIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { useBranding } from '../contexts/BrandingContext';
import api from '../api';
import AnalyticsSkeleton from './skeletons/AnalyticsSkeleton';

// ────────────────────────────────────────────────────────────────────────────
// Types — mirror AnalyticsService response exactly
// ────────────────────────────────────────────────────────────────────────────

interface RoomUtilization {
  room_id: number;
  room_name: string;
  building: string;
  capacity: number;
  room_type: string;
  slots_used: number;
  utilization_rate: number;
  status: string;
}

interface LecturerWorkload {
  lecturer_id: number;
  lecturer_name: string;
  department: string;
  total_hours: number;
  max_hours: number;
  workload_percentage: number;
  status: string;
}

interface CourseDistribution {
  department: string;
  course_count: number;
  total_hours: number;
  percentage: number;
}

interface TimeSlotData {
  count: number;
  percentage: number;
  time_range: string;
}

interface DayDistributionData {
  day_index: number;
  day_name: string;
  short_label: string;
  count: number;
  percentage: number;
}

interface TimetableSlotLite {
  day_of_week: number;
}

interface TimetableWithSlotsLite {
  id: number;
  slots: TimetableSlotLite[];
}

interface AnalyticsData {
  timetable_id: number;
  timetable_name: string;
  room_utilization: RoomUtilization[];
  lecturer_workload: LecturerWorkload[];
  course_distribution: CourseDistribution[];
  time_slot_utilization: {
    morning: TimeSlotData;
    afternoon: TimeSlotData;
    evening: TimeSlotData;
  };
  day_distribution: DayDistributionData[];
  summary: {
    total_slots: number;
    unique_courses: number;
    unique_rooms: number;
    unique_lecturers: number;
    unique_groups: number;
    total_contact_hours: number;
  };
  warnings: {
    total: number;
    largest_overflow: number;
    capacity_fallbacks: Array<{
      slot_id: number;
      course_code: string;
      course_name: string;
      room_name: string;
      room_capacity: number;
      required_size: number;
      overflow: number;
      day_of_week: number;
      start_time: string;
      end_time: string;
      session_type: string;
      group_names: string[];
      group_count: number;
    }>;
  };
}

const EMPTY_TIME_SLOT: TimeSlotData = {
  count: 0,
  percentage: 0,
  time_range: '',
};

const EMPTY_WARNINGS: AnalyticsData['warnings'] = {
  total: 0,
  largest_overflow: 0,
  capacity_fallbacks: [],
};

function buildDayDistributionFromSlots(slots: TimetableSlotLite[]): DayDistributionData[] {
  const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  const counts = [0, 0, 0, 0, 0];

  for (const slot of slots) {
    const dayIndex = normalizeDayIndex(slot?.day_of_week);
    if (dayIndex !== null) {
      counts[dayIndex] += 1;
    }
  }

  const total = counts.reduce((sum, count) => sum + count, 0);

  return counts.map((count, index) => ({
    day_index: index,
    day_name: dayNames[index],
    short_label: dayNames[index].slice(0, 3),
    count,
    percentage: total > 0 ? Number(((count / total) * 100).toFixed(1)) : 0,
  }));
}

function normalizeDayIndex(dayValue: unknown): number | null {
  const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

  if (dayValue === null || dayValue === undefined) {
    return null;
  }

  if (typeof dayValue === 'string') {
    const text = dayValue.trim();
    if (!text) {
      return null;
    }

    if (/^\d+$/.test(text)) {
      dayValue = Number(text);
    } else {
      const lowered = text.toLowerCase();
      const matchedIndex = dayNames.findIndex(
        (dayName) => lowered === dayName.toLowerCase() || lowered === dayName.slice(0, 3).toLowerCase(),
      );
      return matchedIndex >= 0 ? matchedIndex : null;
    }
  }

  if (typeof dayValue === 'number' && Number.isFinite(dayValue)) {
    const dayInt = Math.trunc(dayValue);
    if (dayInt >= 0 && dayInt < dayNames.length) {
      return dayInt;
    }
    if (dayInt >= 1 && dayInt <= dayNames.length) {
      return dayInt - 1;
    }
  }

  return null;
}

function normalizeAnalyticsData(raw: Partial<AnalyticsData> | null | undefined): AnalyticsData {
  return {
    timetable_id: raw?.timetable_id ?? 0,
    timetable_name: raw?.timetable_name ?? 'Active Timetable',
    room_utilization: raw?.room_utilization ?? [],
    lecturer_workload: raw?.lecturer_workload ?? [],
    course_distribution: raw?.course_distribution ?? [],
    time_slot_utilization: {
      morning: raw?.time_slot_utilization?.morning ?? { ...EMPTY_TIME_SLOT, time_range: '07:00 - 12:00' },
      afternoon: raw?.time_slot_utilization?.afternoon ?? { ...EMPTY_TIME_SLOT, time_range: '12:00 - 17:00' },
      evening: raw?.time_slot_utilization?.evening ?? { ...EMPTY_TIME_SLOT, time_range: '17:00 - 20:00' },
    },
    day_distribution: raw?.day_distribution ?? [],
    summary: {
      total_slots: raw?.summary?.total_slots ?? 0,
      unique_courses: raw?.summary?.unique_courses ?? 0,
      unique_rooms: raw?.summary?.unique_rooms ?? 0,
      unique_lecturers: raw?.summary?.unique_lecturers ?? 0,
      unique_groups: raw?.summary?.unique_groups ?? 0,
      total_contact_hours: raw?.summary?.total_contact_hours ?? 0,
    },
    warnings: raw?.warnings ?? EMPTY_WARNINGS,
  };
}

// ────────────────────────────────────────────────────────────────────────────
// Utility helpers
// ────────────────────────────────────────────────────────────────────────────

const BRAND_PALETTE = ['#003366', '#FF8C00', '#4A90E2', '#2e7d32', '#9c27b0', '#d32f2f'];

function dayLabel(dayIndex: number): string {
  return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][dayIndex] || `Day ${dayIndex + 1}`;
}

function statusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'overloaded':
    case 'high':     return '#d32f2f';
    case 'moderate': return '#ed6c02';
    case 'low':
    case 'light':    return '#2e7d32';
    case 'minimal':  return '#757575';
    default:         return '#757575';
  }
}

function utilizationColor(rate: number): string {
  if (rate >= 80) return '#d32f2f';
  if (rate >= 50) return '#ed6c02';
  if (rate >= 20) return '#2e7d32';
  return '#9e9e9e';
}

function dayLoadColor(percentageOfPeak: number): string {
  if (percentageOfPeak >= 80) return '#d32f2f';
  if (percentageOfPeak >= 45) return '#ed6c02';
  return '#2e7d32';
}

function StatusIcon({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === 'overloaded' || s === 'high')
    return <ErrIcon sx={{ fontSize: 14, color: '#d32f2f' }} />;
  if (s === 'moderate')
    return <WarnIcon sx={{ fontSize: 14, color: '#ed6c02' }} />;
  return <OkIcon sx={{ fontSize: 14, color: '#2e7d32' }} />;
}

// ────────────────────────────────────────────────────────────────────────────
// Sub-components
// ────────────────────────────────────────────────────────────────────────────

/** Animated counter that ticks up to a target value */
const AnimatedNumber: React.FC<{ value: number; duration?: number }> = ({
  value,
  duration = 800,
}) => {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = value / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= value) {
        setDisplay(value);
        clearInterval(timer);
      } else {
        setDisplay(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [value, duration]);
  return <>{display}</>;
};

/** Single KPI card in the summary strip */
const KpiCard: React.FC<{
  label: string;
  value: number;
  unit?: string;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}> = ({ label, value, unit = '', icon, color, subtitle }) => (
  <Card
    elevation={0}
    sx={{
      border: '1px solid',
      borderColor: 'divider',
      borderRadius: 3,
      height: '100%',
      position: 'relative',
      overflow: 'hidden',
      transition: 'transform 0.22s ease, box-shadow 0.22s ease',
      '&:hover': {
        transform: 'translateY(-3px)',
        boxShadow: `0 8px 28px ${color}30`,
      },
      '&::before': {
        content: '""',
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        background: `linear-gradient(90deg, ${color}, ${color}88)`,
      },
    }}
  >
    <CardContent sx={{ pt: 2.5, pb: '16px !important' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
        <Box sx={{ p: 1, borderRadius: 2, bgcolor: alpha(color, 0.1), color }}>
          {icon}
        </Box>
      </Box>
      <Typography variant="h4" fontWeight={800} sx={{ color, lineHeight: 1, mb: 0.5 }}>
        <AnimatedNumber value={value} />
        {unit && (
          <Typography component="span" variant="body2" color="text.secondary" fontWeight={500} sx={{ ml: 0.5 }}>
            {unit}
          </Typography>
        )}
      </Typography>
      <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ letterSpacing: 0.3 }}>
        {label}
      </Typography>
      {subtitle && (
        <Typography variant="caption" display="block" color="text.disabled" sx={{ mt: 0.25 }}>
          {subtitle}
        </Typography>
      )}
    </CardContent>
  </Card>
);

/** Horizontal bar row used in room/lecturer/department panels */
const BarRow: React.FC<{
  label: string;
  sublabel?: string;
  rightLabel: string;
  rightSublabel?: string;
  value: number;           // 0–100
  color: string;
  statusChip?: string;
}> = ({ label, sublabel, rightLabel, rightSublabel, value, color, statusChip }) => (
  <Box sx={{ mb: 2 }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
        <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: 180 }}>
          {label}
        </Typography>
        {statusChip && (
          <Chip
            label={statusChip}
            size="small"
            sx={{
              height: 18,
              fontSize: '0.62rem',
              fontWeight: 700,
              bgcolor: alpha(color, 0.12),
              color,
              border: `1px solid ${alpha(color, 0.3)}`,
            }}
          />
        )}
      </Box>
      <Box sx={{ textAlign: 'right', ml: 1, flexShrink: 0 }}>
        <Typography variant="body2" fontWeight={700} color={color}>
          {rightLabel}
        </Typography>
        {rightSublabel && (
          <Typography variant="caption" color="text.disabled">{rightSublabel}</Typography>
        )}
      </Box>
    </Box>
    {sublabel && (
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.4 }}>
        {sublabel}
      </Typography>
    )}
    <LinearProgress
      variant="determinate"
      value={Math.min(value, 100)}
      sx={{
        height: 7,
        borderRadius: 4,
        bgcolor: alpha(color, 0.1),
        '& .MuiLinearProgress-bar': {
          bgcolor: color,
          borderRadius: 4,
          transition: 'transform 0.8s ease',
        },
      }}
    />
  </Box>
);

/** Time distribution arc/bar block */
const TimePeriodBlock: React.FC<{
  label: string;
  data: TimeSlotData;
  color: string;
  emoji: string;
}> = ({ label, data, color, emoji }) => (
  <Box
    sx={{
      flex: 1,
      p: 2,
      borderRadius: 3,
      border: '1px solid',
      borderColor: alpha(color, 0.25),
      bgcolor: alpha(color, 0.04),
      textAlign: 'center',
      position: 'relative',
      overflow: 'hidden',
      '&::after': {
        content: '""',
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: `${Math.min(data.percentage, 100)}%`,
        bgcolor: alpha(color, 0.08),
        transition: 'height 1s ease',
        pointerEvents: 'none',
      },
    }}
  >
    <Typography variant="h4" sx={{ mb: 0.25 }}>{emoji}</Typography>
    <Typography variant="h5" fontWeight={800} sx={{ color, lineHeight: 1 }}>
      {data.percentage}%
    </Typography>
    <Typography variant="caption" fontWeight={700} color="text.secondary">
      {label}
    </Typography>
    <Typography variant="caption" display="block" color="text.disabled">
      {data.time_range}
    </Typography>
    <Chip
      label={`${data.count} slots`}
      size="small"
      sx={{
        mt: 1,
        height: 20,
        fontSize: '0.65rem',
        bgcolor: alpha(color, 0.12),
        color,
        fontWeight: 600,
      }}
    />
  </Box>
);

const DayDistributionChart: React.FC<{ data: DayDistributionData[]; primaryColor: string }> = ({
  data,
  primaryColor: _primaryColor,
}) => {
  const normalizedData = data.length > 0
    ? data
    : [
        { day_index: 0, day_name: 'Monday', short_label: 'Mon', count: 0, percentage: 0 },
        { day_index: 1, day_name: 'Tuesday', short_label: 'Tue', count: 0, percentage: 0 },
        { day_index: 2, day_name: 'Wednesday', short_label: 'Wed', count: 0, percentage: 0 },
        { day_index: 3, day_name: 'Thursday', short_label: 'Thu', count: 0, percentage: 0 },
        { day_index: 4, day_name: 'Friday', short_label: 'Fri', count: 0, percentage: 0 },
      ];
  const maxCount = Math.max(...normalizedData.map((day) => day.count), 1);
  return (
    <Box>
      <Typography
        variant="caption"
        color="text.secondary"
        fontWeight={700}
        sx={{ letterSpacing: 0.5, textTransform: 'uppercase', mb: 1.5, display: 'block' }}
      >
        Day Distribution
      </Typography>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
          gap: 1.25,
          alignItems: 'end',
          minHeight: 260,
          px: 0.5,
        }}
      >
        {normalizedData.map((day) => (
          <Tooltip
            key={day.day_index}
            title={`${day.day_name}: ${day.count} slots (${day.percentage}%)`}
            arrow
          >
            {(() => {
              const peakPct = maxCount > 0 ? (day.count / maxCount) * 100 : 0;
              const barColor = dayLoadColor(peakPct);
              return (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'stretch',
                  justifyContent: 'flex-end',
                  minWidth: 0,
                  height: '100%',
                }}
              >
              <Box
                sx={{
                  height: `${Math.max((day.count / maxCount) * 100, day.count > 0 ? 18 : 4)}%`,
                  minHeight: day.count > 0 ? 28 : 8,
                  borderRadius: '16px 16px 10px 10px',
                  background: `linear-gradient(180deg, ${alpha(barColor, 0.72)} 0%, ${barColor} 100%)`,
                  boxShadow: day.count > 0 ? `0 10px 26px ${alpha(barColor, 0.22)}` : 'none',
                  border: `1px solid ${alpha(barColor, 0.18)}`,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'flex-end',
                  alignItems: 'center',
                  px: 1,
                  py: 1.2,
                }}
              >
                <Typography
                  variant="h6"
                  sx={{
                    color: '#fff',
                    fontWeight: 800,
                    lineHeight: 1,
                    fontSize: { xs: '1rem', sm: '1.2rem' },
                  }}
                >
                  {day.count}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: '#fff',
                    fontWeight: 700,
                    opacity: 0.9,
                    mt: 0.5,
                  }}
                >
                  {day.percentage}%
                </Typography>
              </Box>
              <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textAlign: 'center', mt: 1 }}>
                {day.short_label}
              </Typography>
            </Box>
              );
            })()}
          </Tooltip>
        ))}
      </Box>
    </Box>
  );
};

/** Auto-generated insights from the analytics data */
const Insights: React.FC<{ data: AnalyticsData }> = ({ data }) => {
  const insights = useMemo(() => {
    const tips: { level: 'ok' | 'warn' | 'error'; text: string }[] = [];
    const warnings = data.warnings ?? EMPTY_WARNINGS;

    // Room insights
    const overloadedRooms = data.room_utilization.filter(r => r.utilization_rate >= 80);
    const unusedRooms = data.room_utilization.filter(r => r.slots_used === 0);
    if (overloadedRooms.length > 0)
      tips.push({ level: 'warn', text: `${overloadedRooms.length} room(s) are heavily utilised (≥80%). Consider redistributing sessions.` });
    if (unusedRooms.length > 0)
      tips.push({ level: 'ok', text: `${unusedRooms.length} room(s) are unused this term — available for ad-hoc bookings.` });

    // Lecturer insights
    const overloaded = data.lecturer_workload.filter(l => l.workload_percentage >= 100);
    const underutilised = data.lecturer_workload.filter(l => l.workload_percentage < 30 && l.max_hours > 0);
    if (overloaded.length > 0)
      tips.push({ level: 'error', text: `${overloaded.length} lecturer(s) exceed their maximum weekly hours. Review assignments immediately.` });
    if (underutilised.length > 0)
      tips.push({ level: 'ok', text: `${underutilised.length} lecturer(s) are under 30% workload — capacity available for reassignment.` });

    // Time insights
    const { morning, afternoon, evening } = data.time_slot_utilization;
    if (evening.percentage > 15)
      tips.push({ level: 'warn', text: `${evening.percentage}% of sessions are scheduled in the evening. This may impact student attendance.` });
    if (morning.percentage > 60)
      tips.push({ level: 'ok', text: 'Most sessions are in the morning — optimal for peak cognitive performance.' });
    if (afternoon.percentage > morning.percentage)
      tips.push({ level: 'warn', text: 'Afternoon sessions outnumber morning sessions. Consider rebalancing for better engagement.' });

    if (warnings.total > 0) {
      tips.push({
        level: 'warn',
        text: `${warnings.total} slot(s) are running in largest-room fallback mode. Biggest seat shortfall is ${warnings.largest_overflow}.`,
      });
    }

    // Generic
    if (tips.length === 0)
      tips.push({ level: 'ok', text: 'Timetable looks balanced. No major issues detected.' });

    return tips.slice(0, 4); // keep it concise
  }, [data]);

  const iconMap = { ok: <OkIcon sx={{ fontSize: 16, color: '#2e7d32', flexShrink: 0 }} />, warn: <WarnIcon sx={{ fontSize: 16, color: '#ed6c02', flexShrink: 0 }} />, error: <ErrIcon sx={{ fontSize: 16, color: '#d32f2f', flexShrink: 0 }} /> };
  const bgMap = { ok: alpha('#2e7d32', 0.06), warn: alpha('#ed6c02', 0.06), error: alpha('#d32f2f', 0.06) };

  return (
    <Stack spacing={1}>
      {insights.map((ins, i) => (
        <Box
          key={i}
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1.25,
            p: 1.25,
            borderRadius: 2,
            bgcolor: bgMap[ins.level],
            border: `1px solid ${ins.level === 'error' ? alpha('#d32f2f', 0.2) : ins.level === 'warn' ? alpha('#ed6c02', 0.2) : alpha('#2e7d32', 0.2)}`,
          }}
        >
          {iconMap[ins.level]}
          <Typography variant="body2" color="text.primary" lineHeight={1.5}>
            {ins.text}
          </Typography>
        </Box>
      ))}
    </Stack>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// Main component
// ────────────────────────────────────────────────────────────────────────────

const TimetableAnalytics: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const theme = useTheme();
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || theme.palette.primary.main;

  const fetchAnalytics = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get<AnalyticsData>('/timetables/active/analytics');
      const normalized = normalizeAnalyticsData(response.data);

      const hasUsableDayDistribution = normalized.day_distribution.some((day) => day.count > 0);

      if (normalized.timetable_id && !hasUsableDayDistribution) {
        try {
          const timetableResponse = await api.get<TimetableWithSlotsLite>(`/timetables/${normalized.timetable_id}`);
          const derivedDayDistribution = buildDayDistributionFromSlots(timetableResponse.data?.slots || []);
          const derivedTotal = derivedDayDistribution.reduce((sum, day) => sum + day.count, 0);
          if (derivedTotal > 0) {
            normalized.day_distribution = derivedDayDistribution;
          }
        } catch {
          // Keep analytics response as-is if the slot fallback lookup fails.
        }
      }

      setAnalytics(normalized);
      setLastUpdated(new Date());
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg ?? JSON.stringify(d)).join('; '));
      } else {
        setError('Failed to load analytics data. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // ── Loading state ──
  if (loading) {
    return <AnalyticsSkeleton />;
  }

  // ── Error state ──
  if (error || !analytics) {
    return (
      <Box sx={{ py: 4 }}>
        <Alert
          severity="warning"
          icon={<AutoGraphIcon />}
          sx={{ borderRadius: 3, mb: 2 }}
          action={
            <IconButton size="small" onClick={fetchAnalytics} color="inherit">
              <RefreshIcon fontSize="small" />
            </IconButton>
          }
        >
          {error || 'No analytics data available for the active timetable.'}
        </Alert>
      </Box>
    );
  }

  // ── Derived values ──
  const { summary, room_utilization, lecturer_workload, course_distribution, time_slot_utilization } = analytics;
  const warnings = analytics.warnings ?? EMPTY_WARNINGS;
  const capacityFallbacks = warnings.capacity_fallbacks;

  const kpiCards = [
    { label: 'Scheduled Slots',    value: summary.total_slots,          unit: '',   icon: <ScheduleIcon sx={{ fontSize: 20 }} />,  color: primaryColor,    subtitle: 'across all year levels' },
    { label: 'Active Courses',     value: summary.unique_courses,       unit: '',   icon: <CourseIcon sx={{ fontSize: 20 }} />,    color: '#FF8C00',       subtitle: 'in the timetable' },
    { label: 'Venues Used',        value: summary.unique_rooms,         unit: '',   icon: <RoomIcon sx={{ fontSize: 20 }} />,      color: '#4A90E2',       subtitle: `of ${room_utilization.length} total rooms` },
    { label: 'Active Lecturers',   value: summary.unique_lecturers,     unit: '',   icon: <PersonIcon sx={{ fontSize: 20 }} />,   color: '#2e7d32',       subtitle: `of ${lecturer_workload.length} total` },
    { label: 'Student Groups',     value: summary.unique_groups,        unit: '',   icon: <GroupsIcon sx={{ fontSize: 20 }} />,   color: '#9c27b0',       subtitle: 'with assigned sessions' },
    { label: 'Contact Hours/Wk',   value: summary.total_contact_hours,  unit: 'h',  icon: <AccessTimeIcon sx={{ fontSize: 20 }} />, color: '#d32f2f',    subtitle: 'total teaching time' },
    { label: 'Capacity Warnings',  value: warnings.total, unit: '', icon: <WarnIcon sx={{ fontSize: 20 }} />, color: '#b26a00', subtitle: capacityFallbacks.length > 0 ? `largest gap ${warnings.largest_overflow} seats` : 'no room overflows detected' },
  ];

  const avgRoomUtilization = room_utilization.length > 0
    ? Math.round(room_utilization.reduce((acc, r) => acc + r.utilization_rate, 0) / room_utilization.length)
    : 0;

  const avgLecturerLoad = lecturer_workload.length > 0
    ? Math.round(lecturer_workload.reduce((acc, l) => acc + l.workload_percentage, 0) / lecturer_workload.length)
    : 0;

  return (
    <Box sx={{ pb: 4 }}>
      {/* ══ HERO HEADER ══ */}
      <Paper
        elevation={0}
        sx={{
          mb: 3,
          p: 3,
          borderRadius: 4,
          border: '1px solid',
          borderColor: 'divider',
          background: `linear-gradient(135deg, ${alpha(primaryColor, 0.08)} 0%, transparent 60%)`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              p: 1.5,
              borderRadius: 3,
              background: `linear-gradient(135deg, ${primaryColor}, ${alpha(primaryColor, 0.6)})`,
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              boxShadow: `0 4px 14px ${alpha(primaryColor, 0.4)}`,
            }}
          >
            <AutoGraphIcon sx={{ fontSize: 28 }} />
          </Box>
          <Box>
            <Typography variant="h5" fontWeight={800} sx={{ lineHeight: 1.2 }}>
              Analytics Dashboard
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {analytics.timetable_name}
              &nbsp;·&nbsp;
              {lastUpdated && (
                <Typography component="span" variant="caption" color="text.disabled">
                  Updated {lastUpdated.toLocaleTimeString()}
                </Typography>
              )}
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Chip
            icon={<RoomIcon sx={{ fontSize: '14px !important' }} />}
            label={`Avg Room Load: ${Math.min(100, avgRoomUtilization)}%`}
            size="small"
            sx={{ bgcolor: alpha(utilizationColor(avgRoomUtilization), 0.1), color: utilizationColor(avgRoomUtilization), fontWeight: 700 }}
          />
          <Chip
            icon={<PersonIcon sx={{ fontSize: '14px !important' }} />}
            label={`Avg Lecturer Load: ${Math.min(100, avgLecturerLoad)}%`}
            size="small"
            sx={{ bgcolor: alpha(statusColor(avgLecturerLoad >= 80 ? 'high' : avgLecturerLoad >= 50 ? 'moderate' : 'light'), 0.1), color: statusColor(avgLecturerLoad >= 80 ? 'high' : avgLecturerLoad >= 50 ? 'moderate' : 'light'), fontWeight: 700 }}
          />
          <Tooltip title="Refresh analytics">
            <IconButton
              size="small"
              onClick={fetchAnalytics}
              sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
            >
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>

      {/* ══ KPI STRIP ══ */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {kpiCards.map(card => (
          <Grid item xs={6} sm={4} md={2} key={card.label}>
            <KpiCard {...card} />
          </Grid>
        ))}
      </Grid>

      {/* ══ MAIN PANELS (2-column on lg) ══ */}
      <Grid container spacing={3}>

        {/* ── Room Utilization ── */}
        <Grid item xs={12} lg={6}>
          <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
              <Box sx={{ p: 0.75, borderRadius: 2, bgcolor: alpha('#4A90E2', 0.1), color: '#4A90E2', display: 'flex' }}>
                <RoomIcon sx={{ fontSize: 20 }} />
              </Box>
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>Room Utilisation</Typography>
                <Typography variant="caption" color="text.secondary">
                  {room_utilization.filter(r => r.slots_used > 0).length} of {room_utilization.length} rooms in use
                </Typography>
              </Box>
            </Box>
            <Box sx={{ maxHeight: 340, overflowY: 'auto', pr: 0.5 }}>
              {room_utilization.slice(0, 10).map(room => (
                <BarRow
                  key={room.room_id}
                  label={room.room_name}
                  sublabel={`${room.building} · Cap: ${room.capacity} · ${room.room_type}`}
                  rightLabel={`${Math.min(100, room.utilization_rate)}%`}
                  rightSublabel={`${room.slots_used} slots`}
                  value={room.utilization_rate}
                  color={utilizationColor(room.utilization_rate)}
                  statusChip={room.status}
                />
              ))}
              {room_utilization.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                  No room data available
                </Typography>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* ── Lecturer Workload ── */}
        <Grid item xs={12} lg={6}>
          <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
              <Box sx={{ p: 0.75, borderRadius: 2, bgcolor: alpha('#FF8C00', 0.1), color: '#FF8C00', display: 'flex' }}>
                <PersonIcon sx={{ fontSize: 20 }} />
              </Box>
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>Lecturer Workload</Typography>
                <Typography variant="caption" color="text.secondary">
                  {lecturer_workload.filter(l => l.workload_percentage >= 100).length} overloaded ·{' '}
                  {lecturer_workload.filter(l => l.total_hours === 0).length} unassigned
                </Typography>
              </Box>
            </Box>
            <Box sx={{ maxHeight: 340, overflowY: 'auto', pr: 0.5 }}>
              {lecturer_workload.slice(0, 10).map(lec => (
                <BarRow
                  key={lec.lecturer_id}
                  label={lec.lecturer_name}
                  sublabel={`${lec.department} · ${lec.total_hours}h of ${lec.max_hours}h max`}
                  rightLabel={`${Math.min(100, lec.workload_percentage)}%`}
                  value={lec.workload_percentage}
                  color={statusColor(lec.status)}
                  statusChip={lec.status}
                />
              ))}
              {lecturer_workload.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                  No lecturer data available
                </Typography>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* ── Course Distribution ── */}
        <Grid item xs={12} md={5}>
          <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
              <Box sx={{ p: 0.75, borderRadius: 2, bgcolor: alpha('#2e7d32', 0.1), color: '#2e7d32', display: 'flex' }}>
                <SchoolIcon sx={{ fontSize: 20 }} />
              </Box>
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>Department Breakdown</Typography>
                <Typography variant="caption" color="text.secondary">Courses scheduled per department</Typography>
              </Box>
            </Box>
            {course_distribution.map((dept, idx) => (
              <BarRow
                key={idx}
                label={dept.department}
                sublabel={`${dept.total_hours}h contact time`}
                rightLabel={`${dept.percentage}%`}
                rightSublabel={`${dept.course_count} courses`}
                value={dept.percentage}
                color={BRAND_PALETTE[idx % BRAND_PALETTE.length]}
              />
            ))}
            {course_distribution.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                No distribution data available
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* ── Time Distribution + Rhythm ── */}
        <Grid item xs={12} md={7}>
          <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid', borderColor: 'divider', height: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
              <Box sx={{ p: 0.75, borderRadius: 2, bgcolor: alpha('#9c27b0', 0.1), color: '#9c27b0', display: 'flex' }}>
                <AccessTimeIcon sx={{ fontSize: 20 }} />
              </Box>
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>Time Distribution</Typography>
                <Typography variant="caption" color="text.secondary">When sessions happen across the day</Typography>
              </Box>
            </Box>

            <Stack direction="row" spacing={1.5} sx={{ mb: 3 }}>
              <TimePeriodBlock label="Morning"   data={time_slot_utilization.morning}   color="#FF8C00" emoji="🌅" />
              <TimePeriodBlock label="Afternoon" data={time_slot_utilization.afternoon} color="#4A90E2" emoji="☀️" />
              <TimePeriodBlock label="Evening"   data={time_slot_utilization.evening}   color="#9c27b0" emoji="🌙" />
            </Stack>

            <Divider sx={{ mb: 2.5 }} />

            <DayDistributionChart data={analytics.day_distribution} primaryColor={primaryColor} />
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid', borderColor: capacityFallbacks.length ? alpha('#ed6c02', 0.35) : 'divider' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Box sx={{ p: 0.75, borderRadius: 2, bgcolor: alpha('#ed6c02', 0.1), color: '#ed6c02', display: 'flex' }}>
                  <WarnIcon sx={{ fontSize: 20 }} />
                </Box>
                <Box>
                  <Typography variant="subtitle1" fontWeight={700}>Capacity Fallback Warnings</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Sessions placed in the largest compatible room even though demand still exceeds seats
                  </Typography>
                </Box>
              </Box>
              <Chip
                label={capacityFallbacks.length ? `${warnings.total} active` : 'None'}
                size="small"
                sx={{
                  bgcolor: alpha(capacityFallbacks.length ? '#ed6c02' : '#2e7d32', 0.1),
                  color: capacityFallbacks.length ? '#ed6c02' : '#2e7d32',
                  fontWeight: 700,
                }}
              />
            </Box>

            {capacityFallbacks.length > 0 ? (
              <Stack spacing={1.25}>
                {capacityFallbacks.map((warning) => (
                  <Box
                    key={warning.slot_id}
                    sx={{
                      p: 1.5,
                      borderRadius: 2,
                      border: '1px solid',
                      borderColor: alpha('#ed6c02', 0.18),
                      bgcolor: alpha('#ed6c02', 0.04),
                      display: 'grid',
                      gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1.5fr) minmax(0, 1fr) auto' },
                      gap: 1.5,
                      alignItems: 'center',
                    }}
                  >
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="body2" fontWeight={700} noWrap>
                        {warning.course_code} · {warning.course_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {warning.group_names.join(', ')} · {warning.session_type} · {dayLabel(warning.day_of_week)} {warning.start_time}-{warning.end_time}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" fontWeight={600}>
                        {warning.room_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Seats {warning.room_capacity} for demand {warning.required_size}
                      </Typography>
                    </Box>
                    <Chip
                      label={`+${warning.overflow} overflow`}
                      size="small"
                      sx={{
                        justifySelf: { xs: 'flex-start', md: 'flex-end' },
                        bgcolor: alpha('#d32f2f', 0.1),
                        color: '#d32f2f',
                        fontWeight: 700,
                      }}
                    />
                  </Box>
                ))}
              </Stack>
            ) : (
              <Alert severity="success" icon={<OkIcon />} sx={{ borderRadius: 2 }}>
                No largest-room fallbacks are active in the current timetable.
              </Alert>
            )}
          </Paper>
        </Grid>

        {/* ── AI-Style Insights ── */}
        <Grid item xs={12}>
          <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
              <Box sx={{ p: 0.75, borderRadius: 2, bgcolor: alpha(primaryColor, 0.1), color: primaryColor, display: 'flex' }}>
                <InsightIcon sx={{ fontSize: 20 }} />
              </Box>
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>Auto-Generated Insights</Typography>
                <Typography variant="caption" color="text.secondary">
                  Based on current timetable configuration — for coordinator review
                </Typography>
              </Box>
            </Box>
            <Insights data={analytics} />
          </Paper>
        </Grid>

      </Grid>
    </Box>
  );
};

export default TimetableAnalytics;
